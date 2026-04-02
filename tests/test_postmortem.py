"""Tests for Postmortem genre classifier and Postmortem.* rules."""
from rhetoric_lint.genre import classify_genre
from rhetoric_lint.rules.postmortem import check


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sections(headings):
    return [{"heading": h, "paragraphs": [], "start": 0, "end": 0, "level": 2}
            for h in headings]


def _sections_with_body(heading_bodies):
    secs = []
    for h, body in heading_bodies:
        paras = [{"text": body, "pos": 0, "end": 0, "line": 1, "doc": None,
                  "sentences": [], "nodes": []}] if body else []
        secs.append({"heading": h, "paragraphs": paras, "start": 0, "end": 0, "level": 2})
    return secs


def _ctx(heading_bodies, text=""):
    secs = _sections_with_body(heading_bodies)
    return {"path": "incident.md", "text": text, "sections": secs}


# ---------------------------------------------------------------------------
# Genre classifier tests
# ---------------------------------------------------------------------------

def test_classifies_postmortem_by_headings():
    secs = _sections(["Timeline", "Impact", "Root Cause", "Action Items", "Lessons Learned"])
    assert classify_genre(secs, None, "") == "postmortem"


def test_postmortem_not_classified_with_two_headings():
    secs = _sections(["Timeline", "Action Items"])
    result = classify_genre(secs, None, "")
    assert result != "postmortem"


def test_postmortem_not_classified_plain_doc():
    secs = _sections(["Introduction", "Usage", "Examples"])
    result = classify_genre(secs, None, "")
    assert result != "postmortem"


# ---------------------------------------------------------------------------
# Rule tests
# ---------------------------------------------------------------------------

def test_postmortem_complete_no_issues():
    ctx = _ctx([
        ("Summary", "Service outage on 2024-01-15."),
        ("Timeline", "14:00 Alert fired. 14:10 Engineer paged."),
        ("Impact", "All users affected for 20 minutes."),
        ("Root Cause", "Database connection pool exhausted."),
        ("Action Items", "- Fix pool config @alice by 2024-02-01\n- Add alert @bob by 2024-02-15"),
    ])
    assert check(ctx) == []


def test_postmortem_missing_root_cause():
    ctx = _ctx([
        ("Timeline", "14:00 Alert fired."),
        ("Impact", "Users affected."),
        ("Action Items", "- Fix config @alice by 2024-02-01"),
    ])
    issues = check(ctx)
    assert any(i["check"] == "Postmortem.MissingRootCause" for i in issues)
    assert any(i["severity"] == "error" for i in issues
               if i["check"] == "Postmortem.MissingRootCause")


def test_postmortem_missing_action_items():
    ctx = _ctx([
        ("Timeline", "14:00 Alert fired."),
        ("Impact", "Users affected."),
        ("Root Cause", "Pool exhausted."),
    ])
    issues = check(ctx)
    assert any(i["check"] == "Postmortem.MissingActionItems" for i in issues)


def test_postmortem_missing_timeline():
    ctx = _ctx([
        ("Impact", "Users affected."),
        ("Root Cause", "Pool exhausted."),
        ("Action Items", "- Fix config @alice by 2024-02-01"),
    ])
    issues = check(ctx)
    assert any(i["check"] == "Postmortem.MissingTimeline" for i in issues)


def test_postmortem_open_action_item_no_owner_no_date():
    ctx = _ctx([
        ("Timeline", "14:00 Alert fired."),
        ("Impact", "Users affected."),
        ("Root Cause", "Pool exhausted."),
        ("Action Items", "- Fix the database configuration"),
    ])
    issues = check(ctx)
    assert any(i["check"] == "Postmortem.OpenActionItem" for i in issues)


def test_postmortem_action_item_with_owner_not_flagged():
    ctx = _ctx([
        ("Timeline", "14:00 Alert fired."),
        ("Impact", "Users affected."),
        ("Root Cause", "Pool exhausted."),
        ("Action Items", "- Fix the database configuration @alice"),
    ])
    issues = check(ctx)
    assert not any(i["check"] == "Postmortem.OpenActionItem" for i in issues)


def test_postmortem_action_item_with_date_not_flagged():
    ctx = _ctx([
        ("Timeline", "14:00 Alert fired."),
        ("Impact", "Users affected."),
        ("Root Cause", "Pool exhausted."),
        ("Action Items", "- Fix configuration by 2024-02-01"),
    ])
    issues = check(ctx)
    assert not any(i["check"] == "Postmortem.OpenActionItem" for i in issues)


def test_postmortem_no_false_positive_plain_doc():
    ctx = _ctx([
        ("Introduction", "This is a README."),
        ("Usage", "Run the app."),
    ])
    assert check(ctx) == []
