from __future__ import annotations

from typing import Any, Dict, List, Set

from rhetoric_lint.overlap import channelize_tokens

GENRES = frozenset({"all"})

_GENERIC_NOUNS = {
    "section", "paragraph", "example", "thing", "content", "text",
    "way", "part", "time", "point", "item", "type", "kind", "form",
    "case", "method", "result", "value", "data", "information",
    "document", "file", "step", "list", "note", "page",
}


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Cohesion.AbandonedTopic — flag key nouns introduced early but never seen again.

    A noun that appears in ≥2 sentences in the first few sections sets a reader
    expectation that it is a key concept.  If it never reappears in later
    sections, the topic thread is abandoned.
    """
    issues: List[Dict[str, Any]] = []
    path = context.get("path", "")
    text = context.get("text", "")
    const = context.get("const")
    sections = context.get("sections", [])

    min_mentions = (
        int(getattr(const, "LEXICAL_CHAIN_MIN_EARLY_MENTIONS", 2)) if const else 2
    )
    early_count = (
        int(getattr(const, "LEXICAL_CHAIN_EARLY_SECTION_COUNT", 2)) if const else 2
    )
    severity = (
        getattr(const, "RULE_SEVERITY_LEVELS", {}).get("Cohesion.AbandonedTopic", "suggestion")
        if const else "suggestion"
    )

    if len(sections) < 4:
        return []

    pronouns = set(getattr(const, "PRONOUNS", [])) if const else set()

    # Collect noun mentions in early sections (count distinct sentences per noun)
    early_noun_sentences: Dict[str, int] = {}
    for sec in sections[:early_count]:
        for para in sec.get("paragraphs", []):
            for srec in para.get("sentences", []):
                span = srec.get("span")
                if span is None:
                    continue
                channels = channelize_tokens(span, pronouns)
                for noun in channels.get("nouns", set()):
                    if noun in _GENERIC_NOUNS:
                        continue
                    if len(noun) < 3:
                        continue
                    early_noun_sentences[noun] = early_noun_sentences.get(noun, 0) + 1

    # Filter to introduced nouns (≥ min_mentions sentences)
    introduced = {n for n, c in early_noun_sentences.items() if c >= min_mentions}
    if not introduced:
        return []

    # Collect all noun lemmas from later sections
    later_nouns: Set[str] = set()
    for sec in sections[early_count:]:
        for para in sec.get("paragraphs", []):
            for srec in para.get("sentences", []):
                span = srec.get("span")
                if span is None:
                    continue
                channels = channelize_tokens(span, pronouns)
                later_nouns |= channels.get("nouns", set())

    # Find abandoned topics
    abandoned = sorted(introduced - later_nouns)
    if not abandoned:
        return []

    # Apply stem bridge: if a 6-char prefix of an introduced noun matches
    # any later noun prefix, the topic may still be present in variant form
    later_stems = {n[:6] for n in later_nouns if len(n) >= 5}
    truly_abandoned = []
    for noun in abandoned:
        if len(noun) >= 5 and noun[:6] in later_stems:
            continue
        truly_abandoned.append(noun)

    if not truly_abandoned:
        return []

    noun_list = ", ".join(f"'{n}'" for n in truly_abandoned[:5])
    suffix = f" (and {len(truly_abandoned) - 5} more)" if len(truly_abandoned) > 5 else ""
    issues.append({
        "path": path,
        "line": 1,
        "message": (
            f"Abandoned topic: {noun_list}{suffix} "
            f"introduced in early sections but never referenced again."
        ),
        "severity": severity,
        "check": "Cohesion.AbandonedTopic",
    })

    return issues
