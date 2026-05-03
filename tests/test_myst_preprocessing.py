"""Tests for engine preprocessing of MyST/Sphinx markup and HTML comments.

These lock in the false-positive remediations described in
.claude/plans/investigate-fols-positives-and-structured-avalanche.md.
"""

import pytest

pytest.importorskip("mistletoe")

from rhetoric_lint.engine import (  # noqa: E402
    RhetoricEngine,
    _blank_html_comments,
    _rewrite_gfm_alerts,
    _rewrite_mkdocs_admonitions,
    _rewrite_myst_admonitions,
    _strip_myst_roles,
)
from rhetoric_lint.rules.cohesion import _token_lemmas  # noqa: E402


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


def test_soft_linebreak_preserves_word_boundary(tmp_path):
    """Multi-line paragraphs must not concatenate words across soft breaks.

    Regression for an engine-level bug where mistletoe LineBreak tokens were
    rendered as "" by _node_text, producing 'lives\\nin' -> 'livesin'. This
    silently dropped content overlap signal in cohesion analysis on every
    multi-line paragraph in every doc.
    """
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview.\n\n"
        "## Section heading goes here\n\n"
        "The class lives\n"
        "in the module under a package named for the\n"
        "jurisdiction. The class survives even when reloaded.\n"
    )
    p = tmp_path / "softbreak.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    sections = engine._parse_with_mistletoe(md)
    target = next(s for s in sections if s.get("heading") == "Section heading goes here")
    para_text = target["paragraphs"][0]["text"]
    assert "livesin" not in para_text
    assert "lives in" in para_text
    assert "thejurisdiction" not in para_text
    assert "the\njurisdiction" not in para_text  # newline collapsed to space


def test_mkdocs_admonition_rewrite_preserves_line_count():
    text = (
        "intro line\n"
        "\n"
        "!!! warning \"Optional title\"\n"
        "    Body line one.\n"
        "    Body line two.\n"
        "\n"
        "after\n"
    )
    out = _rewrite_mkdocs_admonitions(text)
    assert out.count("\n") == text.count("\n")
    assert "Warning" in out
    assert "Body line one" in out
    # Marker line replaced; body lines re-prefixed as blockquote.
    assert "!!!" not in out


def test_mkdocs_collapsible_admonition_rewrites():
    text = "??? note\n    Hidden body content here.\n"
    out = _rewrite_mkdocs_admonitions(text)
    assert "Note" in out
    assert "Hidden body content" in out
    assert "???" not in out


def test_mkdocs_admonition_does_not_consume_unindented_following_para(tmp_path):
    """Body ends at the first non-blank line not indented past the marker."""
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview of the pipeline.\n\n"
        "## Deploy the worker\n\n"
        "1. Build the image.\n"
        "2. Push it to the registry.\n\n"
        "!!! warning\n"
        "    If the registry push fails, abort and notify the on-call engineer.\n"
        "\n"
        "Subsequent ordinary paragraph that should not be inside the admonition.\n"
    )
    p = tmp_path / "mkdocs.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    # The admonition body satisfies ErrorPathPresence for the procedural section.
    assert not any(
        i.get("check") == "Resilience.ErrorPathPresence" and "Deploy the worker" in i.get("message", "")
        for i in issues
    )


def test_gfm_alert_rewrite_preserves_line_count():
    text = (
        "before\n"
        "\n"
        "> [!WARNING]\n"
        "> Body text of the alert.\n"
        "> More body.\n"
        "\n"
        "after\n"
    )
    out = _rewrite_gfm_alerts(text)
    assert out.count("\n") == text.count("\n")
    assert "Warning" in out
    assert "[!WARNING]" not in out


def test_gfm_alert_satisfies_resilience(tmp_path):
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview of the pipeline.\n\n"
        "## Deploy the worker\n\n"
        "1. Build the image.\n"
        "2. Push to the registry.\n"
        "3. Apply the manifest.\n\n"
        "> [!WARNING]\n"
        "> If the registry push fails, abort and notify the on-call engineer.\n"
    )
    p = tmp_path / "gfm.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert not any(
        i.get("check") == "Resilience.ErrorPathPresence" and "Deploy the worker" in i.get("message", "")
        for i in issues
    )


def test_token_lemmas_splits_dotted_identifiers():
    """spaCy emits 'court_scraper.scrapers' as one non-alpha token; cohesion
    must still see 'scraper'/'scrapers' as content lemmas."""
    engine = RhetoricEngine()
    sent = engine.nlp("The class lives in court_scraper.scrapers namespace.")
    lemmas = _token_lemmas(sent)
    # Identifier components are surfaced.
    assert "scraper" in lemmas or "scrapers" in lemmas
    assert "court" in lemmas
    # Stop/short fragments not included.
    assert "a" not in lemmas


def test_token_lemmas_splits_underscore_identifiers():
    engine = RhetoricEngine()
    sent = engine.nlp("Set captcha_service_required=True in the sites_meta entry.")
    lemmas = _token_lemmas(sent)
    assert "captcha" in lemmas
    assert "service" in lemmas
    assert "required" in lemmas
    assert "sites" in lemmas or "meta" in lemmas


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
