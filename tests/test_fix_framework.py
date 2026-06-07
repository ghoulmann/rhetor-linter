"""Tests for fix.py and SP1 runner / CrossFileContext wiring."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from rhetoric_lint.fix import apply_fixes, _apply_line_fix
from rhetoric_lint.engine import CrossFileContext, RhetoricEngine


# ── _apply_line_fix unit tests ────────────────────────────────────────────────

def test_apply_line_fix_single_replacement():
    # "hello world" → replace "hello" (col 1, len 5) with "goodbye"
    line = "hello world\n"
    fix = {"edit_column": 1, "delete_count": 5, "insert_text": "goodbye"}
    new_line, ok = _apply_line_fix(line, fix)
    assert ok
    assert new_line == "goodbye world\n"


def test_apply_line_fix_pure_insert():
    line = "hello world\n"
    fix = {"edit_column": 6, "delete_count": 0, "insert_text": " there"}
    new_line, ok = _apply_line_fix(line, fix)
    assert ok
    assert new_line == "hello there world\n"


def test_apply_line_fix_pure_delete():
    line = "hello  world\n"
    fix = {"edit_column": 6, "delete_count": 1, "insert_text": ""}
    new_line, ok = _apply_line_fix(line, fix)
    assert ok
    assert new_line == "hello world\n"


def test_apply_line_fix_missing_column_returns_false():
    line = "some text\n"
    fix = {"delete_count": 2, "insert_text": "xx"}
    new_line, ok = _apply_line_fix(line, fix)
    assert not ok
    assert new_line == line


# ── apply_fixes file-level tests ─────────────────────────────────────────────

def test_apply_fixes_single_fix(tmp_path: Path):
    f = tmp_path / "test.md"
    f.write_text("hello world\n", encoding="utf-8")
    findings = [
        {
            "path": str(f),
            "line": 1,
            "fix": {"edit_column": 1, "delete_count": 5, "insert_text": "goodbye"},
        }
    ]
    count = apply_fixes(str(f), findings)
    assert count == 1
    assert f.read_text() == "goodbye world\n"


def test_apply_fixes_multiple_fixes_same_line_rightmost_first(tmp_path: Path):
    f = tmp_path / "test.md"
    # "simply just easy" → remove "simply " (col 1) and "just " (col 8)
    f.write_text("simply just easy\n", encoding="utf-8")
    findings = [
        {
            "path": str(f), "line": 1,
            "fix": {"edit_column": 1, "delete_count": 7, "insert_text": ""},
        },
        {
            "path": str(f), "line": 1,
            "fix": {"edit_column": 8, "delete_count": 5, "insert_text": ""},
        },
    ]
    count = apply_fixes(str(f), findings)
    assert count == 2
    # Rightmost fix (col 8) applied first: "simply easy\n"
    # Then leftmost (col 1, 7 chars): " easy\n" → but after rightmost "simply easy"
    # col 1, delete 7 → "easy\n"
    assert f.read_text() == "easy\n"


def test_apply_fixes_empty_findings(tmp_path: Path):
    f = tmp_path / "test.md"
    original = "unchanged content\n"
    f.write_text(original, encoding="utf-8")
    count = apply_fixes(str(f), [])
    assert count == 0
    assert f.read_text() == original


def test_apply_fixes_finding_without_fix_key_skipped(tmp_path: Path):
    f = tmp_path / "test.md"
    original = "no changes\n"
    f.write_text(original, encoding="utf-8")
    findings = [{"path": str(f), "line": 1, "message": "something", "severity": "warning"}]
    count = apply_fixes(str(f), findings)
    assert count == 0
    assert f.read_text() == original


def test_apply_fixes_readonly_file_raises(tmp_path: Path):
    f = tmp_path / "readonly.md"
    f.write_text("content\n", encoding="utf-8")
    original_mode = f.stat().st_mode
    f.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    try:
        findings = [
            {"path": str(f), "line": 1,
             "fix": {"edit_column": 1, "delete_count": 3, "insert_text": "new"}}
        ]
        with pytest.raises((PermissionError, OSError)):
            apply_fixes(str(f), findings)
    finally:
        f.chmod(original_mode)


def test_apply_fixes_does_not_modify_unfixed_lines(tmp_path: Path):
    f = tmp_path / "test.md"
    f.write_text("line one\nline two\nline three\n", encoding="utf-8")
    findings = [
        {"path": str(f), "line": 2,
         "fix": {"edit_column": 6, "delete_count": 3, "insert_text": "TWO"}}
    ]
    apply_fixes(str(f), findings)
    lines = f.read_text().splitlines()
    assert lines[0] == "line one"
    assert lines[1] == "line TWO"
    assert lines[2] == "line three"


# ── CrossFileContext tests ────────────────────────────────────────────────────

def test_cross_file_context_scan_empty_no_crash():
    cfc = CrossFileContext()
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        nlp = spacy.blank("en")
    cfc.scan([], nlp)
    assert cfc.term_first_seen == {}
    assert cfc.concept_definitions == {}


def test_cross_file_context_scan_populates_term_first_seen(tmp_path: Path):
    f1 = tmp_path / "doc1.md"
    f2 = tmp_path / "doc2.md"
    f1.write_text("Authentication is the process of verifying identity.\n", encoding="utf-8")
    f2.write_text("Authorization controls access to resources.\n", encoding="utf-8")

    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        nlp = spacy.blank("en")
        try:
            nlp.add_pipe("sentencizer")
        except Exception:
            pass

    cfc = CrossFileContext()
    cfc.scan([str(f1), str(f2)], nlp)
    # At least one term should be populated
    assert len(cfc.term_first_seen) >= 1


# ── Engine context["cross_file"] wiring tests ────────────────────────────────

def test_engine_context_has_cross_file_key(tmp_path: Path):
    """Every per-file context dict must contain cross_file (not None)."""
    f = tmp_path / "sample.md"
    f.write_text("# Hello\n\nThis is a paragraph.\n", encoding="utf-8")

    engine = RhetoricEngine()
    captured_contexts: list = []

    original_lint = engine.lint_files.__func__  # type: ignore[attr-defined]

    # Monkey-patch one rule to capture context
    def _capture_rule(ctx):
        captured_contexts.append(ctx)
        return []

    _capture_rule.genres = frozenset({"all"})
    engine.rules.insert(0, _capture_rule)

    engine.lint_files([str(f)])

    assert captured_contexts, "No context was captured"
    for ctx in captured_contexts:
        assert "cross_file" in ctx
        assert ctx["cross_file"] is not None


def test_rules_without_cross_file_usage_no_breakage(tmp_path: Path):
    """Existing rules that ignore context['cross_file'] must still run without errors."""
    f = tmp_path / "plain.md"
    f.write_text("# Title\n\nA short paragraph.\n", encoding="utf-8")
    engine = RhetoricEngine()
    # Should not raise
    issues = engine.lint_files([str(f)])
    assert isinstance(issues, list)
