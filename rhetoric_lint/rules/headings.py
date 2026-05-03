import re
from typing import Any, Dict, List

from rhetoric_lint.engine import get_synsets

GENRES = frozenset({"all"})


def _line_from_pos(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context.get("path")
    text = context.get("text", "")
    nlp = context.get("nlp")
    const = context.get("const")
    issues: List[Dict[str, Any]] = []

    if not text:
        return []

    # Consume AST-backed sections provided by the engine
    sections = context.get("sections", []) or []
    headings = []
    for s in sections:
        htext = s.get("heading")
        if htext:
            headings.append(
                {"level": s.get("level", 0), "text": htext, "pos": s.get("start", 0)}
            )

    # If we require an H1, ensure it's present (first non-empty heading)
    if const and getattr(const, "REQUIRE_H1", False):
        first_heading = next((h for h in headings if h["text"]), None)
        if not first_heading or first_heading["level"] != 1:
            issues.append(
                {
                    "path": path,
                    "line": 1,
                    "message": "Document missing top-level H1 heading",
                    "severity": "warning",
                    "check": "Heading.H1",
                }
            )

    # Find the main H1 text and its synsets (for InformationScent comparisons)
    h1 = next((h for h in headings if h["level"] == 1), None)
    h1_syn = set()
    if h1:
        try:
            h1_syn = get_synsets(h1["text"]) or set()
        except Exception:
            h1_syn = set()

    weak_verbs = getattr(const, "WEAK_VERBS", {}) if const else {}
    generic_tokens = set(getattr(const, "GENERIC_HEADINGS", [])) if const else set()

    for h_idx, h in enumerate(headings):
        level = h["level"]
        htext = h["text"]
        pos = h["pos"]
        line = _line_from_pos(text, pos)

        # Nearest ancestor heading (most recent preceding heading with lower level).
        ancestor = None
        for prev in reversed(headings[:h_idx]):
            if prev["level"] < level:
                ancestor = prev
                break

        # Skip empty headings
        if not htext:
            continue

        # Analyze with spaCy if available
        doc = None
        if nlp:
            try:
                doc = nlp(htext)
            except Exception:
                doc = None

        # Heading.VividScent: detect weak verbs and suggest vivid replacements
        if doc:
            for tok in doc:
                lemma = getattr(tok, "lemma_", "").lower()
                if lemma in weak_verbs:
                    replacements = ", ".join(weak_verbs.get(lemma, []))
                    issues.append(
                        {
                            "path": path,
                            "line": line,
                            "message": f"Heading contains weak verb '{tok.text}'; consider using more vivid verbs: {replacements}",
                            "severity": (
                                const.RULE_SEVERITY_LEVELS.get(
                                    "Heading.VividScent", "suggestion"
                                )
                                if const
                                else "suggestion"
                            ),
                            "check": "Heading.VividScent",
                        }
                    )

        # Heading.Generic: generic tokens or lack of concrete noun/verb
        low = htext.lower().strip()
        generic_flag = low in generic_tokens
        pos_flag = False
        if doc:
            pos_flag = not any(
                t.pos_ in ("NOUN", "PROPN", "VERB") for t in doc if t.is_alpha
            )
        else:
            # fallback simple heuristic: no alpha word longer than 2 chars
            words = [w for w in re.findall(r"\w+", htext) if len(w) > 2]
            pos_flag = len(words) == 0

        if generic_flag or pos_flag:
            issues.append(
                {
                    "path": path,
                    "line": line,
                    "message": "Generic or non-descriptive heading — add a concrete noun or task verb to improve scannability",
                    "severity": (
                        const.RULE_SEVERITY_LEVELS.get("Heading.Generic", "warning")
                        if const
                        else "warning"
                    ),
                    "check": "Heading.Generic",
                }
            )

        # Heading.InformationScent: check H2+ headings for topic connection to H1.
        # Three-stage pipeline: standard-name gate → synset check → lexical fallback.
        if level >= 2 and h1:
            standard_names = set(getattr(const, "STANDARD_SECTION_NAMES", [])) if const else set()
            # An H1 is "specific" only if it carries enough content words to act as
            # a topical anchor. 2 content words (e.g. "Writing a scraper") is too
            # generic — many legitimate subheads share neither lemma nor synset
            # with such an H1. Require >= 3.
            h1_is_specific = nlp and len(
                [t for t in nlp(h1["text"]) if t.is_alpha and not t.is_stop]
            ) >= 3
            # If the H1 is too generic to act as an anchor, skip InformationScent
            # for non-standard-named headings — there is no meaningful baseline
            # against which to measure overlap.
            if not h1_is_specific and htext.lower().strip() not in standard_names:
                continue

            # Stage 1: Standard section name gate (level-aware)
            if standard_names and htext.lower().strip() in standard_names:
                if level == 2 and h1_is_specific:
                    # H2 under a specific H1: structural name is valid — suppress
                    continue
                else:
                    # H3+: generic name without guaranteed parent context in ToC/RAG —
                    # emit enrichment suggestion instead of a synset warning
                    h1_topic_word = ""
                    if nlp:
                        h1_topic_word = next(
                            (t.text for t in nlp(h1["text"]) if t.is_alpha and not t.is_stop),
                            "",
                        )
                    issues.append({
                        "path": path,
                        "line": line,
                        "message": (
                            f"Heading '{htext}' is a generic section name at H{level} — "
                            f"consider adding a topic qualifier (e.g., "
                            f"'{h1_topic_word} {htext}') to improve scannability "
                            f"and RAG chunk retrieval"
                        ),
                        "severity": "suggestion",
                        "check": "Heading.InformationScent",
                    })
                    continue

            # Stage 2: Synset overlap check
            try:
                h_syn = get_synsets(htext) or set()
            except Exception:
                h_syn = set()

            if h1_syn and h_syn and not h1_syn.isdisjoint(h_syn):
                continue  # synset bridge found — no issue

            # Ancestor-path bridging: an H3 under H2 'Code a scraper' may share no
            # tokens with the H1 but be perfectly coherent with its parent. If the
            # ancestor heading overlaps with this heading AND with the H1, the
            # heading is reachable through the path and should not warn.
            if ancestor and ancestor is not h1:
                try:
                    a_syn = get_synsets(ancestor["text"]) or set()
                except Exception:
                    a_syn = set()
                ancestor_bridges_h = bool(a_syn and h_syn and not a_syn.isdisjoint(h_syn))
                ancestor_bridges_h1 = bool(a_syn and h1_syn and not a_syn.isdisjoint(h1_syn))
                if not (ancestor_bridges_h and ancestor_bridges_h1) and nlp:
                    a_lemmas = {
                        t.lemma_.lower() for t in nlp(ancestor["text"]) if not t.is_stop and t.is_alpha
                    }
                    h1_lemmas = {
                        t.lemma_.lower() for t in nlp(h1["text"]) if not t.is_stop and t.is_alpha
                    }
                    h_lemmas = (
                        {t.lemma_.lower() for t in doc if not t.is_stop and t.is_alpha}
                        if doc else set()
                    )
                    if not ancestor_bridges_h:
                        ancestor_bridges_h = bool(a_lemmas & h_lemmas)
                    if not ancestor_bridges_h1:
                        ancestor_bridges_h1 = bool(a_lemmas & h1_lemmas)
                if ancestor_bridges_h and ancestor_bridges_h1:
                    continue  # path-bridged through ancestor heading

            # Stage 3: Lexical fallback — shared content-word lemmas downgrade to suggestion
            if nlp and doc:
                h1_content_lemmas = {
                    t.lemma_.lower() for t in nlp(h1["text"]) if not t.is_stop and t.is_alpha
                }
                h_content_lemmas = {
                    t.lemma_.lower() for t in doc if not t.is_stop and t.is_alpha
                }
                # Exact lemma match — heading is self-identifying, suppress entirely
                exact_lexical_bridge = bool(h1_content_lemmas & h_content_lemmas)
                # Morphological root match (handles install/installation, configure/configuration,
                # and spaCy lemmatizer artifacts like "Installation"→"installation" vs "instal")
                stem_only_bridge = False
                if not exact_lexical_bridge:
                    h1_stems = {l[:6] for l in h1_content_lemmas if len(l) >= 5}
                    h_stems = {l[:6] for l in h_content_lemmas if len(l) >= 5}
                    stem_only_bridge = bool(h1_stems & h_stems)
                if exact_lexical_bridge:
                    continue  # exact bridge — heading is self-identifying, no issue
                if stem_only_bridge:
                    issues.append({
                        "path": path,
                        "line": line,
                        "message": (
                            f"H{level} '{htext}' is topically linked to the H1 via shared "
                            f"keywords, but may read ambiguously as a standalone heading "
                            f"(ToC entry or RAG chunk label) — consider whether it "
                            f"identifies the topic clearly without its parent context"
                        ),
                        "severity": "suggestion",  # downgraded from warning
                        "check": "Heading.InformationScent",
                    })
                    continue  # stem bridge found — suppress warning

            # No synset or lexical bridge — emit warning
            issues.append({
                "path": path,
                "line": line,
                "message": (
                    f"H{level} '{htext}' has no semantic overlap with the document H1 — "
                    f"consider adding context (e.g., keywords from the H1) to improve "
                    f"findability"
                ),
                "severity": (
                    const.RULE_SEVERITY_LEVELS.get("Heading.InformationScent", "warning")
                    if const else "warning"
                ),
                "check": "Heading.InformationScent",
            })

    # Heading.NearDuplicate: flag heading pairs with high content-word Jaccard similarity
    if nlp:
        for idx_a, h_a in enumerate(headings):
            lemmas_a = {
                t.lemma_.lower() for t in nlp(h_a["text"]) if t.is_alpha and not t.is_stop
            }
            if not lemmas_a:
                continue
            for h_b in headings[idx_a + 1:]:
                lemmas_b = {
                    t.lemma_.lower() for t in nlp(h_b["text"]) if t.is_alpha and not t.is_stop
                }
                if not lemmas_b:
                    continue
                union = lemmas_a | lemmas_b
                jaccard = len(lemmas_a & lemmas_b) / len(union) if union else 0.0
                if jaccard >= 0.7:
                    b_line = _line_from_pos(text, h_b["pos"])
                    issues.append({
                        "path": path,
                        "line": b_line,
                        "message": (
                            f"Heading '{h_b['text']}' is near-duplicate of "
                            f"'{h_a['text']}' (Jaccard {jaccard:.2f}) — "
                            f"consider differentiating to aid navigation and RAG retrieval"
                        ),
                        "severity": (
                            const.RULE_SEVERITY_LEVELS.get("Heading.NearDuplicate", "suggestion")
                            if const else "suggestion"
                        ),
                        "check": "Heading.NearDuplicate",
                    })

    return issues
