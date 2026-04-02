"""Curriculum-specific checks for rhetor-linter.

Active only when genre == "curriculum" (GENRE_GATE_ENABLED = True).

Checks
------
Curriculum.MissingAssessment
    A numbered module/unit/week section contains no assessment item —
    no mention of assignment, quiz, exam, project, essay, graded
    activity, or similar.
"""

import re
from typing import Any, Dict, List

GENRES = frozenset({"curriculum"})

# Headings that indicate a content module (week, unit, module, session, lesson)
_MODULE_HEADING_RE = re.compile(
    r"^(\d+[\.\)]\s|\bweek\b|\bunit\b|\bmodule\b|\bsession\b|\blesson\b)",
    re.I,
)

# Keywords that indicate an assessment component within section text
_ASSESSMENT_KEYWORDS = frozenset({
    "assignment",
    "assignments",
    "quiz",
    "quizzes",
    "exam",
    "exams",
    "examination",
    "test",
    "tests",
    "graded",
    "grade",
    "grades",
    "project",
    "projects",
    "essay",
    "essays",
    "portfolio",
    "portfolios",
    "reflection",
    "reflections",
    "exercise",
    "exercises",
    "homework",
    "due",
    "submit",
    "submission",
    "assess",
    "assessment",
    "rubric",
})


def _section_has_assessment(sec: Dict[str, Any]) -> bool:
    """Return True if any paragraph or heading in *sec* mentions assessment."""
    # check section heading itself
    h = (sec.get("heading") or "").lower()
    if any(kw in h for kw in _ASSESSMENT_KEYWORDS):
        return True
    for para in sec.get("paragraphs", []):
        text = (para.get("text") or "").lower()
        for kw in _ASSESSMENT_KEYWORDS:
            if kw in text:
                return True
    return False


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Curriculum checks."""
    path = context.get("path", "")
    text = context.get("text", "")
    issues: List[Dict[str, Any]] = []

    sections = context.get("sections") or []

    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        if not heading:
            continue

        if not _MODULE_HEADING_RE.match(heading):
            continue

        if _section_has_assessment(sec):
            continue

        # no assessment found in this module section
        start = sec.get("start", 0)
        line = text[:start].count("\n") + 1 if text else 1

        issues.append({
            "path": path,
            "line": line,
            "message": (
                f"Curriculum gap: section '{heading}' appears to be a content module "
                "but contains no assessment item (assignment, quiz, exam, project, etc.)"
            ),
            "severity": "suggestion",
            "check": "Curriculum.MissingAssessment",
        })

    return issues
