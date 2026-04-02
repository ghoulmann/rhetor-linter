"""Tests for ADR genre classifier and ADR.* rules."""
import pytest
from rhetoric_lint.genre import classify_genre
from rhetoric_lint.rules.adr import check


# ---------------------------------------------------------------------------
# Genre classifier tests
# ---------------------------------------------------------------------------

def _sections(headings):
    return [{"heading": h, "paragraphs": [], "start": 0, "end": 0, "level": 2}
            for h in headings]


def _sections_with_body(heading_bodies):
    """heading_bodies: list of (heading, body_text) tuples."""
    secs = []
    for h, body in heading_bodies:
        paras = [{"text": body, "pos": 0, "end": 0, "line": 1, "doc": None,
                  "sentences": [], "nodes": []}] if body else []
        secs.append({"heading": h, "paragraphs": paras, "start": 0, "end": 0, "level": 2})
    return secs


def test_classifies_adr_by_status_and_headings():
    text = "Status: Accepted\n\n## Context\n\n## Decision\n\n## Consequences\n"
    secs = _sections(["Context", "Decision", "Consequences"])
    assert classify_genre(secs, None, text) == "adr"


def test_adr_not_classified_without_status():
    text = "## Context\n\n## Decision\n\n## Consequences\n"
    secs = _sections(["Context", "Decision", "Consequences"])
    # No Status: line — should fall through to general/technical
    result = classify_genre(secs, None, text)
    assert result != "adr"


def test_adr_not_classified_with_status_only_one_section():
    text = "Status: Accepted\n\n## Decision\n"
    secs = _sections(["Decision"])
    result = classify_genre(secs, None, text)
    assert result != "adr"


# ---------------------------------------------------------------------------
# Rule tests
# ---------------------------------------------------------------------------

def _ctx(text, headings_bodies):
    secs = _sections_with_body(headings_bodies)
    return {"path": "test.md", "text": text, "sections": secs}


def test_adr_complete_no_issues():
    text = "Status: Accepted\n"
    ctx = _ctx(text, [
        ("Context", "We needed to choose a database."),
        ("Decision", "We will use PostgreSQL."),
        ("Consequences", "Higher operational overhead but better query support."),
    ])
    assert check(ctx) == []


def test_adr_missing_status():
    text = "# ADR 001\n"
    ctx = _ctx(text, [
        ("Context", "We needed to choose a database."),
        ("Decision", "We will use PostgreSQL."),
        ("Consequences", "Higher overhead."),
    ])
    issues = check(ctx)
    checks = [i["check"] for i in issues]
    assert "ADR.MissingStatus" in checks


def test_adr_missing_decision():
    text = "Status: Accepted\n"
    ctx = _ctx(text, [
        ("Context", "We needed to choose a database."),
        ("Consequences", "Higher overhead."),
    ])
    issues = check(ctx)
    assert any(i["check"] == "ADR.MissingDecision" for i in issues)


def test_adr_missing_consequences():
    text = "Status: Accepted\n"
    ctx = _ctx(text, [
        ("Context", "We needed to choose a database."),
        ("Decision", "We will use PostgreSQL."),
    ])
    issues = check(ctx)
    assert any(i["check"] == "ADR.MissingConsequences" for i in issues)


def test_adr_undecided_status_empty_decision():
    text = "Status: Proposed\n"
    ctx = _ctx(text, [
        ("Context", "We needed to choose a database."),
        ("Decision", ""),  # empty body
        ("Consequences", "TBD."),
    ])
    issues = check(ctx)
    assert any(i["check"] == "ADR.UndecidedStatus" for i in issues)


def test_adr_undecided_status_with_body_no_issue():
    text = "Status: Proposed\n"
    ctx = _ctx(text, [
        ("Context", "We needed to choose a database."),
        ("Decision", "We will use PostgreSQL for its JSONB support."),
        ("Consequences", "Higher overhead."),
    ])
    issues = check(ctx)
    assert not any(i["check"] == "ADR.UndecidedStatus" for i in issues)


def test_adr_no_false_positive_on_plain_doc():
    text = "# My Project\n\nThis is a README.\n"
    ctx = _ctx(text, [("Introduction", "This is a README.")])
    assert check(ctx) == []


def test_adr_severity_decision_is_error():
    text = "Status: Accepted\n"
    ctx = _ctx(text, [
        ("Context", "Some context."),
        ("Consequences", "Some consequences."),
    ])
    issues = check(ctx)
    decision_issue = next(i for i in issues if i["check"] == "ADR.MissingDecision")
    assert decision_issue["severity"] == "error"
