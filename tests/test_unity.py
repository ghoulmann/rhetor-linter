import pytest

from rhetoric_lint.engine import RhetoricEngine

# These tests require the AST parser (mistletoe)
pytest.importorskip("mistletoe")


def _run_md(md: str, tmp_path):
    p = tmp_path / "unity.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    return engine.lint_files([str(p)])


def test_unity_heading_topic_coherence_no_issue_when_aligned(tmp_path):
    md = """# Guide

## Deploy service

Deploy service updates with the release pipeline.

Use deployment logs to verify each release.
"""
    issues = _run_md(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Unity.HeadingTopicCoherence" not in checks


def test_unity_heading_topic_coherence_flags_misalignment(tmp_path):
    md = """# Guide

## Deploy service

Quantum particles oscillate in entangled vacuum states.
"""
    issues = _run_md(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Unity.HeadingTopicCoherence" in checks


def test_unity_topic_section_drift_flags_when_body_shifts_topic(tmp_path):
    md = """# Guide

## Deploy service

Deploy service changes with a staged rollout.

Orchids require humidity and indirect sunlight for growth.
"""
    issues = _run_md(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Unity.TopicSectionDrift" in checks


def test_unity_no_false_positive_surface_form_divergence(tmp_path):
    # "MkDocs" (PROPN → lemma "mkdocs") vs "mkdocs" (NN → lemma "mkdoc")
    # Surface-form fallback in channelize_tokens should bridge these.
    md = """# MkDocs Installation

## Installing MkDocs

Install the mkdocs package using pip to get started.
"""
    issues = _run_md(md, tmp_path)
    checks = [it.get("check") for it in issues]
    assert "Unity.HeadingTopicCoherence" not in checks


def test_unity_no_false_positive_stem_bridge(tmp_path):
    # "Requirements" heading vs "requires" in body — stem "requir" bridges them.
    md = """# Guide

## Requirements

MkDocs requires Python 3.8 or later to be installed.
"""
    issues = _run_md(md, tmp_path)
    checks = [it.get("check") for it in issues]
    assert "Unity.HeadingTopicCoherence" not in checks
