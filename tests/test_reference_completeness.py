"""Tests for SP22 — Reference genre completeness checks."""
import pytest
from rhetoric_lint.rules.reference import check


def _ctx(text: str, genre: str = "reference", headings: list = None) -> dict:
    """Build a minimal context for reference completeness tests."""
    sections = []
    if headings:
        for h in headings:
            sections.append({
                "heading": h,
                "level": 2,
                "start": 0,
                "end": len(text),
                "topic_type": "reference",
                "paragraphs": [],
            })
    else:
        sections = [{
            "heading": "API Reference",
            "level": 1,
            "start": 0,
            "end": len(text),
            "topic_type": "reference",
            "paragraphs": [],
        }]
    return {
        "path": "test.md",
        "text": text,
        "genre": genre,
        "sections": sections,
        "nlp": None,
    }


def _checks(issues):
    return [i["check"] for i in issues]


# Minimal body text that satisfies the 150-word floor
_BODY = " ".join(["word"] * 160)


# ---------------------------------------------------------------------------
# Reference.MissingAuth
# ---------------------------------------------------------------------------

class TestMissingAuth:
    def test_flags_when_no_auth(self):
        issues = check(_ctx(_BODY))
        assert "Reference.MissingAuth" in _checks(issues)

    def test_no_flag_with_auth_heading(self):
        issues = check(_ctx(_BODY, headings=["Authentication", "Endpoints"]))
        assert "Reference.MissingAuth" not in _checks(issues)

    def test_no_flag_with_authorization_heading(self):
        issues = check(_ctx(_BODY, headings=["Authorization"]))
        assert "Reference.MissingAuth" not in _checks(issues)

    def test_no_flag_with_oauth_heading(self):
        issues = check(_ctx(_BODY, headings=["OAuth 2.0"]))
        assert "Reference.MissingAuth" not in _checks(issues)

    def test_no_flag_with_token_marker(self):
        text = _BODY + " Pass your bearer token in the Authorization header."
        issues = check(_ctx(text))
        assert "Reference.MissingAuth" not in _checks(issues)

    def test_no_flag_with_credential_marker(self):
        text = _BODY + " Store your credentials securely."
        issues = check(_ctx(text))
        assert "Reference.MissingAuth" not in _checks(issues)


# ---------------------------------------------------------------------------
# Reference.MissingRateLimit
# ---------------------------------------------------------------------------

class TestMissingRateLimit:
    def test_flags_when_no_rate_limit(self):
        issues = check(_ctx(_BODY))
        assert "Reference.MissingRateLimit" in _checks(issues)

    def test_no_flag_with_rate_limit_heading(self):
        issues = check(_ctx(_BODY, headings=["Rate Limits", "Authentication"]))
        assert "Reference.MissingRateLimit" not in _checks(issues)

    def test_no_flag_with_throttling_heading(self):
        issues = check(_ctx(_BODY, headings=["Throttling"]))
        assert "Reference.MissingRateLimit" not in _checks(issues)

    def test_no_flag_with_quota_marker(self):
        text = _BODY + " Each plan has a request quota of 1000 per day."
        issues = check(_ctx(text))
        assert "Reference.MissingRateLimit" not in _checks(issues)

    def test_no_flag_with_rate_limit_marker(self):
        text = _BODY + " The API enforces a rate limit of 100 requests per minute."
        issues = check(_ctx(text))
        assert "Reference.MissingRateLimit" not in _checks(issues)


# ---------------------------------------------------------------------------
# Reference.MissingVersioning
# ---------------------------------------------------------------------------

class TestMissingVersioning:
    def test_flags_when_no_versioning(self):
        issues = check(_ctx(_BODY))
        assert "Reference.MissingVersioning" in _checks(issues)

    def test_no_flag_with_versioning_heading(self):
        issues = check(_ctx(_BODY, headings=["Versioning", "Authentication"]))
        assert "Reference.MissingVersioning" not in _checks(issues)

    def test_no_flag_with_changelog_heading(self):
        issues = check(_ctx(_BODY, headings=["Changelog"]))
        assert "Reference.MissingVersioning" not in _checks(issues)

    def test_no_flag_with_deprecated_marker(self):
        text = _BODY + " This endpoint is deprecated and will be removed in v3."
        issues = check(_ctx(text))
        assert "Reference.MissingVersioning" not in _checks(issues)

    def test_no_flag_with_api_version_marker(self):
        text = _BODY + " Use the api version header to specify v2."
        issues = check(_ctx(text))
        assert "Reference.MissingVersioning" not in _checks(issues)


# ---------------------------------------------------------------------------
# Reference.MissingRequestExample
# ---------------------------------------------------------------------------

class TestMissingRequestExample:
    def test_flags_when_no_examples(self):
        issues = check(_ctx(_BODY))
        assert "Reference.MissingRequestExample" in _checks(issues)

    def test_no_flag_with_examples_heading(self):
        issues = check(_ctx(_BODY, headings=["Examples", "Authentication"]))
        assert "Reference.MissingRequestExample" not in _checks(issues)

    def test_no_flag_with_request_heading(self):
        issues = check(_ctx(_BODY, headings=["Request"]))
        assert "Reference.MissingRequestExample" not in _checks(issues)

    def test_no_flag_with_curl_marker(self):
        text = _BODY + " curl -X POST https://api.example.com/v1/resource"
        issues = check(_ctx(text))
        assert "Reference.MissingRequestExample" not in _checks(issues)

    def test_no_flag_with_http_method_marker(self):
        text = _BODY + " Send a POST request to the endpoint with JSON body."
        issues = check(_ctx(text))
        assert "Reference.MissingRequestExample" not in _checks(issues)


# ---------------------------------------------------------------------------
# Reference.MissingParameterTable
# ---------------------------------------------------------------------------

class TestMissingParameterTable:
    def test_flags_when_no_parameters(self):
        issues = check(_ctx(_BODY))
        assert "Reference.MissingParameterTable" in _checks(issues)

    def test_no_flag_with_parameters_heading(self):
        issues = check(_ctx(_BODY, headings=["Parameters", "Authentication"]))
        assert "Reference.MissingParameterTable" not in _checks(issues)

    def test_no_flag_with_fields_heading(self):
        issues = check(_ctx(_BODY, headings=["Fields"]))
        assert "Reference.MissingParameterTable" not in _checks(issues)

    def test_no_flag_with_properties_heading(self):
        issues = check(_ctx(_BODY, headings=["Properties"]))
        assert "Reference.MissingParameterTable" not in _checks(issues)

    def test_no_flag_with_type_and_required_marker(self):
        text = _BODY + " | Name | Type | Required | Default | Description |"
        issues = check(_ctx(text))
        assert "Reference.MissingParameterTable" not in _checks(issues)


# ---------------------------------------------------------------------------
# Genre gate: fires for reference genre and API-indicator headings
# ---------------------------------------------------------------------------

class TestGenreGate:
    def test_fires_for_reference_genre(self):
        issues = check(_ctx(_BODY, genre="reference"))
        completeness_checks = [c for c in _checks(issues) if c.startswith("Reference.Missing")]
        assert completeness_checks  # at least one fires

    def test_fires_for_api_indicator_heading_non_reference_genre(self):
        # Not reference genre, but heading contains API indicator
        issues = check(_ctx(_BODY, genre="general", headings=["Endpoint Reference"]))
        completeness_checks = [c for c in _checks(issues) if c.startswith("Reference.Missing")]
        assert completeness_checks

    def test_no_fire_for_general_genre_no_api_heading(self):
        issues = check(_ctx(_BODY, genre="general", headings=["Overview"]))
        completeness_checks = [c for c in _checks(issues) if c.startswith("Reference.Missing")]
        assert not completeness_checks

    def test_no_fire_for_howto_genre(self):
        issues = check(_ctx(_BODY, genre="howto", headings=["How to authenticate"]))
        completeness_checks = [c for c in _checks(issues) if c.startswith("Reference.Missing")]
        assert not completeness_checks

    def test_no_fire_below_word_floor(self):
        short_text = "Short document."
        issues = check(_ctx(short_text, genre="reference"))
        completeness_checks = [c for c in _checks(issues) if c.startswith("Reference.Missing")]
        assert not completeness_checks

    def test_fires_for_endpoint_indicator_heading(self):
        issues = check(_ctx(_BODY, genre="concept", headings=["API Endpoints"]))
        completeness_checks = [c for c in _checks(issues) if c.startswith("Reference.Missing")]
        assert completeness_checks

    def test_full_reference_doc_no_findings(self):
        """A well-formed reference doc with all sections fires nothing."""
        text = (
            _BODY
            + " Pass your bearer token in the Authorization header."
            + " The API enforces a rate limit of 100 requests per minute."
            + " This api version is v2. deprecated fields will be removed."
            + " curl -X POST https://api.example.com/resource"
        )
        headings = ["Authentication", "Rate Limits", "Versioning", "Examples", "Parameters"]
        issues = check(_ctx(text, headings=headings))
        completeness_checks = [c for c in _checks(issues) if c.startswith("Reference.Missing")]
        assert not completeness_checks
