import re
from typing import Any, Dict, List

from rhetoric_lint.engine import get_synsets

# Identifiers like court_scraper.scrapers, captcha_service_required, sites_meta
# arrive from spaCy as a single token with is_alpha=False because of the dots,
# underscores, or dashes. These tokens carry topical signal in technical prose
# and must contribute to lemma overlap; without them, sentence pairs that share
# only identifier tokens look unrelated to cohesion analysis.
_IDENT_SPLIT_RE = re.compile(r"[._\-]")
from rhetoric_lint.overlap import (
    adjacent_overlap_metrics,
    channelize_tokens,
    set_overlap_metrics,
    sentence_pair_givenness_metrics,
    token_channel_counts,
)

GENRES = frozenset({"all"})


def _line_from_pos(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def _token_lemmas(sent):
    # filter out very generic nouns that create false-positive lemma bridges
    GENERIC_TOKENS = {
        "sentence",
        "section",
        "paragraph",
        "item",
        "example",
        "thing",
        "content",
        "text",
    }
    lemmas = set()
    for tok in sent:
        if not (getattr(tok, "is_alpha", False)):
            # Identifier-like non-alpha tokens (course_scraper.scrapers,
            # captcha_service_required) — split on separators and add each
            # alphabetic component as its own lemma.
            surface = (getattr(tok, "text", "") or "").lower()
            if not surface or not any(sep in surface for sep in "._-"):
                continue
            for part in _IDENT_SPLIT_RE.split(surface):
                if len(part) < 2 or not part.isalpha():
                    continue
                if part in GENERIC_TOKENS:
                    continue
                lemmas.add(part)
            continue
        if getattr(tok, "is_stop", False):
            continue
        # prefer the spaCy lemma if available, otherwise fall back to the token text
        lem = (getattr(tok, "lemma_", "") or tok.text or "").lower().strip()
        if not lem:
            continue
        if lem in GENERIC_TOKENS:
            continue
        lemmas.add(lem)
        surface = getattr(tok, "text", "").lower().strip()
        if surface and surface != lem and surface not in GENERIC_TOKENS:
            lemmas.add(surface)
    return lemmas


def _initial_alpha_lemmas(sent, max_tokens: int) -> List[str]:
    out: List[str] = []
    for tok in sent:
        if not getattr(tok, "is_alpha", False):
            continue
        lem = (getattr(tok, "lemma_", "") or tok.text or "").lower().strip()
        if not lem:
            continue
        out.append(lem)
        if len(out) >= max_tokens:
            break
    return out


def _build_connective_lookup(signposts: set):
    by_len = {}
    for phrase in signposts:
        parts = tuple(x for x in phrase.lower().split() if x)
        if not parts:
            continue
        by_len.setdefault(len(parts), set()).add(parts)
    return by_len


def _build_connective_relation_map(signposts_dict: Dict[str, list]) -> Dict[tuple, str]:
    """Map each connective phrase tuple to its rhetorical relation type."""
    relation_map: Dict[tuple, str] = {}
    for relation, phrases in signposts_dict.items():
        for phrase in phrases:
            parts = tuple(x for x in phrase.lower().split() if x)
            if parts:
                relation_map[parts] = relation
    return relation_map


def _match_sentence_initial_connective(sent, connective_lookup: Dict[int, set], window: int) -> str:
    lemmas = _initial_alpha_lemmas(sent, max_tokens=window)
    if not lemmas:
        return ""

    max_len = min(window, len(lemmas))
    for size in range(max_len, 0, -1):
        phrases = connective_lookup.get(size, set())
        if not phrases:
            continue
        cand = tuple(lemmas[:size])
        if cand in phrases:
            return " ".join(cand)
    return ""


def _paragraph_block_type(para: Dict[str, Any]) -> str:
    nodes = para.get("nodes") or []
    if not nodes:
        return "Paragraph"
    return str(nodes[0].get("type") or "Paragraph")


def _is_structural_block(block_type: str) -> bool:
    return block_type in {"ListItem", "List", "Code", "CodeFence", "FencedCode", "BlockCode", "Image"}


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check local cohesion between adjacent sentences in paragraphs.

    For each paragraph, examine pairs of sentences (S_{n-1}, S_n) and
    test three bridge types (lemma overlap, synset overlap, signpost start).
    If none apply, report a `Cohesion.Break` issue.
    """
    path = context.get("path")
    text = context.get("text", "")
    nlp = context.get("nlp")
    const = context.get("const")
    sections = context.get("sections", [])
    issues: List[Dict[str, Any]] = []
    seen_issue_keys = set()

    def _append_issue(issue: Dict[str, Any]) -> None:
        key = (issue.get("path"), issue.get("line"), issue.get("check"), issue.get("message"))
        if key in seen_issue_keys:
            return
        seen_issue_keys.add(key)
        issues.append(issue)

    if not nlp or not sections:
        return []

    signposts = set()
    pronouns = set(getattr(const, "PRONOUNS", [])) if const else set()
    if const:
        for v in getattr(const, "SIGNPOSTS", {}).values():
            for w in v:
                signposts.add(w.lower())
    connective_lookup = _build_connective_lookup(signposts)
    signposts_dict = dict(getattr(const, "SIGNPOSTS", {})) if const else {}
    connective_relation_map = _build_connective_relation_map(signposts_dict)

    adversative_max_overlap = (
        float(getattr(const, "COHESION_ADVERSATIVE_MAX_OVERLAP", 0.4)) if const else 0.4
    )

    max_pron_density = float(getattr(const, "COHESION_MAX_PRONOUN_DENSITY", 0.35)) if const else 0.35
    max_pronoun_noun_ratio = (
        float(getattr(const, "COHESION_MAX_PRONOUN_NOUN_RATIO", 1.5)) if const else 1.5
    )
    min_repeated_content_ratio = (
        float(getattr(const, "COHESION_MIN_REPEATED_CONTENT_RATIO", 0.2)) if const else 0.2
    )
    min_content_overlap_strong = (
        float(getattr(const, "COHESION_MIN_CONTENT_OVERLAP_STRONG", 0.2)) if const else 0.2
    )
    min_content_overlap_with_connective = (
        float(getattr(const, "COHESION_MIN_CONTENT_OVERLAP_WITH_CONNECTIVE", 0.08)) if const else 0.08
    )
    connective_window_tokens = (
        int(getattr(const, "COHESION_CONNECTIVE_WINDOW_TOKENS", 5)) if const else 5
    )
    structural_connective_divergence_min_tokens = (
        int(getattr(const, "COHESION_STRUCTURAL_CONNECTIVE_DIVERGENCE_MIN_TOKENS", 18))
        if const
        else 18
    )

    prose_block_types = {"Paragraph", "BlockQuote", "RawText"}

    for sec in sections:
        # Build a flattened list of sentences across prose-like paragraphs only.
        # Structural blocks (lists/code) are excluded to avoid boundary artifacts.
        sent_records = []
        paragraphs = sec.get("paragraphs", [])
        for para_idx, para in enumerate(paragraphs):
            block_type = _paragraph_block_type(para)
            if block_type not in prose_block_types:
                continue

            prev_para_block_type = (
                _paragraph_block_type(paragraphs[para_idx - 1]) if para_idx > 0 else ""
            )

            ptext = para.get("text", "")
            ppos = para.get("pos", 0)

            # Prefer paragraph-level sentence records from the parser.
            para_sents = para.get("sentences")
            if para_sents:
                for srec in para_sents:
                    sent_records.append(
                        (
                            srec.get("span"),
                            srec.get("start"),
                            ppos,
                            ptext,
                            block_type,
                            prev_para_block_type,
                        )
                    )
                continue

            # Fallback: build sentence records from a fresh paragraph doc.
            try:
                doc = nlp(ptext)
            except Exception:
                continue

            sents = list(doc.sents)
            for s in sents:
                abs_start = ppos + getattr(s, "start_char", 0)
                sent_records.append(
                    (
                        s,
                        abs_start,
                        ppos,
                        ptext,
                        block_type,
                        prev_para_block_type,
                    )
                )

        if len(sent_records) < 2:
            continue

        sent_channels = []
        sent_counts = []
        for s, _, _, _, _, _ in sent_records:
            sent_channels.append(channelize_tokens(s, pronouns))
            sent_counts.append(token_channel_counts(s, pronouns))

        content_segments = [x["content"] for x in sent_channels]
        noun_segments = [x["nouns"] for x in sent_channels]
        pron_segments = [x["pronouns"] for x in sent_channels]
        argument_segments = [x["argument"] for x in sent_channels]

        overlap_snapshot = {
            "content_adj1": adjacent_overlap_metrics(content_segments, lookahead=1),
            "content_adj2": adjacent_overlap_metrics(content_segments, lookahead=2),
            "noun_adj1": adjacent_overlap_metrics(noun_segments, lookahead=1),
            "pronoun_adj1": adjacent_overlap_metrics(pron_segments, lookahead=1),
            "argument_adj1": adjacent_overlap_metrics(argument_segments, lookahead=1),
        }

        for i in range(1, len(sent_records)):
            prev, _, _, _, _, _ = sent_records[i - 1]
            cur, cur_start_abs, cur_ppos, _, _, prev_para_block_type = sent_records[i]

            # Skip very short sentences
            if len([t for t in cur if t.is_alpha]) < 3:
                continue

            # Skip sentence pairs that cross a structural or blockquote paragraph boundary.
            # Code blocks and NOTE callouts are intentional discourse unit breaks — they do
            # not require lexical continuity with the surrounding prose.
            _prev_ppos = sent_records[i - 1][2]
            _cur_ppos = sent_records[i][2]
            if _prev_ppos != _cur_ppos:  # cross-paragraph pair
                _prev_block = sent_records[i - 1][4]   # block_type of prev sentence's para
                _cur_block = sent_records[i][4]         # block_type of cur sentence's para
                if (
                    _is_structural_block(prev_para_block_type)
                    or any(b in ("BlockQuote", "Quote") for b in (_prev_block, _cur_block))
                ):
                    continue

            givenness = sentence_pair_givenness_metrics(
                sent_channels[i - 1],
                sent_channels[i],
                sent_counts[i],
            )

            filtered_prev_lemmas = _token_lemmas(prev)
            filtered_cur_lemmas = _token_lemmas(cur)

            pair_overlap = set_overlap_metrics(
                filtered_prev_lemmas,
                filtered_cur_lemmas,
            )
            content_overlap = pair_overlap["containment_left"]
            filtered_repeated_content_ratio = pair_overlap["containment_right"]

            connective = _match_sentence_initial_connective(
                cur,
                connective_lookup,
                window=connective_window_tokens,
            )
            has_connective = bool(connective)

            has_strong_overlap = content_overlap >= min_content_overlap_strong
            has_overlap_for_connective = (
                content_overlap >= min_content_overlap_with_connective
            )
            has_givenness_support = (
                filtered_repeated_content_ratio >= min_repeated_content_ratio
            )

            # Givenness break: pronoun-heavy sentence without lexical carry-over.
            if (
                givenness["pronoun_density"] >= max_pron_density
                and givenness["pronoun_noun_ratio"] >= max_pronoun_noun_ratio
                and givenness["repeated_content_ratio"] < min_repeated_content_ratio
            ):
                try:
                    abs_start = int(cur_start_abs)
                except Exception:
                    para_pos = cur_ppos if isinstance(cur_ppos, int) else 0
                    abs_start = para_pos + getattr(cur, "start_char", 0)
                line = _line_from_pos(text, abs_start)
                _append_issue(
                    {
                        "path": path,
                        "line": line,
                        "message": "Pronoun-heavy sentence lacks clear lexical givenness from prior context",
                        "detail": (
                            f"pronoun_density={givenness['pronoun_density']:.2f}, "
                            f"pronoun_noun_ratio={givenness['pronoun_noun_ratio']:.2f}, "
                            f"repeated_content_ratio={givenness['repeated_content_ratio']:.2f}"
                        ),
                        "severity": (
                            const.RULE_SEVERITY_LEVELS.get("Cohesion.GivennessBreak", "warning")
                            if const
                            else "warning"
                        ),
                        "check": "Cohesion.GivennessBreak",
                    }
                )
                continue

            # Misused connective: validate that the connective's rhetorical
            # relation matches the actual semantic relationship between sentences.
            if has_connective and connective_relation_map:
                conn_parts = tuple(connective.split())
                relation = connective_relation_map.get(conn_parts, "")
                misused = False
                misuse_reason = ""

                if relation == "adversative":
                    # Adversative ("however", "but") implies contrast — high
                    # content overlap suggests the sentences agree, not contrast.
                    if content_overlap > adversative_max_overlap:
                        misused = True
                        misuse_reason = (
                            f"'{connective}' signals contrast, but these sentences "
                            f"share significant content (overlap {content_overlap:.2f}). "
                            f"Consider removing the connective or rewriting to clarify the contrast."
                        )
                elif relation == "causal":
                    # Causal ("therefore", "because") implies a reasoning chain —
                    # zero shared nouns means there is no visible logical link.
                    noun_overlap = set_overlap_metrics(
                        sent_channels[i - 1].get("nouns", set()),
                        sent_channels[i].get("nouns", set()),
                    )
                    if noun_overlap["overlap_count"] == 0:
                        misused = True
                        misuse_reason = (
                            f"'{connective}' signals a cause-effect relationship, "
                            f"but these sentences share no key terms. "
                            f"Make the logical connection explicit or choose a different transition."
                        )
                elif relation == "additive":
                    # Additive ("also", "moreover") implies building on the same
                    # topic — zero content overlap means there is nothing to add to.
                    if content_overlap == 0.0 and not (filtered_prev_lemmas & filtered_cur_lemmas):
                        misused = True
                        misuse_reason = (
                            f"'{connective}' signals addition to an existing topic, "
                            f"but these sentences share no content. "
                            f"Consider whether this transition accurately reflects the relationship."
                        )

                if misused:
                    try:
                        abs_start = int(cur_start_abs)
                    except Exception:
                        para_pos = cur_ppos if isinstance(cur_ppos, int) else 0
                        abs_start = para_pos + getattr(cur, "start_char", 0)
                    line = _line_from_pos(text, abs_start)
                    _append_issue(
                        {
                            "path": path,
                            "line": line,
                            "message": misuse_reason,
                            "severity": (
                                const.RULE_SEVERITY_LEVELS.get(
                                    "Cohesion.MisusedConnective", "suggestion"
                                )
                                if const
                                else "suggestion"
                            ),
                            "check": "Cohesion.MisusedConnective",
                        }
                    )
                    continue

            # Joint discourse decision: permit connective-based transitions only
            # when there is at least weak lexical overlap or givenness support.
            if has_connective and (has_overlap_for_connective or has_givenness_support):
                continue

            if has_strong_overlap:
                continue

            # Lemma bridge
            if filtered_prev_lemmas & filtered_cur_lemmas:
                continue

            # Stem bridge: 6-char morphological prefix (require/requirement, install/installation)
            # Applied only as fallback when direct lemma overlap is zero, to avoid
            # over-bridging short words (config/conflict, contain/contaminate).
            prev_stems = {l[:6] for l in filtered_prev_lemmas if len(l) >= 5}
            cur_stems = {l[:6] for l in filtered_cur_lemmas if len(l) >= 5}
            if prev_stems & cur_stems:
                continue

            # 5-char secondary stem bridge: handles spaCy inconsistently lemmatizing
            # the same proper noun across positions (e.g. mkdocs→mkdocs vs mkdocs→mkdoc).
            prev_stems5 = {l[:5] for l in filtered_prev_lemmas if len(l) >= 5}
            cur_stems5 = {l[:5] for l in filtered_cur_lemmas if len(l) >= 5}
            if prev_stems5 & cur_stems5:
                continue

            # Synset bridge (optional) — compute synsets only for non-generic
            # content tokens to avoid spurious overlap on words like "sentence".
            try:
                syn_prev = set()
                syn_cur = set()
                prev_content = []
                cur_content = []
                for tok in prev:
                    if not tok.is_alpha or tok.is_stop:
                        continue
                    lem = (getattr(tok, "lemma_", "") or tok.text or "").lower()
                    if lem in {"sentence", "section", "paragraph"}:
                        continue
                    prev_content.append(lem)
                for tok in cur:
                    if not tok.is_alpha or tok.is_stop:
                        continue
                    lem = (getattr(tok, "lemma_", "") or tok.text or "").lower()
                    if lem in {"sentence", "section", "paragraph"}:
                        continue
                    cur_content.append(lem)
                for w in prev_content:
                    syn_prev |= get_synsets(w) or set()
                for w in cur_content:
                    syn_cur |= get_synsets(w) or set()
            except Exception:
                syn_prev = set()
                syn_cur = set()

            has_synset_bridge = bool(syn_prev and syn_cur and not syn_prev.isdisjoint(syn_cur))
            if has_synset_bridge:
                continue

            # Suppress cohesion breaks at structural boundaries when the
            # new prose sentence starts with an explicit discourse connective.
            # Keep the warning only for clearly unrelated long jumps.
            has_high_divergence = (
                content_overlap <= 0.0
                and filtered_repeated_content_ratio <= 0.0
                and not has_synset_bridge
                and len(filtered_cur_lemmas) >= structural_connective_divergence_min_tokens
            )
            if (
                has_connective
                and _is_structural_block(prev_para_block_type)
                and not has_high_divergence
            ):
                continue

            # If none of the bridges applied, emit issue
            # compute absolute start: prefer the absolute start recorded by engine.lint_files
            try:
                abs_start = int(cur_start_abs)
            except Exception:
                para_pos = cur_ppos if isinstance(cur_ppos, int) else 0
                abs_start = para_pos + getattr(cur, "start_char", 0)
            line = _line_from_pos(text, abs_start)
            _append_issue(
                {
                    "path": path,
                    "line": line,
                    "message": "Local cohesion break: sentence appears unrelated to the previous sentence",
                    "detail": (
                        "adjacent overlap snapshot — "
                        f"content@1={overlap_snapshot['content_adj1']['overlap_per_opportunity']:.2f}, "
                        f"content@2={overlap_snapshot['content_adj2']['overlap_per_opportunity']:.2f}, "
                        f"nouns@1={overlap_snapshot['noun_adj1']['overlap_per_opportunity']:.2f}, "
                        f"pronouns@1={overlap_snapshot['pronoun_adj1']['overlap_per_opportunity']:.2f}, "
                        f"argument@1={overlap_snapshot['argument_adj1']['overlap_per_opportunity']:.2f}; "
                        f"pair_content_overlap={content_overlap:.2f}; "
                        f"connective={connective or 'none'}; "
                        f"pair_repeated_content_ratio={filtered_repeated_content_ratio:.2f}"
                    ),
                    "severity": (
                        const.RULE_SEVERITY_LEVELS.get("Cohesion.Break", "warning")
                        if const
                        else "warning"
                    ),
                    "check": "Cohesion.Break",
                }
            )

    return issues
