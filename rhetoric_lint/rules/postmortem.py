"""Postmortem / incident report checks for rhetor-linter.

Active only when genre == "postmortem" (GENRE_GATE_ENABLED = True), but
self-qualifies via heading constellation when the gate is off.

Checks
------
Postmortem.MissingRootCause
    Postmortem has no Root Cause or Contributing Factors section.
Postmortem.MissingActionItems
    Postmortem has no Action Items or Corrective Actions section.
Postmortem.OpenActionItem
    An action item line has no owner (@mention or [Owner:]) and no date.
Postmortem.MissingTimeline
    Postmortem has no Timeline section.
"""

import re
from typing import Any, Dict, List

GENRES = frozenset({"postmortem"})

_ROOT_CAUSE_HEADINGS = frozenset({
    "root cause", "root cause analysis", "contributing factors",
    "cause", "causes", "why did this happen",
})
_ACTION_ITEM_HEADINGS = frozenset({
    "action items", "corrective actions", "follow-up actions",
    "remediation", "action plan", "next steps", "follow-up",
})
_TIMELINE_HEADINGS = frozenset({
    "timeline", "incident timeline", "chronology", "sequence of events",
})
_ALL_POSTMORTEM_HEADINGS = (
    _ROOT_CAUSE_HEADINGS | _ACTION_ITEM_HEADINGS | _TIMELINE_HEADINGS
    | frozenset({
        "impact", "severity", "affected systems", "summary",
        "incident summary", "lessons learned", "what went well",
        "what went wrong", "detection", "resolution", "overview",
    })
)

# Owner detection: @mention, [Owner: Name], or "Owner: Name" label
_OWNER_RE = re.compile(
    r"@\w+"                       # @mention
    r"|\[Owner:\s*[^\]]+\]"       # [Owner: Name]
    r"|Owner:\s*\w",              # Owner: Name
    re.I,
)
# Date detection: ISO dates, "YYYY-MM-DD", "Mon DD", "Q1 YYYY", sprint refs
_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"             # 2024-01-15
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\b"  # Jan 15
    r"|\bQ[1-4]\s+\d{4}\b"               # Q1 2024
    r"|\bSprint\s+\d+\b",                # Sprint 12
    re.I,
)


def _h(sec: Dict[str, Any]) -> str:
    return (sec.get("heading") or "").strip().lower()


def _is_postmortem(sections: List[Dict[str, Any]]) -> bool:
    """Self-qualify: ≥3 postmortem-distinctive headings."""
    return sum(1 for s in sections if _h(s) in _ALL_POSTMORTEM_HEADINGS) >= 3


def _section_lines(sec: Dict[str, Any]) -> List[str]:
    lines = []
    for para in sec.get("paragraphs", []):
        text = (para.get("text") or "").strip()
        if text:
            lines.extend(text.splitlines())
    return lines


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context.get("path", "")
    text = context.get("text", "")
    sections = context.get("sections") or []
    issues: List[Dict[str, Any]] = []

    if not _is_postmortem(sections):
        return issues

    has_root_cause = any(_h(s) in _ROOT_CAUSE_HEADINGS for s in sections)
    has_action_items = any(_h(s) in _ACTION_ITEM_HEADINGS for s in sections)
    has_timeline = any(_h(s) in _TIMELINE_HEADINGS for s in sections)

    if not has_root_cause:
        issues.append({
            "path": path,
            "line": 1,
            "column": 1,
            "message": (
                "Postmortem is missing a Root Cause or Contributing Factors section."
            ),
            "severity": "error",
            "check": "Postmortem.MissingRootCause",
        })

    if not has_action_items:
        issues.append({
            "path": path,
            "line": 1,
            "column": 1,
            "message": (
                "Postmortem is missing an Action Items or Corrective Actions section."
            ),
            "severity": "error",
            "check": "Postmortem.MissingActionItems",
        })

    if not has_timeline:
        issues.append({
            "path": path,
            "line": 1,
            "column": 1,
            "message": "Postmortem is missing a Timeline section.",
            "severity": "warning",
            "check": "Postmortem.MissingTimeline",
        })

    # OpenActionItem: scan action item section paragraphs for unowned lines
    for sec in sections:
        if _h(sec) not in _ACTION_ITEM_HEADINGS:
            continue
        for para in sec.get("paragraphs", []):
            para_text = para.get("text") or ""
            para_line = para.get("line", 1)
            for i, line in enumerate(para_text.splitlines()):
                stripped = line.strip()
                # Only check non-empty list-item-style lines
                if not stripped or not (
                    stripped.startswith("-")
                    or stripped.startswith("*")
                    or re.match(r"^\d+\.", stripped)
                ):
                    continue
                if not _OWNER_RE.search(stripped) and not _DATE_RE.search(stripped):
                    issues.append({
                        "path": path,
                        "line": para_line + i,
                        "column": 1,
                        "message": (
                            "Action item has no assigned owner and no due date: "
                            f"'{stripped[:80]}'"
                        ),
                        "severity": "warning",
                        "check": "Postmortem.OpenActionItem",
                    })

    return issues
