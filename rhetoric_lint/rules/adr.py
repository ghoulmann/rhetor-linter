"""ADR (Architecture Decision Record) checks for rhetor-linter.

Active only when genre == "adr" (GENRE_GATE_ENABLED = True), but
self-qualifies via Status: line + section headings when the gate is off.

Checks
------
ADR.MissingStatus
    ADR has no Status: field.
ADR.MissingDecision
    ADR has no Decision section.
ADR.UndecidedStatus
    Status is Proposed/Draft/Pending but Decision section has no body.
ADR.MissingConsequences
    ADR has no Consequences, Trade-offs, or Impact section.
"""

import re
from typing import Any, Dict, List

GENRES = frozenset({"adr"})

_STATUS_LINE_RE = re.compile(r"^Status:\s*\S", re.M | re.I)
_STATUS_OPEN_RE = re.compile(
    r"^Status:\s*(proposed|draft|pending|under[ -]review)", re.M | re.I
)

_DECISION_HEADINGS = frozenset({
    "decision", "decision outcome", "chosen option",
})
_CONTEXT_HEADINGS = frozenset({
    "context", "context and problem statement", "problem statement",
    "background",
})
_CONSEQUENCES_HEADINGS = frozenset({
    "consequences", "consequences / trade-offs", "trade-offs", "tradeoffs",
    "impact", "implications", "pros and cons",
    "positive consequences", "negative consequences",
})
_ALL_ADR_HEADINGS = (
    _DECISION_HEADINGS | _CONTEXT_HEADINGS | _CONSEQUENCES_HEADINGS
    | frozenset({"options considered", "considered options", "decision drivers"})
)


def _h(sec: Dict[str, Any]) -> str:
    return (sec.get("heading") or "").strip().lower()


def _section_is_empty(sec: Dict[str, Any]) -> bool:
    for para in sec.get("paragraphs", []):
        if len((para.get("text") or "").strip()) > 10:
            return False
    return True


def _is_adr(sections: List[Dict[str, Any]], text: str) -> bool:
    """Self-qualify: Status: line + ≥2 ADR headings, OR ≥3 ADR headings alone."""
    has_status = bool(_STATUS_LINE_RE.search(text))
    section_count = sum(1 for s in sections if _h(s) in _ALL_ADR_HEADINGS)
    return (has_status and section_count >= 2) or section_count >= 3


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context.get("path", "")
    text = context.get("text", "")
    sections = context.get("sections") or []
    issues: List[Dict[str, Any]] = []

    if not _is_adr(sections, text):
        return issues

    has_status = bool(_STATUS_LINE_RE.search(text))
    has_decision = any(_h(s) in _DECISION_HEADINGS for s in sections)
    has_consequences = any(_h(s) in _CONSEQUENCES_HEADINGS for s in sections)

    if not has_status:
        issues.append({
            "path": path,
            "line": 1,
            "column": 1,
            "message": "ADR is missing a Status: field (e.g. 'Status: Accepted').",
            "severity": "warning",
            "check": "ADR.MissingStatus",
        })

    if not has_decision:
        issues.append({
            "path": path,
            "line": 1,
            "column": 1,
            "message": "ADR is missing a Decision section.",
            "severity": "error",
            "check": "ADR.MissingDecision",
        })

    if has_status and has_decision and _STATUS_OPEN_RE.search(text):
        for sec in sections:
            if _h(sec) in _DECISION_HEADINGS:
                if _section_is_empty(sec):
                    start = sec.get("start", 0)
                    line = text[:start].count("\n") + 1 if text else 1
                    m = _STATUS_OPEN_RE.search(text)
                    status_val = m.group(1).title() if m else "Proposed"
                    issues.append({
                        "path": path,
                        "line": line,
                        "column": 1,
                        "message": (
                            f"ADR Status is '{status_val}' but Decision section "
                            "has no body; record the decision or update Status."
                        ),
                        "severity": "warning",
                        "check": "ADR.UndecidedStatus",
                    })
                break

    if not has_consequences:
        issues.append({
            "path": path,
            "line": 1,
            "column": 1,
            "message": (
                "ADR is missing a Consequences, Trade-offs, or Impact section."
            ),
            "severity": "warning",
            "check": "ADR.MissingConsequences",
        })

    return issues
