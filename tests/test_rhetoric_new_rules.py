"""Tests for Rhetoric.TrivializingLanguage (Vale YAML), Rhetoric.ModalAmbiguity, and
Cohesion.ForwardReference."""
import os
from contextlib import contextmanager
from pathlib import Path

import rhetoric_lint.const as _const
from rhetoric_lint.engine import RhetoricEngine

# Absolute path to style-sets/ (sibling of tests/)
_STYLE_SETS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "style-sets")
)


@contextmanager
def _rhetoric_style():
    """Temporarily configure the engine to load the Rhetoric style set."""
    orig_dirs = _const.STYLE_DIRS
    orig_styles = _const.ENABLED_STYLES
    _const.STYLE_DIRS = [_STYLE_SETS_DIR]
    _const.ENABLED_STYLES = ["Rhetoric"]
    try:
        yield
    finally:
        _const.STYLE_DIRS = orig_dirs
        _const.ENABLED_STYLES = orig_styles


def _run(text: str, tmp_path: Path):
    p = tmp_path / "test.md"
    p.write_text(text, encoding="utf-8")
    eng = RhetoricEngine()
    return eng.lint_files([str(p)])


def _run_with_rhetoric(text: str, tmp_path: Path):
    """Run engine with Rhetoric style set loaded (for SP6 Vale-based TrivializingLanguage)."""
    p = tmp_path / "test.md"
    p.write_text(text, encoding="utf-8")
    with _rhetoric_style():
        eng = RhetoricEngine()
        eng._init_runners()
    return eng.lint_files([str(p)])


# ---------------------------------------------------------------------------
# Rhetoric.TrivializingLanguage
# ---------------------------------------------------------------------------


def test_trivializing_simply(tmp_path):
    md = "# Installing the Package\n\nSimply run `pip install foo` to get started.\n"
    issues = _run_with_rhetoric(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert any("TrivializingLanguage" in c for c in checks)


def test_trivializing_obviously(tmp_path):
    md = "# Setup\n\nObviously you will need to configure the database first.\n"
    issues = _run_with_rhetoric(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert any("TrivializingLanguage" in c for c in checks)


def test_trivializing_of_course(tmp_path):
    md = "# Prerequisites\n\nOf course, you should have Python 3.10 or later installed.\n"
    issues = _run_with_rhetoric(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert any("TrivializingLanguage" in c for c in checks)


def test_trivializing_no_false_positive_temporal_just(tmp_path):
    md = "# Release Notes\n\nWe have just released version 2.0 with breaking changes.\n"
    issues = _run_with_rhetoric(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert not any("TrivializingLanguage" in c for c in checks)


def test_trivializing_no_false_positive_code_block(tmp_path):
    # "simply" inside a fenced code block should not trigger
    md = "# Setup\n\n```bash\n# simply install the package\npip install foo\n```\n"
    issues = _run_with_rhetoric(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert not any("TrivializingLanguage" in c for c in checks)


def test_trivializing_just_released(tmp_path):
    md = "# What Changed\n\nWe just released a new version.\n"
    issues = _run_with_rhetoric(md, tmp_path)
    trivializing = [i for i in issues if "TrivializingLanguage" in i["check"]]
    assert len(trivializing) == 0


# ---------------------------------------------------------------------------
# Rhetoric.ModalAmbiguity
# ---------------------------------------------------------------------------


def test_modal_ambiguity_mixed(tmp_path):
    md = (
        "# Deploy the Service\n\n"
        "1. You must configure the environment variables.\n"
        "2. You should restart the service.\n"
        "3. Run the health check.\n"
    )
    issues = _run(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert "Rhetoric.ModalAmbiguity" in checks


def test_modal_ambiguity_consistent_prescriptive(tmp_path):
    md = (
        "# Deploy the Service\n\n"
        "1. You must configure the environment variables.\n"
        "2. You must restart the service.\n"
        "3. You must verify the health endpoint returns 200.\n"
    )
    issues = _run(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert "Rhetoric.ModalAmbiguity" not in checks


def test_modal_ambiguity_consistent_advisory(tmp_path):
    md = (
        "# Best Practices\n\n"
        "1. You should configure logging.\n"
        "2. Consider enabling health checks.\n"
        "3. You may set a timeout.\n"
    )
    issues = _run(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert "Rhetoric.ModalAmbiguity" not in checks


def test_modal_ambiguity_no_modals(tmp_path):
    md = (
        "# Steps\n\n"
        "1. Configure the environment variables.\n"
        "2. Restart the service.\n"
        "3. Run the health check.\n"
    )
    issues = _run(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert "Rhetoric.ModalAmbiguity" not in checks


def test_modal_ambiguity_required_vs_optional(tmp_path):
    md = (
        "# Configuration\n\n"
        "1. Set the required API key.\n"
        "2. This step is optional if you have a default config.\n"
    )
    issues = _run(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert "Rhetoric.ModalAmbiguity" in checks


# ---------------------------------------------------------------------------
# Cohesion.ForwardReference
# ---------------------------------------------------------------------------


def test_forward_reference_as_described_above(tmp_path):
    md = "# Configuration\n\nAs described above, the service requires three environment variables.\n"
    issues = _run(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert "Cohesion.ForwardReference" in checks


def test_forward_reference_previous_section(tmp_path):
    md = "# Advanced Setup\n\nIn the previous section, we installed the base package.\n"
    issues = _run(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert "Cohesion.ForwardReference" in checks


def test_forward_reference_no_false_positive_code_block(tmp_path):
    # Phrase inside a code block should not trigger
    md = (
        "# Example\n\n"
        "```\n"
        "# as described above\n"
        "value = 42\n"
        "```\n"
    )
    issues = _run(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert "Cohesion.ForwardReference" not in checks


def test_forward_reference_no_trigger_clean_section(tmp_path):
    md = (
        "# Configuration\n\n"
        "Set the following environment variables before running the service.\n\n"
        "The service reads configuration from a YAML file at startup.\n"
    )
    issues = _run(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert "Cohesion.ForwardReference" not in checks


def test_forward_reference_as_mentioned_above(tmp_path):
    md = "# Deployment\n\nAs mentioned above, you need Docker installed.\n"
    issues = _run(md, tmp_path)
    checks = {i["check"] for i in issues}
    assert "Cohesion.ForwardReference" in checks


# ---------------------------------------------------------------------------
# Rhetoric.UnresolvedContrast
# ---------------------------------------------------------------------------


def _contrast_checks(text: str, tmp_path):
    issues = _run(text, tmp_path)
    return {i["check"] for i in issues}


def test_contrast_resolved_therefore(tmp_path):
    md = (
        "# Overview\n\n"
        "The system processes requests synchronously. "
        "However, this can be slow under load. "
        "Therefore, we recommend using the async API for batch workloads. "
        "This keeps latency low.\n"
    )
    checks = _contrast_checks(md, tmp_path)
    assert "Rhetoric.UnresolvedContrast" not in checks


def test_contrast_unresolved_fires(tmp_path):
    md = (
        "# Overview\n\n"
        "The system processes requests synchronously. "
        "However, this can be slow under load. "
        "Users have reported timeouts during peak periods. "
        "The team is investigating root causes.\n"
    )
    checks = _contrast_checks(md, tmp_path)
    assert "Rhetoric.UnresolvedContrast" in checks


def test_contrast_below_min_sentences_no_finding(tmp_path):
    md = "# Overview\n\nBut this is short.\n"
    checks = _contrast_checks(md, tmp_path)
    assert "Rhetoric.UnresolvedContrast" not in checks


def test_contrast_mid_sentence_signal_no_finding(tmp_path):
    # "but" appears past the 30% position — should not trigger
    md = (
        "# Overview\n\n"
        "The feature works well in production environments, but edge cases exist. "
        "We have tested it thoroughly. "
        "Performance is acceptable across all scenarios. "
        "Further investigation is ongoing.\n"
    )
    checks = _contrast_checks(md, tmp_path)
    assert "Rhetoric.UnresolvedContrast" not in checks


def test_contrast_mid_sentence_no_finding(tmp_path):
    # "but" deep in a sentence (> 30% position) should not trigger
    md = (
        "# Overview\n\n"
        "The feature works in production environments, but edge cases exist under load. "
        "We have tested it thoroughly across all scenarios. "
        "Performance is acceptable in all observed cases. "
        "Further investigation is ongoing.\n"
    )
    issues = _run(md, tmp_path)
    contrast = [i for i in issues if i["check"] == "Rhetoric.UnresolvedContrast"]
    assert len(contrast) == 0


def test_contrast_precision_corpus(tmp_path):
    """Zero findings on the precision corpus (false-positive guard)."""
    import os
    corpus_dir = (
        "tests/fixtures/corpus/technical/"
    )
    if not os.path.isdir(corpus_dir):
        return
    eng = RhetoricEngine()
    files = [
        os.path.join(corpus_dir, f)
        for f in os.listdir(corpus_dir)
        if f.endswith(".md")
    ]
    issues = eng.lint_files(files)
    contrast = [i for i in issues if i["check"] == "Rhetoric.UnresolvedContrast"]
    assert contrast == [], f"Unexpected findings on precision corpus: {contrast}"
