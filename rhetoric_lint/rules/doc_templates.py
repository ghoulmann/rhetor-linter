"""Platform and product documentation template checks for rhetor-linter.

Each template is a prescribed section structure. Rules enforce section
presence (heading keyword detection) and structural anti-patterns (AST
node type checks). All rules self-qualify via doc_template value.

Templates and their checks
--------------------------
ProductOverview.MissingOverview / MissingCapabilities / MissingUseCases
ProductOverview.ProcedureLeak

Architecture.MissingOverview / MissingTechnicalDesign
Architecture.ProcedureLeak

UseCases.MissingOverview
UseCases.MultipleUseCasesInSection

Onboarding.MissingOverview / MissingRequirements / MissingSteps

QuickStart.MissingOverview / MissingPrerequisites / MissingCoreTask
QuickStart.MissingVerification / MissingNextSteps

PlatformOnboarding.MissingOverview / MissingPrerequisites / MissingEnvSetup
PlatformOnboarding.MissingAuth / MissingWorkflow / MissingVerification
PlatformOnboarding.MissingKeyConcepts / MissingNextSteps / MissingTroubleshooting
"""

from typing import Any, Dict, List

GENRES = frozenset({"all"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _h(sec: Dict[str, Any]) -> str:
    return (sec.get("heading") or "").strip().lower()


def _has_heading(sections, *keyword_sets):
    """Return True if any section heading matches any keyword in any set."""
    for sec in sections:
        h = _h(sec)
        for kws in keyword_sets:
            if any(kw in h for kw in kws):
                return True
    return False


def _ol_count(sections) -> int:
    """Count total ordered-list items across all sections."""
    count = 0
    for sec in sections:
        for para in sec.get("paragraphs", []):
            for node in para.get("nodes", []):
                if node.get("type") == "ListItem" and node.get("list_type") == "ol":
                    count += 1
    return count


def _sec_line(sec: Dict[str, Any], text: str) -> int:
    start = sec.get("start", 0)
    return text[:start].count("\n") + 1 if text else 1


def _issue(path, line, message, check, severity="warning"):
    return {
        "path": path,
        "line": line,
        "column": 1,
        "message": message,
        "severity": severity,
        "check": check,
    }


# ---------------------------------------------------------------------------
# Heading keyword sets per required section
# ---------------------------------------------------------------------------

_OVERVIEW_KWS = ("overview", "introduction", "about", "what is", "summary")
_CAPABILITIES_KWS = ("capabilities", "features", "what you can", "what it does")
_USE_CASE_KWS = ("use case", "use cases", "scenarios", "scenario")
_TECH_DESIGN_KWS = ("components", "technical design", "architecture", "design",
                    "system design", "how it works", "internals")
_PREREQ_KWS = ("prerequisites", "requirements", "before you begin",
               "what you need", "dependencies")
_STEPS_KWS = ("steps", "procedure", "how to", "how-to", "install",
              "configure", "set up", "setup", "onboard")
_AUTH_KWS = ("authentication", "auth", "authenticate", "log in", "login",
             "credentials", "api key", "access token")
_ENV_KWS = ("environment", "env", "set up", "setup", "install", "prerequisites")
_WORKFLOW_KWS = ("workflow", "run", "execute", "first request", "example",
                 "core task", "your first", "try it")
_VERIFY_KWS = ("verify", "verification", "confirm", "validate",
               "test your setup", "check your setup")
_NEXT_KWS = ("next steps", "what's next", "whats next", "further reading",
             "learn more", "where to go")
_KEY_CONCEPTS_KWS = ("key concepts", "core concepts", "concepts",
                     "terminology", "glossary")
_TROUBLESHOOTING_KWS = ("troubleshooting", "troubleshoot", "common issues",
                        "debugging", "errors", "problems")


# ---------------------------------------------------------------------------
# Per-template check functions
# ---------------------------------------------------------------------------

def _check_product_overview(path, sections, text) -> List[Dict[str, Any]]:
    issues = []

    if not _has_heading(sections, _OVERVIEW_KWS):
        issues.append(_issue(path, 1, "Product Overview is missing an Overview or Introduction section.",
                             "ProductOverview.MissingOverview"))
    if not _has_heading(sections, _CAPABILITIES_KWS):
        issues.append(_issue(path, 1, "Product Overview is missing a Capabilities or Features section.",
                             "ProductOverview.MissingCapabilities"))
    if not _has_heading(sections, _USE_CASE_KWS):
        issues.append(_issue(path, 1, "Product Overview is missing a Use Cases section.",
                             "ProductOverview.MissingUseCases", severity="suggestion"))

    # ProcedureLeak: ordered procedural list in a Product Overview
    for sec in sections:
        if sec.get("topic_type") == "howto":
            line = _sec_line(sec, text)
            heading = (sec.get("heading") or "this section").strip()
            issues.append(_issue(
                path, line,
                f"Product Overview section '{heading}' contains procedural steps "
                "— link to a How-To or Quick Start instead.",
                "ProductOverview.ProcedureLeak",
            ))

    return issues


def _check_architecture(path, sections, text) -> List[Dict[str, Any]]:
    issues = []

    if not _has_heading(sections, _OVERVIEW_KWS):
        issues.append(_issue(path, 1, "Architecture doc is missing an Overview section.",
                             "Architecture.MissingOverview"))
    if not _has_heading(sections, _TECH_DESIGN_KWS):
        issues.append(_issue(path, 1,
                             "Architecture doc is missing a Components or Technical Design section.",
                             "Architecture.MissingTechnicalDesign"))

    # ProcedureLeak: How-To sections in an Architecture doc
    for sec in sections:
        if sec.get("topic_type") == "howto":
            line = _sec_line(sec, text)
            heading = (sec.get("heading") or "this section").strip()
            issues.append(_issue(
                path, line,
                f"Architecture section '{heading}' contains procedural steps "
                "— Architecture docs should be Concept type throughout.",
                "Architecture.ProcedureLeak",
            ))

    return issues


def _check_use_cases(path, sections, text) -> List[Dict[str, Any]]:
    issues = []

    if not _has_heading(sections, _OVERVIEW_KWS):
        issues.append(_issue(path, 1, "Use Cases doc is missing an Overview section.",
                             "UseCases.MissingOverview"))

    # MultipleUseCasesInSection: a section has ≥2 child H3 sections that look like use cases
    for i, sec in enumerate(sections):
        if sec.get("level", 0) != 2:
            continue
        child_uc_count = sum(
            1 for s in sections[i + 1:]
            if s.get("level", 0) == 3
            and any(kw in _h(s) for kw in ("scenario", "use case", "example", "case"))
        )
        # Stop when we hit another H2
        child_h2_idx = next(
            (j for j, s in enumerate(sections[i + 1:], i + 1)
             if s.get("level", 0) == 2),
            len(sections),
        )
        child_uc_count = sum(
            1 for s in sections[i + 1:child_h2_idx]
            if s.get("level", 0) == 3
            and any(kw in _h(s) for kw in ("scenario", "use case", "example", "case"))
        )
        if child_uc_count >= 2:
            line = _sec_line(sec, text)
            heading = (sec.get("heading") or "this section").strip()
            issues.append(_issue(
                path, line,
                f"Use Cases section '{heading}' contains {child_uc_count} sub-use-cases "
                "— each use case should be its own top-level section.",
                "UseCases.MultipleUseCasesInSection",
                severity="suggestion",
            ))

    return issues


def _check_onboarding(path, sections, text) -> List[Dict[str, Any]]:
    issues = []

    if not _has_heading(sections, _OVERVIEW_KWS):
        issues.append(_issue(path, 1, "Onboarding doc is missing an Overview section.",
                             "Onboarding.MissingOverview"))
    if not _has_heading(sections, _PREREQ_KWS):
        issues.append(_issue(path, 1,
                             "Onboarding doc is missing a Requirements or Prerequisites section.",
                             "Onboarding.MissingRequirements"))
    if not _has_heading(sections, _STEPS_KWS):
        issues.append(_issue(path, 1,
                             "Onboarding doc is missing a steps or How-To section.",
                             "Onboarding.MissingSteps", severity="error"))

    return issues


def _check_quick_start(path, sections, text) -> List[Dict[str, Any]]:
    issues = []

    if not _has_heading(sections, _OVERVIEW_KWS):
        issues.append(_issue(path, 1, "Quick Start is missing an Overview or Introduction section.",
                             "QuickStart.MissingOverview"))
    if not _has_heading(sections, _PREREQ_KWS):
        issues.append(_issue(path, 1, "Quick Start is missing a Prerequisites section.",
                             "QuickStart.MissingPrerequisites"))
    if not any(s.get("topic_type") == "howto" for s in sections):
        issues.append(_issue(path, 1,
                             "Quick Start is missing a core task section (How-To).",
                             "QuickStart.MissingCoreTask", severity="error"))
    if not _has_heading(sections, _VERIFY_KWS):
        issues.append(_issue(path, 1,
                             "Quick Start is missing a Verify or Confirm step "
                             "— readers need confirmation that setup succeeded.",
                             "QuickStart.MissingVerification"))
    if not _has_heading(sections, _NEXT_KWS):
        issues.append(_issue(path, 1, "Quick Start is missing a Next Steps section.",
                             "QuickStart.MissingNextSteps", severity="suggestion"))

    return issues


def _check_platform_onboarding(path, sections, text) -> List[Dict[str, Any]]:
    issues = []

    if not _has_heading(sections, _OVERVIEW_KWS):
        issues.append(_issue(path, 1, "Platform Onboarding is missing an Overview section.",
                             "PlatformOnboarding.MissingOverview"))
    if not _has_heading(sections, _PREREQ_KWS):
        issues.append(_issue(path, 1,
                             "Platform Onboarding is missing a Prerequisites section.",
                             "PlatformOnboarding.MissingPrerequisites"))
    if not _has_heading(sections, _ENV_KWS):
        issues.append(_issue(path, 1,
                             "Platform Onboarding is missing an Environment Setup section.",
                             "PlatformOnboarding.MissingEnvSetup"))
    if not _has_heading(sections, _AUTH_KWS):
        issues.append(_issue(path, 1,
                             "Platform Onboarding is missing an Authentication section.",
                             "PlatformOnboarding.MissingAuth"))
    if not _has_heading(sections, _WORKFLOW_KWS):
        issues.append(_issue(path, 1,
                             "Platform Onboarding is missing a Workflow or core task section.",
                             "PlatformOnboarding.MissingWorkflow"))
    if not _has_heading(sections, _VERIFY_KWS):
        issues.append(_issue(path, 1,
                             "Platform Onboarding is missing a Verify step.",
                             "PlatformOnboarding.MissingVerification"))
    if not _has_heading(sections, _KEY_CONCEPTS_KWS):
        issues.append(_issue(path, 1,
                             "Platform Onboarding is missing a Key Concepts section.",
                             "PlatformOnboarding.MissingKeyConcepts"))
    if not _has_heading(sections, _NEXT_KWS):
        issues.append(_issue(path, 1,
                             "Platform Onboarding is missing a Next Steps section.",
                             "PlatformOnboarding.MissingNextSteps", severity="suggestion"))
    if not _has_heading(sections, _TROUBLESHOOTING_KWS):
        issues.append(_issue(path, 1,
                             "Platform Onboarding is missing a Troubleshooting section.",
                             "PlatformOnboarding.MissingTroubleshooting"))

    return issues


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_TEMPLATE_CHECKS = {
    "product_overview":     _check_product_overview,
    "architecture":         _check_architecture,
    "use_cases":            _check_use_cases,
    "onboarding":           _check_onboarding,
    "quick_start":          _check_quick_start,
    "platform_onboarding":  _check_platform_onboarding,
}


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    doc_template = context.get("doc_template", "general")
    check_fn = _TEMPLATE_CHECKS.get(doc_template)
    if check_fn is None:
        return []
    path = context.get("path", "")
    sections = context.get("sections") or []
    text = context.get("text", "")
    return check_fn(path, sections, text)
