import pytest
from pathlib import Path

from rhetoric_lint.engine import RhetoricEngine

# Skip these tests if mistletoe isn't installed
pytest.importorskip("mistletoe")


def test_cohesion_issue_line_is_absolute(tmp_path: Path):
    md = """# Section

This is a sentence about apples.

Completely unrelated island sentence about quantum mechanics.
"""
    p = tmp_path / "pos.md"
    p.write_text(md, encoding="utf-8")

    eng = RhetoricEngine()
    issues = eng.lint_files([str(p)])

    # find cohesion issues for this file
    coh = [
        it
        for it in issues
        if it.get("check") == "Cohesion.Break" and it.get("path") == str(p)
    ]
    assert coh, "expected at least one Cohesion.Break issue"

    # the unrelated sentence starts on line 5 of the file
    # pick the first cohesion issue and assert its line is the expected one
    assert coh[0]["line"] == 5
