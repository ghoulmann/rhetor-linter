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
    - Rhetoric.TrivializingLanguage: trivializing words in prose paragraphs.
    - Rhetoric.ModalAmbiguity: mixed prescriptive/advisory modals in ordered lists.
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
    # Rhetoric.TrivializingLanguage — section/node-aware pass
    # -------------------------------------------------------------------------
    _trivializing_check(issues, sections, path, text, const)

    # -------------------------------------------------------------------------
    # Rhetoric.ModalAmbiguity — section/node-aware pass
    # -------------------------------------------------------------------------
    _modal_ambiguity_check(issues, sections, path, text, const)

    return issues


_SKIP_NODE_TYPES = frozenset({
    "ListItem", "List", "Code", "CodeFence", "FencedCode",
    "BlockCode", "Image", "BlockQuote",
})


def _trivializing_check(
    issues: List[Dict[str, Any]],
    sections: List[Dict[str, Any]],
    path: str,
    text: str,
    const: Any,
) -> None:
    """Rhetoric.TrivializingLanguage: flag trivializing words in prose paragraphs."""
    words = getattr(const, "TRIVIALIZING_WORDS", [
        "simply", "just", "easily", "obviously", "of course", "straightforward",
    ]) if const else ["simply", "just", "easily", "obviously", "of course", "straightforward"]
    severity = (
        const.RULE_SEVERITY_LEVELS.get("Rhetoric.TrivializingLanguage", "suggestion")
        if const else "suggestion"
    )

    patterns = []
    for phrase in words:
        if " " in phrase:
            pat = re.compile(re.escape(phrase), re.IGNORECASE)
        else:
            pat = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
        patterns.append((phrase, pat))

    for sec in sections:
        for para in sec.get("paragraphs", []):
            nodes = para.get("nodes", [])
            if not nodes:
                continue
            node_type = nodes[0].get("type", "Paragraph")
            if node_type in _SKIP_NODE_TYPES:
                continue

            para_text = para.get("text", "")
            if not para_text:
                continue
            para_pos = para.get("pos", 0)

            for phrase, pat in patterns:
                m = pat.search(para_text)
                if not m:
                    continue

                # Suppress "just" in temporal/recency contexts
                if phrase == "just":
                    window = para_text[max(0, m.start() - 30):m.end() + 30].lower()
                    if re.search(
                        r"\bjust\s+(released|updated|published|merged|deployed|added|"
                        r"fixed|changed|created|removed|now|recently)\b",
                        window,
                    ):
                        continue
                    if re.search(r"\b(have|has|had|was|were)\s+just\b", window):
                        continue

                abs_pos = para_pos + m.start()
                line = _line_from_pos(text, abs_pos)
                issues.append({
                    "path": path,
                    "line": line,
                    "column": 1,
                    "message": (
                        f"Trivializing language: '{phrase}' implies readers should find "
                        f"this easy, which alienates readers who don't. Consider removing."
                    ),
                    "severity": severity,
                    "check": "Rhetoric.TrivializingLanguage",
                })
                break  # one issue per paragraph (first matching phrase wins)


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
