"""Unit tests for the genre classifier and engine integration."""

import pytest

pytest.importorskip("mistletoe")

import rhetoric_lint.const as const
from rhetoric_lint.engine import RhetoricEngine
from rhetoric_lint.genre import classify_genre


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify(md: str, tmp_path, genre_override=None):
    """Run the engine on *md* and return (genre, issues)."""
    p = tmp_path / "doc.md"
    p.write_text(md, encoding="utf-8")
    eng = RhetoricEngine()
    issues = eng.lint_files([str(p)], genre_override=genre_override)
    genre = eng.last_genres.get(str(p))
    return genre, issues


# ---------------------------------------------------------------------------
# Classifier unit tests (classify_genre called directly)
# ---------------------------------------------------------------------------

def test_classifies_technical_by_code_fence_density(tmp_path):
    md = """\
# Deploy Service

## Install

Install the package.

```bash
pip install mypackage
```

```bash
mypackage deploy --env prod
```

## Configure

```yaml
service:
  name: myapp
```
"""
    p = tmp_path / "doc.md"
    p.write_text(md, encoding="utf-8")
    eng = RhetoricEngine()
    sections = eng._parse_with_mistletoe(md)
    import spacy
    nlp = eng.nlp
    doc = nlp(md)
    genre = classify_genre(sections, doc, md, const)
    assert genre == "technical"


def test_classifies_scientific_by_imrad_headings(tmp_path):
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
    p = tmp_path / "doc.md"
    p.write_text(md, encoding="utf-8")
    eng = RhetoricEngine()
    sections = eng._parse_with_mistletoe(md)
    doc = eng.nlp(md)
    genre = classify_genre(sections, doc, md, const)
    assert genre == "scientific"


def test_classifies_curriculum_by_numbered_headings_and_list_density(tmp_path):
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
    p = tmp_path / "doc.md"
    p.write_text(md, encoding="utf-8")
    eng = RhetoricEngine()
    sections = eng._parse_with_mistletoe(md)
    doc = eng.nlp(md)
    genre = classify_genre(sections, doc, md, const)
    assert genre == "curriculum"


def test_classifies_general_for_plain_prose(tmp_path):
    md = """\
# My Thoughts on Widgets

Widgets are interesting objects that people use every day.
They come in many shapes and sizes.

There are wooden widgets and plastic widgets.
Some people prefer metal widgets for their durability.

In conclusion, widgets serve many purposes in daily life.
"""
    p = tmp_path / "doc.md"
    p.write_text(md, encoding="utf-8")
    eng = RhetoricEngine()
    sections = eng._parse_with_mistletoe(md)
    doc = eng.nlp(md)
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
    # Plain prose document would normally classify as "general"
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

    # Document with ordered list that would normally trigger
    # Structure.TaskOrientation or Symmetry.OrderedListImperatives
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
    assert const.GENRE_GATE_ENABLED is False  # verify default

    md = """\
# Course Syllabus

## 1. Introduction to Theory

Read chapter one. Consider the foundational concepts.

## 2. Applied Practice

Attend lab. Complete exercises.
"""
    # Even with curriculum genre, tech rules should still be able to fire
    # (gate is off)
    eng = RhetoricEngine()
    p = tmp_path / "doc.md"
    p.write_text(md, encoding="utf-8")
    # Just confirm it doesn't raise and returns issues (gate-off path)
    issues = eng.lint_files([str(p)], genre_override="curriculum")
    assert isinstance(issues, list)
