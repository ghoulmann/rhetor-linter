import re
from typing import Any, Dict, List

from rhetoric_lint.rules._list_utils import group_contiguous_lists

GENRES = frozenset({"all"})


def _line_from_pos(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rhetoric checks:

    - Rhetoric.ComplexitySpike: propositional density in long paragraphs.
    - Rhetoric.ThroatClearing: first-10-words stopword ratio.
    - Rhetoric.ModalAmbiguity: mixed prescriptive/advisory modals in ordered lists.

    Note: Rhetoric.TrivializingLanguage was migrated to Vale YAML (SP6).
    Load it via --style-dir style-sets/ --style Rhetoric.
    """
    path = context["path"]
    text = context["text"]
    nlp = context.get("nlp")
    const = context.get("const")
    sections = context.get("sections", [])
    issues: List[Dict[str, Any]] = []

    if not text:
        return []

    # Split into paragraph blocks (simple Markdown paragraphs)
    blocks = re.split(r"\n\s*\n+", text)
    offset = 0
    for block in blocks:
        s = block.strip()
        if not s:
            offset += len(block)
            continue

        # skip headings and lists and code fences
        if (
            re.match(r"^#{1,6}\s+", s)
            or re.match(r"^([-*]|\d+\.)\s+", s)
            or s.startswith("```")
        ):
            offset += len(block)
            continue

        # find position of this block starting at offset
        pos = text.find(block, offset)
        if pos < 0:
            pos = offset

        # Analyze with spaCy
        try:
            doc = nlp(s)
        except Exception:
            doc = None

        words = [t for t in (doc if doc else []) if t.is_alpha]
        total_words = len(words)

        # Rhetoric.ComplexitySpike
        if total_words > 30 and doc:
            noun_count = sum(1 for t in words if t.pos_ in ("NOUN", "PROPN"))
            verb_count = sum(1 for t in words if t.pos_ == "VERB")
            pd = (noun_count + verb_count) / max(1, total_words)
            if pd > const.THRESHOLDS.get("PROPOSITIONAL_DENSITY", 0.6):
                issues.append(
                    {
                        "path": path,
                        "line": _line_from_pos(text, pos),
                        "message": f"High propositional density ({pd:.2f}) in long paragraph — consider adding a visual aid (diagram)",
                        "severity": const.RULE_SEVERITY_LEVELS.get(
                            "Rhetoric.ComplexitySpike", "warning"
                        ),
                        "check": "Rhetoric.ComplexitySpike",
                    }
                )

        # Rhetoric.ThroatClearing: examine first 10 words for stopword ratio
        if doc:
            first_alpha = [t for t in doc if t.is_alpha][:10]
            if first_alpha:
                stop_count = sum(1 for t in first_alpha if t.is_stop)
                ratio = stop_count / len(first_alpha)
                if ratio > const.THRESHOLDS.get("THROAT_CLEARING_SALIENCE", 0.8):
                    issues.append(
                        {
                            "path": path,
                            "line": _line_from_pos(text, pos),
                            "message": "Opening of paragraph contains excessive meta-discourse/stopwords — consider removing throat-clearing",
                            "severity": const.RULE_SEVERITY_LEVELS.get(
                                "Rhetoric.ThroatClearing", "suggestion"
                            ),
                            "check": "Rhetoric.ThroatClearing",
                        }
                    )

        offset = pos + len(block)

    # -------------------------------------------------------------------------
    # Rhetoric.ModalAmbiguity — section/node-aware pass
    # -------------------------------------------------------------------------
    _modal_ambiguity_check(issues, sections, path, text, const)

    # -------------------------------------------------------------------------
    # Rhetoric.UnresolvedContrast — section/node-aware pass
    # -------------------------------------------------------------------------
    genre = context.get("genre", "general")
    _unresolved_contrast_check(issues, sections, path, text, const, genre)

    return issues


_SKIP_NODE_TYPES = frozenset({
    "ListItem", "List", "Code", "CodeFence", "FencedCode",
    "BlockCode", "Image", "BlockQuote",
})


def _modal_ambiguity_check(
    issues: List[Dict[str, Any]],
    sections: List[Dict[str, Any]],
    path: str,
    text: str,
    const: Any,
) -> None:
    """Rhetoric.ModalAmbiguity: flag ordered lists that mix prescriptive and advisory modals."""
    prescriptive = getattr(const, "PRESCRIPTIVE_MODALS", [
        "must", "shall", "required", "have to", "need to", "has to", "needs to",
    ]) if const else ["must", "shall", "required", "have to", "need to", "has to", "needs to"]
    advisory = getattr(const, "ADVISORY_MODALS", [
        "should", "may", "might", "recommend", "consider", "optional",
    ]) if const else ["should", "may", "might", "recommend", "consider", "optional"]
    severity = (
        const.RULE_SEVERITY_LEVELS.get("Rhetoric.ModalAmbiguity", "warning")
        if const else "warning"
    )

    prescriptive_pats = [
        re.compile(r"\b" + re.escape(m) + r"\b", re.IGNORECASE) for m in prescriptive
    ]
    advisory_pats = [
        re.compile(r"\b" + re.escape(m) + r"\b", re.IGNORECASE) for m in advisory
    ]

    class _Item:
        __slots__ = ("text", "_start")

        def __init__(self, text: str, start: int):
            self.text = text
            self._start = start

        def start(self) -> int:
            return self._start

        def end(self) -> int:
            return self._start + len(self.text)

    ol_items: List[_Item] = []
    for sec in sections:
        for para in sec.get("paragraphs", []):
            for node in para.get("nodes", []):
                if (
                    node.get("type") == "ListItem"
                    and node.get("list_type") == "ol"
                ):
                    ol_items.append(
                        _Item(node.get("text", ""), node.get("start", para.get("pos", 0)))
                    )

    if not ol_items:
        return

    def _classify(item_text: str) -> str:
        for pat in prescriptive_pats:
            if pat.search(item_text):
                return "prescriptive"
        for pat in advisory_pats:
            if pat.search(item_text):
                return "advisory"
        return "none"

    for group in group_contiguous_lists(ol_items, text):
        if len(group) < 2:
            continue

        first_class = "none"
        diverger = None
        seen_prescriptive = False
        seen_advisory = False

        for item in group:
            cls = _classify(item.text)
            if cls == "prescriptive":
                seen_prescriptive = True
            elif cls == "advisory":
                seen_advisory = True
            if cls != "none" and first_class == "none":
                first_class = cls
            elif cls != "none" and cls != first_class and diverger is None:
                diverger = item

        if seen_prescriptive and seen_advisory:
            target = diverger if diverger is not None else group[0]
            issues.append({
                "path": path,
                "line": _line_from_pos(text, target.start()),
                "column": 1,
                "message": (
                    "Ordered list mixes prescriptive modals (must/shall/required) "
                    "with advisory modals (should/may/recommend) — reader cannot "
                    "distinguish mandatory steps from optional ones."
                ),
                "severity": severity,
                "check": "Rhetoric.ModalAmbiguity",
            })


# ---------------------------------------------------------------------------
# Rhetoric.UnresolvedContrast
# ---------------------------------------------------------------------------

# Topic types where an unresolved contrast is a defect — orientation/discussion sections.
# "general" is excluded: unclassified sections are declarative procedural prose that
# legitimately uses conditional contrast ("if X, otherwise Y") without a resolution frame.
# Howto/tutorial/reference/faq are also excluded — contrast is valid in those contexts.
_CONTRAST_GATE_TOPIC_TYPES = frozenset({
    "concept", "explanation",
})

_CONTRAST_WORD_RE_CACHE: dict = {}


def _build_contrast_pattern(signals: list) -> "re.Pattern":
    key = tuple(signals)
    if key not in _CONTRAST_WORD_RE_CACHE:
        alts = "|".join(re.escape(s) for s in sorted(signals, key=len, reverse=True))
        _CONTRAST_WORD_RE_CACHE[key] = re.compile(
            r"(?<![a-zA-Z])(" + alts + r")(?![a-zA-Z])", re.I
        )
    return _CONTRAST_WORD_RE_CACHE[key]


def _unresolved_contrast_check(
    issues: List[Dict[str, Any]],
    sections: List[Dict[str, Any]],
    path: str,
    text: str,
    const: Any,
    genre: str,
) -> None:
    """Rhetoric.UnresolvedContrast: contrast signal without a following resolution."""

    contrast_signals = getattr(const, "CONTRAST_SIGNALS", [])
    resolution_signals = getattr(const, "CONTRAST_RESOLUTION_SIGNALS", [])
    min_sentences = getattr(const, "CONTRAST_MIN_SENTENCES", 3)
    max_per_para = getattr(const, "CONTRAST_UNRESOLVED_MAX_PER_PARA", 2)

    if not contrast_signals:
        return

    contrast_re = _build_contrast_pattern(contrast_signals)
    resolution_lower = [s.lower() for s in resolution_signals]

    def _has_contrast(sentence_text: str) -> bool:
        t = sentence_text.lower().strip()
        m = contrast_re.search(t)
        if not m:
            return False
        # Signal must appear at position < 30% of sentence length (word-boundary safe)
        return m.start() / max(1, len(t)) < 0.30

    def _has_resolution(sentence_text: str) -> bool:
        t = sentence_text.lower()
        return any(sig in t for sig in resolution_lower)

    for sec in sections:
        if sec.get("topic_type", "general") not in _CONTRAST_GATE_TOPIC_TYPES:
            continue
        for para in sec.get("paragraphs", []):
            # Skip non-prose nodes (code, images, list items, blockquotes)
            nodes = para.get("nodes", [])
            if nodes and any(n.get("type") in _SKIP_NODE_TYPES for n in nodes):
                continue

            sentences = para.get("sentences", [])
            if len(sentences) < min_sentences:
                continue

            findings_this_para = 0
            for i, sent in enumerate(sentences):
                if findings_this_para >= max_per_para:
                    break
                sent_text = sent.get("span", None)
                if sent_text is not None:
                    sent_str = sent_text.text
                else:
                    sent_str = ""
                if not _has_contrast(sent_str):
                    continue
                # Check rest of contrast sentence + next sentence for resolution
                resolved = _has_resolution(sent_str)
                if not resolved and i + 1 < len(sentences):
                    next_sent = sentences[i + 1]
                    next_text = next_sent.get("span", None)
                    if next_text is not None:
                        resolved = _has_resolution(next_text.text)
                if not resolved:
                    issues.append({
                        "path": path,
                        "line": sent.get("line", _line_from_pos(text, para.get("pos", 0))),
                        "column": 1,
                        "message": (
                            "Contrast signal (however/but/although/…) without a "
                            "following resolution — add 'therefore', 'instead', "
                            "'the solution is', or similar to clarify the takeaway."
                        ),
                        "severity": getattr(const, "RULE_SEVERITY_LEVELS", {}).get(
                            "Rhetoric.UnresolvedContrast", "suggestion"
                        ),
                        "check": "Rhetoric.UnresolvedContrast",
                    })
                    findings_this_para += 1
