"""
metadata.py — frontmatter and section-annotation normalisation.

Consumed by the engine (F2) and the server. No spaCy dependency.
"""

from __future__ import annotations

_TOPIC_TYPE_ALIASES: dict[str, str] = {
    "how-to":      "howto",
    "how_to":      "howto",
    "guide":       "howto",
    "tutorial":    "tutorial",
    "concept":     "concept",
    "conceptual":  "concept",
    "explanation": "explanation",
    "explain":     "explanation",
    "reference":   "reference",
    "ref":         "reference",
    "faq":         "faq",
    "adr":         "adr",
    "postmortem":  "postmortem",
    "technical":   "technical",
    "general":     "general",
}


def normalise_topic_type(raw: str) -> str:
    """Normalise a raw topic_type string to a canonical value."""
    key = raw.strip().lower()
    return _TOPIC_TYPE_ALIASES.get(key, key)


def normalise_owner(raw: str | list) -> list[str]:
    """
    Normalise an owner value to a list of Backstage-format entity refs.

    Plain team names are prefixed with 'group:'. Already-qualified refs
    (containing ':') are passed through unchanged.
    """
    items: list[str] = [raw] if isinstance(raw, str) else list(raw)
    result: list[str] = []
    for item in items:
        s = item.strip()
        if not s:
            continue
        if ":" not in s:
            s = f"group:{s}"
        result.append(s)
    return result


def normalise_frontmatter(fm: dict) -> dict:
    """
    Apply canonical normalisation to a parsed frontmatter dict.

    - topic_type  → normalise_topic_type()
    - owner       → normalise_owner()
    - tags/author/audience → coerce scalar to list
    Returns a new dict; does not mutate the input.
    """
    out = dict(fm)

    if "topic_type" in out:
        out["topic_type"] = normalise_topic_type(str(out["topic_type"]))

    if "owner" in out:
        out["owner"] = normalise_owner(out["owner"])

    for list_field in ("tags", "author", "audience"):
        if list_field in out and not isinstance(out[list_field], list):
            out[list_field] = [out[list_field]]

    return out
