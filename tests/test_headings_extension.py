"""Tests for SP21 — Heading.SiblingParallelism."""
import pytest

try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
    _SPACY_OK = True
except Exception:
    _nlp = None
    _SPACY_OK = False

from rhetoric_lint.rules.headings import check
import rhetoric_lint.const as _const


def _h(level: int, text: str, pos: int = 0) -> dict:
    return {"level": level, "heading": text, "start": pos, "end": pos + 100,
            "topic_type": "general", "paragraphs": []}


def _ctx(sections: list, nlp=None) -> dict:
    text = "\n".join(
        "#" * s["level"] + " " + s["heading"] for s in sections
    )
    return {
        "path": "test.md",
        "text": text,
        "genre": "general",
        "sections": sections,
        "nlp": nlp,
        "const": _const,
    }


def _sibling_checks(issues):
    return [i for i in issues if i["check"] == "Heading.SiblingParallelism"]


# ---------------------------------------------------------------------------
# Heading.SiblingParallelism
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _SPACY_OK, reason="spaCy model not available")
class TestHeadingSiblingParallelism:

    def test_flags_noun_outlier_in_verb_group(self):
        # 3 verb-led + 1 noun-led → noun is minority
        sections = [
            _h(1, "API Reference", pos=0),
            _h(2, "Configure the client", pos=20),
            _h(2, "Install the package", pos=60),
            _h(2, "Deploy to production", pos=100),
            _h(2, "Authentication overview", pos=140),  # noun-led — minority
        ]
        issues = _sibling_checks(check(_ctx(sections, nlp=_nlp)))
        assert issues
        assert any("Authentication overview" in i["message"] for i in issues)

    def test_flags_verb_outlier_in_noun_group(self):
        # 3 noun-led + 1 verb-led → verb is minority
        sections = [
            _h(1, "SDK Reference", pos=0),
            _h(2, "Authentication", pos=20),
            _h(2, "Rate limits", pos=60),
            _h(2, "Versioning", pos=100),
            _h(2, "Configure your client", pos=140),  # verb-led — minority
        ]
        issues = _sibling_checks(check(_ctx(sections, nlp=_nlp)))
        assert issues
        assert any("Configure your client" in i["message"] for i in issues)

    def test_no_flag_when_all_verb_led(self):
        sections = [
            _h(1, "Getting started", pos=0),
            _h(2, "Install the package", pos=20),
            _h(2, "Configure the client", pos=60),
            _h(2, "Deploy to production", pos=100),
        ]
        issues = _sibling_checks(check(_ctx(sections, nlp=_nlp)))
        assert not issues

    def test_no_flag_when_all_noun_led(self):
        sections = [
            _h(1, "API Reference", pos=0),
            _h(2, "Authentication", pos=20),
            _h(2, "Rate limits", pos=60),
            _h(2, "Versioning", pos=100),
        ]
        issues = _sibling_checks(check(_ctx(sections, nlp=_nlp)))
        assert not issues

    def test_no_flag_below_min_group(self):
        # Only 2 H2s under the H1 — below HEADING_PARALLELISM_MIN_GROUP (3)
        sections = [
            _h(1, "API Reference", pos=0),
            _h(2, "Authentication", pos=20),
            _h(2, "Configure the client", pos=60),
        ]
        issues = _sibling_checks(check(_ctx(sections, nlp=_nlp)))
        assert not issues

    def test_no_flag_when_split_not_minority(self):
        # 3 verb-led, 2 noun-led → minority (noun) is 2/5 = 40% ≥ 33% → no flag
        sections = [
            _h(1, "API Reference", pos=0),
            _h(2, "Authentication", pos=20),
            _h(2, "Authorization", pos=60),
            _h(2, "Configure the client", pos=100),
            _h(2, "Install the package", pos=140),
            _h(2, "Deploy to production", pos=180),
        ]
        issues = _sibling_checks(check(_ctx(sections, nlp=_nlp)))
        assert not issues

    def test_groups_reset_per_h1(self):
        # Two H1 sections; each has a consistent group — no flags expected
        sections = [
            _h(1, "Setup", pos=0),
            _h(2, "Install the package", pos=20),
            _h(2, "Configure the client", pos=60),
            _h(2, "Deploy to production", pos=100),
            _h(1, "Reference", pos=140),
            _h(2, "Authentication", pos=160),
            _h(2, "Rate limits", pos=200),
            _h(2, "Versioning", pos=240),
        ]
        issues = _sibling_checks(check(_ctx(sections, nlp=_nlp)))
        assert not issues

    def test_no_flag_without_nlp(self):
        # Without spaCy, rule should not fire (silently skipped)
        sections = [
            _h(1, "API Reference", pos=0),
            _h(2, "Configure the client", pos=20),
            _h(2, "Install the package", pos=60),
            _h(2, "Deploy to production", pos=100),
            _h(2, "Authentication overview", pos=140),
        ]
        issues = _sibling_checks(check(_ctx(sections, nlp=None)))
        assert not issues
