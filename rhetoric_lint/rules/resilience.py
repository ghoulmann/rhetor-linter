import re
from typing import Any, Dict, List, Optional, Tuple

GENRES = frozenset({"all"})

# Common action verbs used to identify imperative headings
_ACTION_VERBS = {
    "add", "apply", "build", "check", "clone", "configure", "connect",
    "create", "delete", "deploy", "disable", "download", "enable", "generate",
    "install", "open", "push", "remove", "restart", "run", "set", "start",
    "stop", "test", "update", "upload", "verify",
}


def _line_from_pos(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def _first_verb_tag(heading: str, nlp) -> Optional[Tuple[str, str]]:
    """Return (pos, tag) of the first non-punctuation token in heading, or None."""
    clean = re.sub(r"`+.*?`+", "", heading).strip()
    if not clean or nlp is None:
        return None
    try:
        doc = nlp(clean)
    except Exception:
        return None
    for tok in doc:
        if tok.is_space or tok.is_punct:
            continue
        pos_ = tok.pos_
        tag_ = tok.tag_
        # Fallback: spaCy sometimes tags capitalized verbs as NNP
        if tag_ == "NNP" and tok.text.lower() in _ACTION_VERBS:
            pos_, tag_ = "VERB", "VB"
        return (pos_, tag_)
    return None


def _is_procedural_section(sec: dict, nlp, const) -> bool:
    """Return True if the section is task/procedure-oriented."""
    heading = (sec.get("heading") or "").strip()
    heading_lower = heading.lower()

    task_keywords = [k.lower() for k in getattr(const, "TASK_LIST_KEYWORDS", [])]

    # 1. Heading contains a task keyword
    if any(kw in heading_lower for kw in task_keywords):
        return True

    # 2. Heading first token is imperative (VB) or gerund (VBG)
    result = _first_verb_tag(heading, nlp)
    if result and result[1] in ("VB", "VBG"):
        return True

    # 3. Section contains an ordered list
    for para in sec.get("paragraphs", []):
        for node in para.get("nodes", []):
            if node.get("type") == "ListItem" and node.get("list_type") == "ol":
                return True

    return False


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Resilience.ErrorPathPresence — flag procedural sections with no error guidance.

    A section that walks through a task but never mentions what to do when
    things go wrong leaves readers stranded. This check flags sections that
    look procedural (task keywords in heading, ordered list, or imperative
    verb) but contain no failure/troubleshooting language.
    """
    issues = []
    path = context.get("path", "")
    text = context.get("text", "")
    sections = context.get("sections", [])
    nlp = context.get("nlp")
    const = context.get("const")

    error_keywords = [k.lower() for k in getattr(const, "ERROR_PATH_KEYWORDS", [])] if const else []
    severity = (
        getattr(const, "RULE_SEVERITY_LEVELS", {}).get("Resilience.ErrorPathPresence", "warning")
        if const else "warning"
    )

    if not error_keywords:
        return issues

    for sec in sections:
        if not sec.get("heading"):
            continue
        if not _is_procedural_section(sec, nlp, const):
            continue

        # Collect all paragraph text in the section
        all_text = " ".join(
            para.get("text", "") for para in sec.get("paragraphs", [])
        ).lower()

        if not all_text.strip():
            continue

        # Pass if any error-path keyword is present
        if any(kw in all_text for kw in error_keywords):
            continue

        sec_pos = sec.get("start", 0)
        line = _line_from_pos(text, sec_pos)
        heading = sec.get("heading", "")

        issues.append({
            "path": path,
            "line": line,
            "column": 1,
            "message": (
                f"Procedural section '{heading}' has no failure guidance, "
                "troubleshooting note, or error scenario."
            ),
            "severity": severity,
            "check": "Resilience.ErrorPathPresence",
        })

    return issues
