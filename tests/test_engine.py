import pytest
from rhetoric_lint.engine import RhetoricEngine, get_synsets

# Skip these tests if mistletoe isn't installed
pytest.importorskip("mistletoe")


def test_get_synsets_returns_set():
    s = "Run the test and verify output."
    syns = get_synsets(s)
    assert isinstance(syns, set)


def test_engine_sections_and_basic_lint(tmp_path):
    md = """# Project Title

## Introduction

This is an intro paragraph.

- Run the tests
- Build the project
- Packaging the release
"""

    p = tmp_path / "sample.md"
    p.write_text(md, encoding="utf-8")

    engine = RhetoricEngine()
    issues = engine.lint_files([str(p)])
    assert isinstance(issues, list)
    # Expect at least one heading-related or symmetry-related issue
    checks = {it.get("check") for it in issues}
    assert any(
        c
        for c in checks
        if c
        and (
            c.startswith("Heading")
            or c.startswith("Symmetry")
            or c.startswith("Structure")
        )
    )
