"""Tests for engine preprocessing of MyST/Sphinx markup and HTML comments.

These lock in the false-positive remediations described in
.claude/plans/investigate-fols-positives-and-structured-avalanche.md.
"""

import pytest

pytest.importorskip("mistletoe")

from rhetoric_lint.engine import (  # noqa: E402
    RhetoricEngine,
    _blank_html_comments,
    _rewrite_myst_admonitions,
    _strip_myst_roles,
)


def test_html_comment_blanking_preserves_line_count():
    text = "before\n<!-- one\ntwo\nthree -->\nafter\n"
    out = _blank_html_comments(text)
    assert out.count("\n") == text.count("\n")
    assert "one" not in out and "three" not in out
    assert "before" in out and "after" in out


def test_myst_role_stripped_to_label():
    assert _strip_myst_roles("see {code}`Site` class") == "see Site class"
    assert _strip_myst_roles("call {py:class}`court_scraper.Site`") == "call court_scraper.Site"


def test_myst_ref_role_keeps_label_drops_target():
    assert _strip_myst_roles("see {ref}`Place ID <place id>`") == "see Place ID"


def test_admonition_rewrite_preserves_line_count():
    text = "intro\n\n```{warning}\nDo not retry forever.\nLog and abort.\n```\n\nafter\n"
    out = _rewrite_myst_admonitions(text)
    assert out.count("\n") == text.count("\n")
    # Warning kind survives so keyword-based rules can find it.
    assert "Warning" in out
    assert "abort" in out


def test_information_scent_skips_short_h1(tmp_path):
    """H1 'Writing a scraper' has 2 content words — too short to anchor."""
    md = (
        "# Writing a scraper\n\n"
        "Intro paragraph about scraping.\n\n"
        "## Add a Site class\n\n"
        "The main task is creating a Site class with a search method.\n"
    )
    p = tmp_path / "short_h1.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert not any(i.get("check") == "Heading.InformationScent" for i in issues), \
        "H2 under a 2-word H1 must not trigger InformationScent"


def test_information_scent_still_fires_for_specific_h1(tmp_path):
    """H1 with 3+ content words is specific enough to anchor."""
    md = (
        "# Image processing pipeline\n\n"
        "This pipeline ingests photographs and stores thumbnails.\n\n"
        "## Configuring auth\n\n"
        "Auth tokens come from the central identity provider.\n"
    )
    p = tmp_path / "specific_h1.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert any(
        i.get("check") == "Heading.InformationScent" and "Configuring auth" in i.get("message", "")
        for i in issues
    ), "Off-topic H2 under specific H1 should still warn"


def test_resilience_skips_conceptual_verb_led_section(tmp_path):
    """Verb-led heading + conceptual body (no imperatives) must not warn."""
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview of the pipeline.\n\n"
        "## Understand the data flow\n\n"
        "The scraper produces three artifacts for each case: a metadata record, "
        "the raw search-results HTML, and the case-detail HTML. "
        "Downstream pipelines join these on the case number.\n"
    )
    p = tmp_path / "conceptual.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert not any(i.get("check") == "Resilience.ErrorPathPresence" for i in issues), \
        "Conceptual section with verb-led heading must not require failure guidance"


def test_resilience_admonition_satisfies_failure_guidance(tmp_path):
    """A {warning} admonition supplies failure guidance."""
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview of the pipeline.\n\n"
        "## Deploy the worker\n\n"
        "1. Build the image.\n"
        "2. Push to the registry.\n"
        "3. Apply the manifest.\n\n"
        "```{warning}\n"
        "If the registry push fails, abort and notify the on-call engineer.\n"
        "```\n"
    )
    p = tmp_path / "with_admonition.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert not any(
        i.get("check") == "Resilience.ErrorPathPresence" and "Deploy the worker" in i.get("message", "")
        for i in issues
    ), "Section with {warning} admonition body must satisfy ErrorPathPresence"


def test_resilience_still_fires_on_unguarded_procedure(tmp_path):
    """Recall guard: a procedure with no failure guidance must still warn."""
    md = (
        "# Image processing pipeline\n\n"
        "Overview of the deployment pipeline.\n\n"
        "## Deploy the worker\n\n"
        "1. Build the worker image.\n"
        "2. Push it to the registry.\n"
        "3. Apply the Kubernetes manifest.\n"
        "4. Verify the pod reaches Running status.\n"
    )
    p = tmp_path / "unguarded.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert any(
        i.get("check") == "Resilience.ErrorPathPresence" and "Deploy the worker" in i.get("message", "")
        for i in issues
    )
