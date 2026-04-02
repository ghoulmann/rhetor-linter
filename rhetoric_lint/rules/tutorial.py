"""Tutorial topic-type checks for rhetor-linter.

Checks
------
Tutorial.NoObservationCues
    Tutorial section has no feedback mechanism ("notice that", "you should see", etc.).
Tutorial.AlternativesDiversion
    Tutorial section offers branching paths mid-way (Diataxis forbids alternatives
    in tutorials — there must be one path).
"""

import re
from typing import Any, Dict, List

GENRES = frozenset({"all"})

# Observation cue phrases
_OBSERVATION_CUES_RE = re.compile(
    r"\b(notice that|you should see|you will see|observe that|"
    r"you can see|the output (?:should|will)|expected output|"
    r"you should now|this confirms|verify that)\b",
    re.I,
)

# Alternative/branching signals at the start of an ordered list item
_ALTERNATIVES_RE = re.compile(
    r"^\s*(?:\d+[\.\)]\s+|[-*]\s+)?(?:or\b|alternatively\b|if you (?:prefer|want|chose|use)\b)",
    re.I,
)

# Minimum body length (chars) before checking for observation cues
_MIN_BODY_FOR_CHECK = 200


def _body_text(section: Dict[str, Any]) -> str:
    parts = []
    for para in section.get("paragraphs", []):
        t = (para.get("text") or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts)


def _ol_item_texts(section: Dict[str, Any]) -> List[str]:
    texts = []
    for para in section.get("paragraphs", []):
        for node in para.get("nodes", []):
            if node.get("type") == "ListItem" and node.get("list_type") == "ol":
                t = (node.get("text") or "").strip()
                if t:
                    texts.append(t)
    return texts


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context.get("path", "")
    text = context.get("text", "")
    sections = context.get("sections") or []
    issues: List[Dict[str, Any]] = []

    for sec in sections:
        if sec.get("topic_type") != "tutorial":
            continue

        start = sec.get("start", 0)
        line = text[:start].count("\n") + 1 if text else 1
        heading = (sec.get("heading") or "this section").strip()
        body = _body_text(sec)

        # NoObservationCues: only check sections with enough content
        if len(body) >= _MIN_BODY_FOR_CHECK and not _OBSERVATION_CUES_RE.search(body):
            issues.append({
                "path": path,
                "line": line,
                "column": 1,
                "message": (
                    f"Tutorial section '{heading}' has no observation cues "
                    "('notice that', 'you should see', etc.) — "
                    "tutorials require feedback mechanisms so learners can confirm progress."
                ),
                "severity": "suggestion",
                "check": "Tutorial.NoObservationCues",
            })

        # AlternativesDiversion: ordered list items starting with "or" / "alternatively"
        ol_items = _ol_item_texts(sec)
        # Check items after the first (first item can't be an alternative)
        for item in ol_items[1:]:
            if _ALTERNATIVES_RE.match(item):
                issues.append({
                    "path": path,
                    "line": line,
                    "column": 1,
                    "message": (
                        f"Tutorial section '{heading}' offers alternative paths "
                        f"('{item[:60]}') — tutorials must follow a single route."
                    ),
                    "severity": "warning",
                    "check": "Tutorial.AlternativesDiversion",
                })
                break  # one issue per section is enough

    return issues
