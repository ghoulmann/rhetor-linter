import re
from typing import Any, Dict, List

GENRES = frozenset({"all"})


def _line_from_pos(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rhetoric checks:

    - Rhetoric.ComplexitySpike: propositional density in long paragraphs.
    - Rhetoric.ThroatClearing: first-10-words stopword ratio.
    """
    path = context["path"]
    text = context["text"]
    nlp = context.get("nlp")
    const = context.get("const")
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

    return issues
