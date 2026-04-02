"""Document template classifier for rhetor-linter.

Second-pass classifier that runs after genre detection and topic-type
classification. Identifies specific platform/product documentation templates
within the "technical" genre family.

Recognised templates
--------------------
  platform_onboarding — comprehensive setup: env + auth + workflow + key concepts + troubleshooting
  quick_start         — minimal path to first success: prereqs + steps + verify + next steps
  onboarding          — structured introduction: overview + requirements + how-to steps
  architecture        — technical design: all-concept sections, no procedures
  use_cases           — scenario catalogue: overview + one-use-case-per-section
  product_overview    — user-facing orientation: capabilities + use cases, no procedures
  general             — fallback

Usage
-----
  doc_template = classify_doc_template(sections, text, const=None)
"""

from typing import Any, Dict, List, Optional


def _h(sec: Dict[str, Any]) -> str:
    return (sec.get("heading") or "").strip().lower()


def _h1(sections: List[Dict[str, Any]]) -> str:
    for sec in sections:
        if sec.get("level") == 1 and sec.get("heading"):
            return sec["heading"].strip().lower()
    # Fall back to first heading of any level
    for sec in sections:
        if sec.get("heading"):
            return sec["heading"].strip().lower()
    return ""


def _heading_set(sections: List[Dict[str, Any]]):
    return {_h(s) for s in sections}


# ---------------------------------------------------------------------------
# Heading keyword groups
# ---------------------------------------------------------------------------

_KEY_CONCEPTS_HEADINGS = frozenset({
    "key concepts", "core concepts", "concepts", "terminology", "glossary",
})
_VERIFY_HEADINGS = frozenset({
    "verify", "verification", "confirm", "validate",
    "test your setup", "check your setup", "next steps",
})
_NEXT_STEPS_HEADINGS = frozenset({
    "next steps", "what's next", "whats next", "where to go next",
    "further reading", "learn more",
})
_PREREQ_HEADINGS = frozenset({
    "prerequisites", "requirements", "before you begin",
    "what you need", "dependencies", "prerequisite",
})
_ARCH_SIGNAL_WORDS = frozenset({
    "architecture", "components", "data flow", "system design",
    "infrastructure", "technical design", "internals", "design overview",
})


def classify_doc_template(
    sections: List[Dict[str, Any]],
    text: str,
    const: Optional[Any] = None,
) -> str:
    """Return the doc template string for the document."""
    h1 = _h1(sections)
    all_headings = _heading_set(sections)

    # Topic type counts (populated by classify_section_topic earlier)
    howto_count = sum(1 for s in sections if s.get("topic_type") == "howto")
    concept_count = sum(1 for s in sections if s.get("topic_type") == "concept")
    has_troubleshooting_sec = any(
        s.get("topic_type") == "troubleshooting" for s in sections
    )

    has_key_concepts = bool(all_headings & _KEY_CONCEPTS_HEADINGS)
    has_verify = bool(all_headings & _VERIFY_HEADINGS)
    has_next_steps = bool(all_headings & _NEXT_STEPS_HEADINGS)
    has_prereqs = bool(all_headings & _PREREQ_HEADINGS)

    platform_kws = ("platform onboarding", "platform setup", "platform guide",
                    "developer onboarding", "developer setup")
    qs_kws = ("quick start", "quickstart", "quickstart guide", "quick-start")
    onboard_kws = ("onboarding", "onboard", "getting started", "get started")
    arch_kws = ("architecture", "technical design", "system design",
                "components", "how it works")
    uc_kws = ("use cases", "use case", "scenarios", "scenario")
    overview_kws = ("overview", "introduction", "product overview",
                    "about", "what is")

    # 1. Platform Onboarding — comprehensive: key concepts + troubleshooting + procedures
    if any(kw in h1 for kw in platform_kws) or (
        has_key_concepts and has_troubleshooting_sec and howto_count >= 3
    ):
        return "platform_onboarding"

    # 2. Quick Start — tight path: title signal + verify/next-steps + ≥2 how-to
    if any(kw in h1 for kw in qs_kws) and (has_verify or has_next_steps) and howto_count >= 2:
        return "quick_start"

    # 3. Onboarding — structured intro: title signal + prerequisites
    if any(kw in h1 for kw in onboard_kws) and has_prereqs:
        return "onboarding"

    # 4. Architecture — arch keywords in headings, no How-To sections
    arch_heading_matches = sum(
        1 for h in all_headings
        if any(kw in h for kw in arch_kws)
    )
    if arch_heading_matches >= 1 and howto_count == 0 and concept_count >= 1:
        return "architecture"

    # 5. Use Cases — use-case keywords in H1 or in heading set
    if (
        any(kw in h1 for kw in uc_kws)
        or any(kw in all_headings for kw in ("use cases", "use case", "scenarios"))
    ):
        return "use_cases"

    # 6. Product Overview — overview keywords + no procedures + concept sections
    if (
        any(kw in h1 for kw in overview_kws)
        and howto_count == 0
        and concept_count >= 1
    ):
        return "product_overview"

    return "general"
