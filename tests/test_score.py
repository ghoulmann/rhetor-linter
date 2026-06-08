"""Tests for score.py and the score CLI subcommand."""

import json
import pytest

pytest.importorskip("mistletoe")

from rhetoric_lint.score import score_file, ScoreResult, DimensionScore
from rhetoric_lint.engine import RhetoricEngine


# ---------------------------------------------------------------------------
# score_file() unit tests
# ---------------------------------------------------------------------------

def _make_context(genre="howto", doc_template="general"):
    return {"genre": genre, "doc_template": doc_template, "doc": None}


def test_score_file_returns_score_result():
    result = score_file("doc.md", [], _make_context(), word_count=500)
    assert isinstance(result, ScoreResult)
    assert result.path == "doc.md"
    assert result.word_count == 500
    assert result.genre == "howto"
    assert result.doc_template == "general"


def test_score_file_no_findings_all_zero():
    result = score_file("doc.md", [], _make_context(), word_count=500)
    for dim in result.dimensions.values():
        assert dim.finding_count == 0
        assert dim.density == 0.0


def test_score_file_badge_suppressed_below_threshold():
    result = score_file("short.md", [], _make_context(), word_count=50)
    assert result.badge_suppressed is True


def test_score_file_badge_not_suppressed_above_threshold():
    result = score_file("long.md", [], _make_context(), word_count=200)
    assert result.badge_suppressed is False


def test_score_file_finding_routed_to_correct_dimension():
    findings = [
        {"check": "Cohesion.Break", "severity": "warning", "line": 1},
        {"check": "Heading.Generic", "severity": "warning", "line": 2},
        {"check": "Completeness.ResultVerification", "severity": "error", "line": 3},
    ]
    result = score_file("doc.md", findings, _make_context(), word_count=1000)
    assert result.dimensions["Clarity"].finding_count == 1
    assert result.dimensions["Structure"].finding_count == 1
    assert result.dimensions["Completeness"].finding_count == 1


def test_score_file_unknown_check_falls_to_style():
    findings = [{"check": "Unknown.SomeRule", "severity": "suggestion", "line": 1}]
    result = score_file("doc.md", findings, _make_context(), word_count=1000)
    assert result.dimensions["Style"].finding_count == 1


def test_score_file_density_calculation():
    findings = [{"check": "Cohesion.Break", "severity": "warning", "line": 1}]
    result = score_file("doc.md", findings, _make_context(), word_count=1000)
    assert result.dimensions["Clarity"].density == 1.0  # 1 / 1000 * 1000


def test_score_file_word_count_none_with_null_doc():
    result = score_file("doc.md", [], {"genre": "howto", "doc_template": "general", "doc": None})
    assert result.word_count == 0
    assert result.badge_suppressed is True


# ---------------------------------------------------------------------------
# Engine last_doc_templates / last_word_counts populated
# ---------------------------------------------------------------------------

def test_engine_stores_doc_template_and_word_count(tmp_path):
    md = "# Guide\n\nInstall the package.\n\nRun the tests.\n"
    p = tmp_path / "doc.md"
    p.write_text(md)
    eng = RhetoricEngine()
    eng.lint_files([str(p)])
    assert str(p) in eng.last_doc_templates
    assert str(p) in eng.last_word_counts
    assert eng.last_word_counts[str(p)] > 0


# ---------------------------------------------------------------------------
# score CLI subcommand (via typer runner)
# ---------------------------------------------------------------------------

def test_score_cli_outputs_valid_json(tmp_path):
    from typer.testing import CliRunner
    from rhetoric_lint.main import app

    md = "# Guide\n\n" + ("Install the package and run the tests. " * 10) + "\n"
    p = tmp_path / "doc.md"
    p.write_text(md)

    runner = CliRunner()
    result = runner.invoke(app, ["score", str(p)])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["path"] == str(p)
    assert "dimensions" in data[0]
    assert "findings" not in data[0]  # findings are omitted from score output


def test_score_cli_exits_zero_even_with_findings(tmp_path):
    from typer.testing import CliRunner
    from rhetoric_lint.main import app

    md = "No H1 here.\n\nJust some text without a heading.\n"
    p = tmp_path / "doc.md"
    p.write_text(md)

    runner = CliRunner()
    result = runner.invoke(app, ["score", str(p)])
    assert result.exit_code == 0
