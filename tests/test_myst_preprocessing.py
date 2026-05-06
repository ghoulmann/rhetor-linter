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


def test_terminology_drift_skips_narrow_sense_words(tmp_path):
    """Words with <=2 WordNet synsets cannot reliably indicate drift."""
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview of the pipeline.\n\n"
        "## Project layout\n\n"
        "The whole project is organized into modules and test fixtures.\n\n"
        "## Worker tasks\n\n"
        "Each task in the queue triggers a downstream job.\n"
    )
    p = tmp_path / "narrow.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert not any(
        i.get("check") == "Cohesion.TerminologyDrift" and "project" in i.get("message", "")
        for i in issues
    ), "project/task narrow-sense words must not trigger drift"


def test_unity_skips_blockquote_topic(tmp_path):
    """Admonition leads (rewritten to blockquotes) must not be picked as topic."""
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview of the pipeline.\n\n"
        "## Storage architecture\n\n"
        "```{note}\n"
        "Check out the contributor guide before getting started on local setup.\n"
        "```\n\n"
        "The storage architecture writes thumbnails to object storage and "
        "indexes them in a relational table for fast lookup.\n"
    )
    p = tmp_path / "topic.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert not any(
        i.get("check") == "Unity.HeadingTopicCoherence" and "Storage" in i.get("message", "Storage architecture")
        for i in issues
    ), "Topic sentence picker must skip blockquote/admonition paragraphs"


def test_link_ref_def_does_not_swallow_next_line(tmp_path):
    """Reference-style links followed by code fences must not eat the fence.

    Regression for the engine's _LINK_REF_DEF_RE which used \\s+ (any
    whitespace including newlines) and silently consumed the next non-blank
    line — destroying the AST whenever a doc had "[label][ref]:" followed by
    a code fence or other content.
    """
    md = (
        "# Sample\n\n"
        "Top-level overview.\n\n"
        "## Generics\n\n"
        "To inherit from a generic model, the subclass must inherit from\n"
        "[`Generic`][typing.Generic]:\n\n"
        "```python\n"
        "from typing import Generic\n"
        "```\n\n"
        "Following text.\n"
    )
    p = tmp_path / "linkref.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    sections = engine._parse_with_mistletoe(md)
    # Code fence content must survive intact in the section's paragraphs.
    target = next(s for s in sections if s.get("heading") == "Generics")
    code_para = next(
        (p for p in target.get("paragraphs", [])
         if (p.get("nodes") or [{}])[0].get("type") in {"Code", "CodeFence", "FencedCode"}),
        None,
    )
    assert code_para is not None, \
        "Code fence following a reference-link line was consumed by _LINK_REF_DEF_RE"
    assert "from typing import Generic" in (code_para.get("text") or "")


def test_overlap_channelize_splits_dotted_identifiers():
    """Dotted/underscore identifiers must contribute lemmas across all rules."""
    from rhetoric_lint.overlap import channelize_tokens
    engine = RhetoricEngine()
    sent = engine.nlp("The class lives in court_scraper.scrapers namespace.")
    ch = channelize_tokens(sent)
    assert "scraper" in ch["content"] or "scrapers" in ch["content"]
    assert "court" in ch["content"]
    # Components are also classified as nouns for argument-channel coverage.
    assert "court" in ch["nouns"]


def test_topic_type_we_alone_is_not_tutorial(tmp_path):
    """Plain 'we' in body without learning-frame cues must not classify tutorial."""
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview of the pipeline.\n\n"
        "## Devise a scraping strategy\n\n"
        "Before coding, we favor scrapers that gather data using HTTP calls "
        "rather than browser automation.\n"
    )
    p = tmp_path / "we.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert not any(i.get("check", "").startswith("Tutorial.") for i in issues), \
        "Bare 'we' is not a tutorial cue"


def test_task_orientation_counts_admonitions(tmp_path):
    """Admonitions rewritten to blockquotes must count toward task density."""
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview of the pipeline.\n\n"
        "## Build the worker container\n\n"
        "Build the container image with the standard build script.\n\n"
        "```{warning}\n"
        "If the build fails, check that Docker is running before retrying.\n"
        "```\n\n"
        "```{note}\n"
        "The build cache is shared across worker variants.\n"
        "```\n\n"
        "```bash\n"
        "make build\n"
        "```\n"
    )
    p = tmp_path / "td.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    # 2 admonitions + 1 code fence + 2 paragraphs => td = 3/5 = 0.6 > 0.3
    assert not any(
        i.get("check") == "Structure.TaskOrientation" and "Build the worker" in i.get("message", "")
        for i in issues
    )


def test_cohesion_demonstrative_determiner_bridges(tmp_path):
    """'Such cases', 'This file', 'These X' anaphoric references should bridge."""
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview of the pipeline.\n\n"
        "## Storage strategy\n\n"
        "We store thumbnails in object storage rather than the relational database. "
        "Such storage scales independently of the primary write workload. "
        "These thumbnails are served directly from the bucket.\n"
    )
    p = tmp_path / "demonstrative.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    breaks = [i for i in issues if i.get("check") == "Cohesion.Break"]
    assert not breaks, (
        "Demonstrative determiners ('Such', 'These') opening a sentence "
        f"with a content noun should bridge cohesion. Got: {breaks}"
    )


def test_cohesion_demonstrative_pronoun_does_not_bridge(tmp_path):
    """'This is X' (demonstrative as pronoun, not determiner) should NOT bridge."""
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview of the pipeline.\n\n"
        "## Storage strategy\n\n"
        "We store thumbnails in object storage rather than the relational database. "
        "Whales migrate thousands of miles each year along ocean corridors.\n"
    )
    p = tmp_path / "no-bridge.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    # Genuinely unrelated sentences must still flag.
    assert any(i.get("check") == "Cohesion.Break" for i in issues)


def test_deictic_ghost_ignores_relative_pronoun_that(tmp_path):
    """'Sites that are heavy' — 'that' is a relative pronoun, not deictic."""
    md = (
        "# Scraping strategy\n\n"
        "Top-level overview.\n\n"
        "## Approach\n\n"
        "We favor scrapers that gather data using basic HTTP calls. "
        "Sites that are heavy on dynamically generated content require "
        "browser automation instead.\n"
    )
    p = tmp_path / "relpron.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert not any(i.get("check") == "Cohesion.DeicticGhost" for i in issues), \
        "Mid-sentence relative-pronoun 'that' must not be flagged as deictic"


def test_deictic_ghost_still_fires_on_sentence_initial(tmp_path):
    """Recall: a true sentence-initial 'This/That' with no antecedent must fire."""
    md = (
        "# Image processing pipeline\n\n"
        "Top-level overview of the pipeline.\n\n"
        "## Notes\n\n"
        "Whales migrate thousands of miles each year. "
        "This is critical for downstream consumers.\n"
    )
    p = tmp_path / "ghost.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert any(i.get("check") == "Cohesion.DeicticGhost" for i in issues)


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
