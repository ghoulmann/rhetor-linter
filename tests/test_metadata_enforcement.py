"""Tests for SP23 — Frontmatter metadata enforcement (opt-in)."""
import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock

from rhetoric_lint.rules.metadata_enforcement import check
import rhetoric_lint.const as _const


def _make_const(enabled: bool = True, stale_days: int = 183,
                valid_audiences=None) -> MagicMock:
    c = MagicMock()
    c.FRONTMATTER_ENFORCEMENT_ENABLED = enabled
    c.METADATA_STALE_DAYS = stale_days
    c.VALID_AUDIENCE_VALUES = valid_audiences or _const.VALID_AUDIENCE_VALUES
    c.RULE_SEVERITY_LEVELS = _const.RULE_SEVERITY_LEVELS
    return c


def _ctx(frontmatter: dict, enabled: bool = True, stale_days: int = 183) -> dict:
    return {
        "path": "test.md",
        "text": "Some text.",
        "genre": "general",
        "sections": [],
        "frontmatter": frontmatter,
        "const": _make_const(enabled=enabled, stale_days=stale_days),
    }


def _checks(issues):
    return [i["check"] for i in issues]


# ---------------------------------------------------------------------------
# Opt-in gate: disabled by default
# ---------------------------------------------------------------------------

class TestOptIn:
    def test_no_fire_when_disabled(self):
        issues = check(_ctx({}, enabled=False))
        assert not issues

    def test_no_fire_without_const(self):
        issues = check({"path": "test.md", "text": "", "genre": "general",
                        "sections": [], "frontmatter": {}, "const": None})
        assert not issues

    def test_fires_when_enabled(self):
        issues = check(_ctx({}))
        assert issues  # empty frontmatter fires several checks when enabled


# ---------------------------------------------------------------------------
# Metadata.MissingOwner
# ---------------------------------------------------------------------------

class TestMissingOwner:
    def test_flags_when_no_owner(self):
        issues = check(_ctx({}))
        assert "Metadata.MissingOwner" in _checks(issues)

    def test_no_flag_with_owner(self):
        issues = check(_ctx({"owner": "platform-team"}))
        assert "Metadata.MissingOwner" not in _checks(issues)

    def test_no_flag_with_owner_empty_string(self):
        # Empty string counts as absent
        issues = check(_ctx({"owner": ""}))
        assert "Metadata.MissingOwner" in _checks(issues)


# ---------------------------------------------------------------------------
# Metadata.MissingAudience
# ---------------------------------------------------------------------------

class TestMissingAudience:
    def test_flags_when_no_audience(self):
        issues = check(_ctx({}))
        assert "Metadata.MissingAudience" in _checks(issues)

    def test_no_flag_with_valid_audience(self):
        issues = check(_ctx({"audience": "developer"}))
        assert "Metadata.MissingAudience" not in _checks(issues)


# ---------------------------------------------------------------------------
# Metadata.InvalidAudience
# ---------------------------------------------------------------------------

class TestInvalidAudience:
    def test_flags_invalid_audience(self):
        issues = check(_ctx({"audience": "wizard"}))
        assert "Metadata.InvalidAudience" in _checks(issues)

    def test_no_flag_valid_audience(self):
        issues = check(_ctx({"audience": "developer"}))
        assert "Metadata.InvalidAudience" not in _checks(issues)

    def test_no_flag_valid_audience_admin(self):
        issues = check(_ctx({"audience": "admin"}))
        assert "Metadata.InvalidAudience" not in _checks(issues)

    def test_case_insensitive(self):
        # "Developer" (capitalized) should be accepted
        issues = check(_ctx({"audience": "Developer"}))
        assert "Metadata.InvalidAudience" not in _checks(issues)


# ---------------------------------------------------------------------------
# Metadata.MissingDate
# ---------------------------------------------------------------------------

class TestMissingDate:
    def test_flags_when_owner_but_no_date(self):
        issues = check(_ctx({"owner": "team-x"}))
        assert "Metadata.MissingDate" in _checks(issues)

    def test_no_flag_when_no_owner(self):
        # MissingDate only fires when owner IS present
        issues = check(_ctx({}))
        assert "Metadata.MissingDate" not in _checks(issues)

    def test_no_flag_when_owner_and_date(self):
        today = date.today().isoformat()
        issues = check(_ctx({"owner": "team-x", "date": today}))
        assert "Metadata.MissingDate" not in _checks(issues)

    def test_accepts_updated_field(self):
        today = date.today().isoformat()
        issues = check(_ctx({"owner": "team-x", "updated": today}))
        assert "Metadata.MissingDate" not in _checks(issues)


# ---------------------------------------------------------------------------
# Metadata.Stale
# ---------------------------------------------------------------------------

class TestStale:
    def test_flags_old_date(self):
        old = (date.today() - timedelta(days=200)).isoformat()
        issues = check(_ctx({"date": old}))
        assert "Metadata.Stale" in _checks(issues)

    def test_no_flag_recent_date(self):
        recent = (date.today() - timedelta(days=30)).isoformat()
        issues = check(_ctx({"date": recent}))
        assert "Metadata.Stale" not in _checks(issues)

    def test_no_flag_exactly_at_threshold(self):
        at_threshold = (date.today() - timedelta(days=183)).isoformat()
        issues = check(_ctx({"date": at_threshold}, stale_days=183))
        assert "Metadata.Stale" not in _checks(issues)

    def test_flags_one_day_past_threshold(self):
        past = (date.today() - timedelta(days=184)).isoformat()
        issues = check(_ctx({"date": past}, stale_days=183))
        assert "Metadata.Stale" in _checks(issues)

    def test_accepts_date_object(self):
        old_date = date.today() - timedelta(days=200)
        issues = check(_ctx({"date": old_date}))
        assert "Metadata.Stale" in _checks(issues)

    def test_no_flag_when_date_unparseable(self):
        issues = check(_ctx({"date": "not-a-date"}))
        assert "Metadata.Stale" not in _checks(issues)

    def test_configurable_stale_days(self):
        # 90-day threshold: 91 days old = stale
        old = (date.today() - timedelta(days=91)).isoformat()
        issues = check(_ctx({"date": old}, stale_days=90))
        assert "Metadata.Stale" in _checks(issues)
        # Same date with 180-day threshold: not stale
        issues2 = check(_ctx({"date": old}, stale_days=180))
        assert "Metadata.Stale" not in _checks(issues2)
