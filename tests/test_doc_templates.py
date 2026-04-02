"""Tests for template_type classifier and doc_templates rule."""
from rhetoric_lint.template_type import classify_doc_template
from rhetoric_lint.rules.doc_templates import check


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sec(heading, level=2, topic_type="general", ol_items=None, body="", start=0):
    nodes = []
    if ol_items:
        nodes = [{"type": "ListItem", "list_type": "ol", "text": t} for t in ol_items]
    paras = []
    if body or nodes:
        paras = [{"text": body, "pos": 0, "end": 50, "line": 2,
                  "doc": None, "sentences": [], "nodes": nodes}]
    return {"heading": heading, "level": level, "topic_type": topic_type,
            "paragraphs": paras, "start": start, "end": start + 100}


def _ctx(sections, doc_template, text=""):
    return {
        "path": "test.md",
        "text": text,
        "sections": sections,
        "doc_template": doc_template,
    }


# ---------------------------------------------------------------------------
# Template classifier tests
# ---------------------------------------------------------------------------

class TestTemplateClassifier:
    def test_platform_onboarding_by_title(self):
        secs = [_sec("Platform Onboarding Guide", level=1)]
        assert classify_doc_template(secs, "") == "platform_onboarding"

    def test_platform_onboarding_by_structure(self):
        secs = [
            _sec("Overview", level=1, topic_type="concept"),
            _sec("Key Concepts", topic_type="concept"),
            _sec("Troubleshooting", topic_type="troubleshooting"),
            _sec("Install", topic_type="howto"),
            _sec("Configure", topic_type="howto"),
            _sec("Run", topic_type="howto"),
        ]
        assert classify_doc_template(secs, "") == "platform_onboarding"

    def test_quick_start_by_title_and_structure(self):
        secs = [
            _sec("Quick Start", level=1, topic_type="concept"),
            _sec("Prerequisites", topic_type="reference"),
            _sec("Install", topic_type="howto"),
            _sec("Run", topic_type="howto"),
            _sec("Verify", topic_type="howto"),
            _sec("Next Steps"),
        ]
        assert classify_doc_template(secs, "") == "quick_start"

    def test_onboarding_by_title_and_prereqs(self):
        secs = [
            _sec("Getting Started", level=1, topic_type="concept"),
            _sec("Prerequisites", topic_type="reference"),
            _sec("Install", topic_type="howto"),
        ]
        assert classify_doc_template(secs, "") == "onboarding"

    def test_architecture_by_headings(self):
        secs = [
            _sec("System Architecture", level=1, topic_type="concept"),
            _sec("Components", topic_type="concept"),
            _sec("Data Flow", topic_type="concept"),
        ]
        assert classify_doc_template(secs, "") == "architecture"

    def test_use_cases_by_title(self):
        secs = [
            _sec("Use Cases", level=1, topic_type="concept"),
            _sec("Batch Processing", topic_type="general"),
            _sec("Real-Time Analytics", topic_type="general"),
        ]
        assert classify_doc_template(secs, "") == "use_cases"

    def test_product_overview_by_title_and_structure(self):
        secs = [
            _sec("Product Overview", level=1, topic_type="concept"),
            _sec("Features", topic_type="concept"),
        ]
        assert classify_doc_template(secs, "") == "product_overview"

    def test_general_fallback(self):
        secs = [_sec("Changelog", level=1)]
        assert classify_doc_template(secs, "") == "general"

    def test_no_rules_for_general(self):
        ctx = _ctx([_sec("Changelog", level=1)], "general")
        assert check(ctx) == []


# ---------------------------------------------------------------------------
# Product Overview
# ---------------------------------------------------------------------------

class TestProductOverview:
    def _secs_complete(self):
        return [
            _sec("Overview", topic_type="concept"),
            _sec("Capabilities", topic_type="concept"),
            _sec("Use Cases", topic_type="concept"),
        ]

    def test_complete_no_issues(self):
        ctx = _ctx(self._secs_complete(), "product_overview")
        assert check(ctx) == []

    def test_missing_overview(self):
        ctx = _ctx([_sec("Capabilities", topic_type="concept"),
                    _sec("Use Cases", topic_type="concept")], "product_overview")
        checks = [i["check"] for i in check(ctx)]
        assert "ProductOverview.MissingOverview" in checks

    def test_missing_capabilities(self):
        ctx = _ctx([_sec("Overview", topic_type="concept"),
                    _sec("Use Cases", topic_type="concept")], "product_overview")
        checks = [i["check"] for i in check(ctx)]
        assert "ProductOverview.MissingCapabilities" in checks

    def test_procedure_leak(self):
        secs = self._secs_complete() + [_sec("Installing", topic_type="howto")]
        ctx = _ctx(secs, "product_overview")
        checks = [i["check"] for i in check(ctx)]
        assert "ProductOverview.ProcedureLeak" in checks


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------

class TestArchitecture:
    def test_complete_no_issues(self):
        ctx = _ctx([
            _sec("Overview", topic_type="concept"),
            _sec("Components", topic_type="concept"),
        ], "architecture")
        assert check(ctx) == []

    def test_missing_overview(self):
        ctx = _ctx([_sec("Components", topic_type="concept")], "architecture")
        checks = [i["check"] for i in check(ctx)]
        assert "Architecture.MissingOverview" in checks

    def test_missing_technical_design(self):
        ctx = _ctx([_sec("Overview", topic_type="concept")], "architecture")
        checks = [i["check"] for i in check(ctx)]
        assert "Architecture.MissingTechnicalDesign" in checks

    def test_procedure_leak(self):
        ctx = _ctx([
            _sec("Overview", topic_type="concept"),
            _sec("Components", topic_type="concept"),
            _sec("Deploying", topic_type="howto"),
        ], "architecture")
        checks = [i["check"] for i in check(ctx)]
        assert "Architecture.ProcedureLeak" in checks


# ---------------------------------------------------------------------------
# Use Cases
# ---------------------------------------------------------------------------

class TestUseCases:
    def test_complete_no_issues(self):
        ctx = _ctx([
            _sec("Overview", topic_type="concept"),
            _sec("Batch Processing", topic_type="general"),
        ], "use_cases")
        assert check(ctx) == []

    def test_missing_overview(self):
        ctx = _ctx([_sec("Batch Processing", topic_type="general")], "use_cases")
        checks = [i["check"] for i in check(ctx)]
        assert "UseCases.MissingOverview" in checks

    def test_multiple_use_cases_in_section(self):
        secs = [
            _sec("Overview", level=2, topic_type="concept"),
            _sec("Batch Processing Use Case", level=2),
            _sec("Example scenario", level=3),
            _sec("Another scenario", level=3),
        ]
        ctx = _ctx(secs, "use_cases")
        checks = [i["check"] for i in check(ctx)]
        assert "UseCases.MultipleUseCasesInSection" in checks


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

class TestOnboarding:
    def test_complete_no_issues(self):
        ctx = _ctx([
            _sec("Overview", topic_type="concept"),
            _sec("Requirements", topic_type="reference"),
            _sec("How to Install", topic_type="howto"),
        ], "onboarding")
        assert check(ctx) == []

    def test_missing_requirements(self):
        ctx = _ctx([
            _sec("Overview", topic_type="concept"),
            _sec("How to Install", topic_type="howto"),
        ], "onboarding")
        checks = [i["check"] for i in check(ctx)]
        assert "Onboarding.MissingRequirements" in checks

    def test_missing_steps_is_error(self):
        ctx = _ctx([
            _sec("Overview", topic_type="concept"),
            _sec("Requirements", topic_type="reference"),
        ], "onboarding")
        issues = check(ctx)
        step_issue = next((i for i in issues if i["check"] == "Onboarding.MissingSteps"), None)
        assert step_issue is not None
        assert step_issue["severity"] == "error"


# ---------------------------------------------------------------------------
# Quick Start
# ---------------------------------------------------------------------------

class TestQuickStart:
    def _complete_secs(self):
        return [
            _sec("Overview", topic_type="concept"),
            _sec("Prerequisites", topic_type="reference"),
            _sec("Install", topic_type="howto"),
            _sec("Verify"),
            _sec("Next Steps"),
        ]

    def test_complete_no_issues(self):
        ctx = _ctx(self._complete_secs(), "quick_start")
        assert check(ctx) == []

    def test_missing_verification(self):
        secs = [
            _sec("Overview", topic_type="concept"),
            _sec("Prerequisites", topic_type="reference"),
            _sec("Install", topic_type="howto"),
            _sec("Next Steps"),
        ]
        ctx = _ctx(secs, "quick_start")
        checks = [i["check"] for i in check(ctx)]
        assert "QuickStart.MissingVerification" in checks

    def test_missing_core_task_is_error(self):
        ctx = _ctx([
            _sec("Overview", topic_type="concept"),
            _sec("Prerequisites", topic_type="reference"),
            _sec("Verify"),
        ], "quick_start")
        issues = check(ctx)
        ct = next((i for i in issues if i["check"] == "QuickStart.MissingCoreTask"), None)
        assert ct is not None
        assert ct["severity"] == "error"


# ---------------------------------------------------------------------------
# Platform Onboarding
# ---------------------------------------------------------------------------

class TestPlatformOnboarding:
    def _complete_secs(self):
        return [
            _sec("Overview", topic_type="concept"),
            _sec("Prerequisites", topic_type="reference"),
            _sec("Set Up Environment", topic_type="howto"),
            _sec("Authentication", topic_type="howto"),
            _sec("Run Your First Workflow", topic_type="howto"),
            _sec("Verify", topic_type="howto"),
            _sec("Key Concepts", topic_type="concept"),
            _sec("Next Steps"),
            _sec("Troubleshooting", topic_type="troubleshooting"),
        ]

    def test_complete_no_issues(self):
        ctx = _ctx(self._complete_secs(), "platform_onboarding")
        assert check(ctx) == []

    def test_missing_auth(self):
        secs = [s for s in self._complete_secs()
                if "auth" not in (s.get("heading") or "").lower()]
        ctx = _ctx(secs, "platform_onboarding")
        checks = [i["check"] for i in check(ctx)]
        assert "PlatformOnboarding.MissingAuth" in checks

    def test_missing_key_concepts(self):
        secs = [s for s in self._complete_secs()
                if "concept" not in (s.get("heading") or "").lower()]
        ctx = _ctx(secs, "platform_onboarding")
        checks = [i["check"] for i in check(ctx)]
        assert "PlatformOnboarding.MissingKeyConcepts" in checks

    def test_missing_troubleshooting(self):
        secs = [s for s in self._complete_secs()
                if s.get("topic_type") != "troubleshooting"]
        ctx = _ctx(secs, "platform_onboarding")
        checks = [i["check"] for i in check(ctx)]
        assert "PlatformOnboarding.MissingTroubleshooting" in checks
