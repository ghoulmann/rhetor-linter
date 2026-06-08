"""Unit tests for the genre classifier and engine integration."""

import pytest

pytest.importorskip("mistletoe")

import rhetoric_lint.const as const
from rhetoric_lint.engine import RhetoricEngine
from rhetoric_lint.genre import classify_genre


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify(md: str, tmp_path, genre_override=None, filename="doc.md"):
    """Run the engine on *md* and return (genre, issues)."""
    p = tmp_path / filename
    p.write_text(md, encoding="utf-8")
    eng = RhetoricEngine()
    issues = eng.lint_files([str(p)], genre_override=genre_override)
    genre = eng.last_genres.get(str(p))
    return genre, issues


def _sections_doc(md: str):
    eng = RhetoricEngine()
    sections = eng._parse_with_mistletoe(md)
    doc = eng.nlp(md)
    return sections, doc, eng


# ---------------------------------------------------------------------------
# Filename-based genre detection
# ---------------------------------------------------------------------------

def test_readme_detected_by_filename(tmp_path):
    md = "# myproject\n\nA useful tool.\n"
    genre, _ = _classify(md, tmp_path, filename="README.md")
    assert genre == "readme"


def test_changelog_detected_by_filename(tmp_path):
    md = "# Changelog\n\n## [1.0.0]\n\n### Added\n\n- Initial release.\n"
    genre, _ = _classify(md, tmp_path, filename="CHANGELOG.md")
    assert genre == "changelog"


def test_contributing_detected_as_howto(tmp_path):
    md = "# Contributing\n\nFork the repo.\n\nRun the tests.\n"
    genre, _ = _classify(md, tmp_path, filename="CONTRIBUTING.md")
    assert genre == "howto"


def test_history_detected_as_changelog(tmp_path):
    md = "# History\n\n## v2.0.0\n\nBig rewrite.\n"
    genre, _ = _classify(md, tmp_path, filename="HISTORY.md")
    assert genre == "changelog"


# ---------------------------------------------------------------------------
# Changelog structural detection (content-based, non-README filenames)
# ---------------------------------------------------------------------------

def test_changelog_detected_by_version_headings(tmp_path):
    md = """\
# Project Changelog

## [2.1.0]

### Added

- New feature A.
- New feature B.

## [2.0.0]

### Fixed

- Fixed critical bug.

## [1.0.0]

### Changed

- Initial stable release.
"""
    sections, doc, eng = _sections_doc(md)
    genre = classify_genre(sections, doc, md, const)
    assert genre == "changelog"


def test_changelog_detected_by_semver_headings(tmp_path):
    md = """\
# Releases

## v1.2.3

Bug fixes.

## v1.2.0

New feature.
"""
    sections, doc, eng = _sections_doc(md)
    genre = classify_genre(sections, doc, md, const)
    assert genre == "changelog"


# ---------------------------------------------------------------------------
# ADR and postmortem (unchanged behavior)
# ---------------------------------------------------------------------------

def test_classifies_adr(tmp_path):
    md = """\
# Use PostgreSQL for Primary Storage

Status: Accepted

## Context

We need a relational database.

## Decision

We will use PostgreSQL.

## Consequences

Operational team must manage backups.
"""
    sections, doc, eng = _sections_doc(md)
    genre = classify_genre(sections, doc, md, const)
    assert genre == "adr"


def test_classifies_postmortem(tmp_path):
    md = """\
# Service Outage 2024-03-15

## Summary

The payment service was down for 45 minutes.

## Timeline

Events leading to the incident.

## Root Cause

A misconfigured load balancer rule.

## Action Items

1. Add monitoring for this path.
2. Document the config change process.

## Lessons Learned

Always review changes in staging first.
"""
    sections, doc, eng = _sections_doc(md)
    genre = classify_genre(sections, doc, md, const)
    assert genre == "postmortem"


# ---------------------------------------------------------------------------
# General fallback — documents without distinctive signals
# ---------------------------------------------------------------------------

def test_classifies_general_for_plain_prose(tmp_path):
    md = """\
# My Thoughts on Widgets

Widgets are interesting objects that people use every day.
They come in many shapes and sizes.

There are wooden widgets and plastic widgets.
Some people prefer metal widgets for their durability.

In conclusion, widgets serve many purposes in daily life.
"""
    sections, doc, _ = _sections_doc(md)
    genre = classify_genre(sections, doc, md, const)
    assert genre == "general"


def test_imrad_structure_without_signals_is_general(tmp_path):
    """IMRAD headings alone (no code, no status field) → general.

    Scientific papers are not a target genre; no rules are gated on them.
    """
    md = """\
# On Frobnicating Widgets

## Abstract

We study the frobnicating of widgets.

## Introduction

Widget frobnicating is a longstanding problem.

## Methods

We applied the Frobnitz algorithm.

## Results

Frobnicating improved yield by 12%.

## Discussion

These results suggest frobnicating is effective.

## Conclusion

Frobnicating widgets is worthwhile.
"""
    sections, doc, _ = _sections_doc(md)
    genre = classify_genre(sections, doc, md, const)
    assert genre == "general"


def test_numbered_curriculum_structure_without_signals_is_general(tmp_path):
    """Numbered headings + list density alone → general (not inferred as curriculum).

    Curriculum genre requires explicit genre_override or frontmatter.
    """
    md = """\
# Introduction to Widgets

## 1. Foundations of Widget Theory

- Widget history
- Widget anatomy
- Widget materials

## 2. Widget Design Principles

- Design patterns
- Color theory for widgets
- Ergonomic considerations

## 3. Advanced Widgetry

- Micro-widget fabrication
- Widget networks
- Widget lifecycle management
"""
    sections, doc, _ = _sections_doc(md)
    genre = classify_genre(sections, doc, md, const)
    assert genre == "general"


# ---------------------------------------------------------------------------
# Engine integration: last_genres is populated
# ---------------------------------------------------------------------------

def test_last_genres_populated_after_lint(tmp_path):
    md = """\
# Guide

## Install

```bash
pip install pkg
```
"""
    genre, _ = _classify(md, tmp_path)
    assert genre is not None
    assert isinstance(genre, str)


# ---------------------------------------------------------------------------
# genre_override bypasses classifier
# ---------------------------------------------------------------------------

def test_genre_override_bypasses_classifier(tmp_path):
    md = """\
# Widget Notes

Widgets are everywhere.

More widget thoughts here.
"""
    genre, _ = _classify(md, tmp_path, genre_override="curriculum")
    assert genre == "curriculum"


# ---------------------------------------------------------------------------
# Genre gate: GENRES filtering is respected when gate is on
# ---------------------------------------------------------------------------

def test_genre_gate_suppresses_tech_rules_for_curriculum(tmp_path, monkeypatch):
    """When gate is enabled and genre==curriculum, symmetry/completeness rules
    (GENRES={"technical","general"}) should not fire."""
    monkeypatch.setattr(const, "GENRE_GATE_ENABLED", True)

    md = """\
# Course Syllabus

## 1. Introduction to Theory

Read chapter one.

Consider the foundational concepts before the next session.

Learn the history of widget design.

## 2. Applied Practice

Attend the lab session.

Complete the hands-on exercises.

Review your notes after each session.
"""
    genre, issues = _classify(md, tmp_path, genre_override="curriculum")
    assert genre == "curriculum"

    tech_checks = {
        "Structure.TaskOrientation",
        "Symmetry.Parallelism",
        "Symmetry.OrderedListImperatives",
        "Completeness.ResultVerification",
        "Completeness.SchemaMapping",
        "Navigation.FindabilityMap",
        "Structure.ActionableHeadings",
        "Structure.WallOfText",
    }
    fired_checks = {it.get("check") for it in issues}
    assert not (fired_checks & tech_checks), (
        f"Tech rules fired on curriculum doc (gate enabled): {fired_checks & tech_checks}"
    )


def test_genre_gate_disabled_by_default(tmp_path, monkeypatch):
    """With GENRE_GATE_ENABLED=False (default), all rules run regardless of genre."""
    assert const.GENRE_GATE_ENABLED is False

    md = """\
# Course Syllabus

## 1. Introduction to Theory

Read chapter one. Consider the foundational concepts.

## 2. Applied Practice

Attend lab. Complete exercises.
"""
    eng = RhetoricEngine()
    p = tmp_path / "doc.md"
    p.write_text(md, encoding="utf-8")
    issues = eng.lint_files([str(p)], genre_override="curriculum")
    assert isinstance(issues, list)
