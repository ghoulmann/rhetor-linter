"""Troubleshooting topic-type checks for rhetor-linter.

Checks
------
Troubleshooting.MissingRemediation
    A Troubleshooting section has no ordered list (remediation steps must be sequenced).
Troubleshooting.UnorderedRemediation
    Remediation steps are in an unordered list; order matters and they must be ol.
"""

from typing import Any, Dict, List

GENRES = frozenset({"all"})


def _list_counts(section: Dict[str, Any]):
    """Return (ol_count, ul_count) of list items in section."""
    ol = ul = 0
    for para in section.get("paragraphs", []):
        for node in para.get("nodes", []):
            if node.get("type") == "ListItem":
                if node.get("list_type") == "ol":
                    ol += 1
                else:
                    ul += 1
    return ol, ul


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context.get("path", "")
    text = context.get("text", "")
    sections = context.get("sections") or []
    issues: List[Dict[str, Any]] = []

    for sec in sections:
        if sec.get("topic_type") != "troubleshooting":
            continue

        ol_count, ul_count = _list_counts(sec)
        start = sec.get("start", 0)
        line = text[:start].count("\n") + 1 if text else 1
        heading = (sec.get("heading") or "this section").strip()

        if ol_count == 0 and ul_count == 0:
            issues.append({
                "path": path,
                "line": line,
                "column": 1,
                "message": (
                    f"Troubleshooting section '{heading}' has no remediation steps "
                    "— add an ordered list of resolution steps."
                ),
                "severity": "warning",
                "check": "Troubleshooting.MissingRemediation",
            })
        elif ol_count == 0 and ul_count > 0:
            issues.append({
                "path": path,
                "line": line,
                "column": 1,
                "message": (
                    f"Troubleshooting section '{heading}' uses an unordered list for "
                    "remediation steps — use a numbered list (order matters)."
                ),
                "severity": "warning",
                "check": "Troubleshooting.UnorderedRemediation",
            })

    return issues
