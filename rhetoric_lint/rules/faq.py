"""FAQ topic-type checks for rhetor-linter.

Checks
------
FAQ.EmptyAnswer
    A question heading (or Q: entry) has no substantive answer body.
FAQ.NonQuestionEntry
    A heading within an FAQ section is not phrased as a question.
"""

import re
from typing import Any, Dict, List

GENRES = frozenset({"all"})

_QUESTION_RE = re.compile(r"\?\s*$")
# Minimum characters for a substantive answer
_MIN_ANSWER_CHARS = 20

# FAQ parent heading keywords (section headings that introduce an FAQ block)
_FAQ_PARENT_HEADINGS = frozenset({
    "faq", "faqs", "frequently asked questions", "common questions",
    "questions and answers", "q&a", "questions",
})


def _h(sec: Dict[str, Any]) -> str:
    return (sec.get("heading") or "").strip().lower()


def _section_text_len(sec: Dict[str, Any]) -> int:
    total = 0
    for para in sec.get("paragraphs", []):
        total += len((para.get("text") or "").strip())
    return total


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context.get("path", "")
    text = context.get("text", "")
    sections = context.get("sections") or []
    issues: List[Dict[str, Any]] = []

    # Identify FAQ sections: either typed as "faq" by classifier, or
    # child sections whose parent is an FAQ heading.
    faq_parent_indices = {
        i for i, s in enumerate(sections)
        if _h(s) in _FAQ_PARENT_HEADINGS or s.get("topic_type") == "faq"
    }

    for i, sec in enumerate(sections):
        is_faq = (
            sec.get("topic_type") == "faq"
            or i in faq_parent_indices
            or any(
                j in faq_parent_indices and sections[j].get("level", 0) < sec.get("level", 0)
                for j in range(max(0, i - 5), i)
            )
        )
        if not is_faq:
            continue

        heading = (sec.get("heading") or "").strip()
        if not heading:
            continue

        start = sec.get("start", 0)
        line = text[:start].count("\n") + 1 if text else 1

        # FAQ.NonQuestionEntry — heading is not itself a question
        # (skip the parent FAQ heading — it labels the section, not a Q)
        if _h(sec) not in _FAQ_PARENT_HEADINGS and not _QUESTION_RE.search(heading):
            issues.append({
                "path": path,
                "line": line,
                "column": 1,
                "message": (
                    f"FAQ entry '{heading}' is not phrased as a question "
                    "(headings in FAQ sections should end with '?')."
                ),
                "severity": "suggestion",
                "check": "FAQ.NonQuestionEntry",
            })

        # FAQ.EmptyAnswer — question with no substantive answer
        if _QUESTION_RE.search(heading) and _section_text_len(sec) < _MIN_ANSWER_CHARS:
            issues.append({
                "path": path,
                "line": line,
                "column": 1,
                "message": (
                    f"FAQ entry '{heading}' has no substantive answer."
                ),
                "severity": "warning",
                "check": "FAQ.EmptyAnswer",
            })

    return issues
