"""Section-level topic type classifier for rhetor-linter.

Classifies each section into one of:
  concept        — high-level orientation: what something is and how it helps
  tutorial       — learning-oriented experience under tutor guidance (Diataxis)
  howto          — goal-oriented directions assuming baseline competence (Diataxis)
  troubleshooting — reactive resolution guidance: symptom → cause → fix
  faq            — self-contained Q&A pairs for lookup
  reference      — technical descriptions of the machinery (Diataxis)
  explanation    — discursive treatment permitting reflection (Diataxis)
  general        — fallback when no type is identified

Usage
-----
  topic_type = classify_section_topic(section, const=None)
"""

import re
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Heading keyword sets — primary classification signal
# ---------------------------------------------------------------------------

_CONCEPT_HEADINGS = frozenset({
    "overview", "introduction", "about", "concepts", "concept",
    "what is", "understanding", "background", "key concepts",
    "core concepts", "how it works", "capabilities", "features",
    "product overview", "architecture overview",
})

_TUTORIAL_HEADINGS = frozenset({
    "tutorial", "tutorials", "getting started tutorial",
    "learn", "learning", "guided tour", "walkthrough",
})

_HOWTO_HEADINGS = frozenset({
    "how to", "how-to", "installing", "installation",
    "configuring", "configuration", "setting up", "setup",
    "deploying", "deployment", "creating", "building",
    "enabling", "disabling", "migrating", "upgrading",
    "integrating", "connecting", "authenticating",
})

_TROUBLESHOOTING_HEADINGS = frozenset({
    "troubleshooting", "troubleshoot", "common issues", "common problems",
    "known issues", "errors", "error handling", "debugging", "diagnose",
    "fixing", "resolving", "solutions", "workarounds",
})

_FAQ_HEADINGS = frozenset({
    "faq", "faqs", "frequently asked questions", "common questions",
    "questions and answers", "q&a", "questions",
})

_REFERENCE_HEADINGS = frozenset({
    "reference", "api reference", "api", "specification", "spec",
    "schema", "parameters", "options", "flags", "configuration reference",
    "environment variables", "cli reference", "endpoints",
    "data types", "types", "glossary",
})

_EXPLANATION_HEADINGS = frozenset({
    "explanation", "why", "rationale", "design rationale",
    "design decisions", "architecture decisions", "background",
    "motivation", "theory", "deep dive", "internals",
    "how it works", "under the hood",
})

# Error code pattern in section body → troubleshooting signal
_ERROR_CODE_RE = re.compile(
    r"\b(?:error|exception|errno|exit code|http\s*[45]\d{2})\b"
    r"|\bE[A-Z]{2,}\b"       # errno-style: ENOENT, EACCES
    r"|\b[45]\d{2}\b",       # HTTP 4xx/5xx bare
    re.I,
)

# Tutorial cues: first-person plural
_TUTORIAL_WE_RE = re.compile(r"\b(we|let's|let us)\b", re.I)

# Heading ends with "?" → FAQ entry
_QUESTION_HEADING_RE = re.compile(r"\?\s*$")


def _h(section: Dict[str, Any]) -> str:
    return (section.get("heading") or "").strip().lower()


def _body_text(section: Dict[str, Any]) -> str:
    parts = []
    for para in section.get("paragraphs", []):
        t = (para.get("text") or "").strip()
        if t:
            parts.append(t)
    return " ".join(parts)


def _has_ordered_list(section: Dict[str, Any]) -> bool:
    for para in section.get("paragraphs", []):
        for node in para.get("nodes", []):
            if node.get("type") == "ListItem" and node.get("list_type") == "ol":
                return True
    return False


def classify_section_topic(
    section: Dict[str, Any],
    const: Optional[Any] = None,
) -> str:
    """Return the topic type string for *section*.

    Classification order: most distinctive signals first.
    """
    heading = _h(section)
    body = _body_text(section)

    # 1. FAQ — heading is "faq*" OR heading ends with "?"
    if heading in _FAQ_HEADINGS or _QUESTION_HEADING_RE.search(heading):
        return "faq"

    # 2. Troubleshooting — heading keyword OR error codes in body
    if heading in _TROUBLESHOOTING_HEADINGS or (
        heading and _ERROR_CODE_RE.search(body)
        and any(kw in heading for kw in ("error", "issue", "problem", "fix", "debug"))
    ):
        return "troubleshooting"

    # 3. Reference — heading keyword (distinctive names)
    if heading in _REFERENCE_HEADINGS:
        return "reference"

    # 4. Explanation — heading keyword
    if heading in _EXPLANATION_HEADINGS and heading not in _CONCEPT_HEADINGS:
        return "explanation"

    # 5. How-To — heading starts with or contains imperative action phrase
    if heading in _HOWTO_HEADINGS or any(
        heading.startswith(kw) for kw in (
            "how to", "how-to", "install", "configure", "set up",
            "deploy", "create", "build", "enable", "disable",
            "migrate", "upgrade", "integrate", "connect", "auth",
        )
    ):
        return "howto"

    # 6. Tutorial — heading keyword OR first-person plural in body
    if heading in _TUTORIAL_HEADINGS or (
        heading and "tutorial" in heading
    ) or (
        body and _TUTORIAL_WE_RE.search(body[:200])
        and not _has_ordered_list(section)
    ):
        return "tutorial"

    # 7. Concept — heading keyword
    if heading in _CONCEPT_HEADINGS:
        return "concept"

    return "general"
