"""Concept topic-type checks for rhetor-linter.

Checks
------
Concept.ProcedureLeak
    A Concept section contains ≥3 ordered-list imperative steps, indicating
    it has drifted into How-To territory.
"""

from typing import Any, Dict, List

GENRES = frozenset({"all"})

# Minimum ordered-list items before flagging a procedure leak in a Concept section
_MIN_OL_ITEMS = 3


def _ol_item_count(section: Dict[str, Any]) -> int:
    count = 0
    for para in section.get("paragraphs", []):
        for node in para.get("nodes", []):
            if node.get("type") == "ListItem" and node.get("list_type") == "ol":
                count += 1
    return count


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context.get("path", "")
    text = context.get("text", "")
    sections = context.get("sections") or []
    const = context.get("const")
    min_items = getattr(const, "CONCEPT_PROCEDURE_LEAK_MIN_OL_ITEMS", _MIN_OL_ITEMS)
    issues: List[Dict[str, Any]] = []

    for sec in sections:
        if sec.get("topic_type") != "concept":
            continue
        ol_count = _ol_item_count(sec)
        if ol_count >= min_items:
            start = sec.get("start", 0)
            line = text[:start].count("\n") + 1 if text else 1
            heading = (sec.get("heading") or "this section").strip()
            issues.append({
                "path": path,
                "line": line,
                "column": 1,
                "message": (
                    f"Concept section '{heading}' contains {ol_count} ordered steps "
                    "— procedural content belongs in a How-To section."
                ),
                "severity": "warning",
                "check": "Concept.ProcedureLeak",
            })

    return issues
