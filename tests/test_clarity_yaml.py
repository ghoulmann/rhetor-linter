"""Tests for SP19 — Clarity Vale YAML pack."""
import os
import pytest
from rhetoric_lint.runners.vale_style import ValeStyleRunner

STYLE_SETS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "style-sets")
)


def _runner() -> ValeStyleRunner:
    r = ValeStyleRunner()
    r.load(style_dirs=[STYLE_SETS_DIR], enabled_styles=["Clarity"])
    return r


def _para_ctx(text: str, genre: str = "general") -> dict:
    """Context with text in a paragraph (for paragraph/text-scoped rules)."""
    return {
        "path": "test.md",
        "text": text,
        "genre": genre,
        "sections": [
            {
                "heading": "Section",
                "level": 2,
                "start": 0,
                "end": len(text),
                "topic_type": "general",
                "paragraphs": [
                    {
                        "text": text,
                        "pos": 0,
                        "line": 1,
                        "nodes": [{"type": "Paragraph", "text": text}],
                        "sentences": [],
                    }
                ],
            }
        ],
    }


def _heading_ctx(heading_text: str, genre: str = "general", body: str = "Body text.") -> dict:
    """Context with a specific heading (for heading-scoped rules)."""
    return {
        "path": "test.md",
        "text": f"## {heading_text}\n\n{body}\n",
        "genre": genre,
        "sections": [
            {
                "heading": heading_text,
                "level": 2,
                "start": 0,
                "end": len(heading_text) + len(body) + 10,
                "topic_type": "general",
                "paragraphs": [
                    {
                        "text": body,
                        "pos": len(heading_text) + 4,
                        "line": 3,
                        "nodes": [{"type": "Paragraph", "text": body}],
                        "sentences": [],
                    }
                ],
            }
        ],
    }


def _checks(issues):
    return [i["check"] for i in issues]


# ---------------------------------------------------------------------------
# Clarity.NoPlease
# ---------------------------------------------------------------------------

class TestNoPlease:
    def setup_method(self):
        self.runner = _runner()

    def test_flags_please(self):
        issues = self.runner.check(_para_ctx("Please run the install script."))
        assert any("NoPlease" in c for c in _checks(issues))

    def test_no_flag_without_please(self):
        issues = self.runner.check(_para_ctx("Run the install script."))
        assert not any("NoPlease" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# Clarity.PositiveLanguage
# ---------------------------------------------------------------------------

class TestPositiveLanguage:
    def setup_method(self):
        self.runner = _runner()

    def test_flags_cannot(self):
        issues = self.runner.check(_para_ctx("You cannot connect without a valid token."))
        assert any("PositiveLanguage" in c for c in _checks(issues))

    def test_flags_is_not_supported(self):
        issues = self.runner.check(_para_ctx("This feature is not supported in version 1."))
        assert any("PositiveLanguage" in c for c in _checks(issues))

    def test_no_flag_positive_phrasing(self):
        issues = self.runner.check(_para_ctx("Connect using a valid token."))
        assert not any("PositiveLanguage" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# Clarity.NoGerundHeadings
# ---------------------------------------------------------------------------

class TestNoGerundHeadings:
    def setup_method(self):
        self.runner = _runner()

    def test_flags_gerund_in_concept(self):
        issues = self.runner.check(_heading_ctx("Understanding the pipeline", genre="concept"))
        assert any("NoGerundHeadings" in c for c in _checks(issues))

    def test_flags_gerund_in_reference(self):
        issues = self.runner.check(_heading_ctx("Configuring the server", genre="reference"))
        assert any("NoGerundHeadings" in c for c in _checks(issues))

    def test_no_flag_in_howto(self):
        # howto is excluded from genre gate — gerund headings valid
        issues = self.runner.check(_heading_ctx("Configuring the server", genre="howto"))
        assert not any("NoGerundHeadings" in c for c in _checks(issues))

    def test_no_flag_exception_word_following(self):
        issues = self.runner.check(_heading_ctx("Following best practices", genre="concept"))
        assert not any("NoGerundHeadings" in c for c in _checks(issues))

    def test_no_flag_noun_heading(self):
        issues = self.runner.check(_heading_ctx("Authentication overview", genre="concept"))
        assert not any("NoGerundHeadings" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# Clarity.HardCodedVersions
# ---------------------------------------------------------------------------

class TestHardCodedVersions:
    def setup_method(self):
        self.runner = _runner()

    def test_flags_semver(self):
        issues = self.runner.check(_para_ctx("Install version v1.2.3 of the package."))
        assert any("HardCodedVersions" in c for c in _checks(issues))

    def test_flags_major_minor(self):
        issues = self.runner.check(_para_ctx("Requires v3.10 or higher."))
        assert any("HardCodedVersions" in c for c in _checks(issues))

    def test_no_flag_no_version(self):
        issues = self.runner.check(_para_ctx("Install the latest version of the package."))
        assert not any("HardCodedVersions" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# Clarity.HeadingLength
# ---------------------------------------------------------------------------

class TestHeadingLength:
    def setup_method(self):
        self.runner = _runner()

    def test_flags_long_heading(self):
        long = "How to configure the authentication system for your production environment safely"
        issues = self.runner.check(_heading_ctx(long))
        assert any("HeadingLength" in c for c in _checks(issues))

    def test_no_flag_short_heading(self):
        issues = self.runner.check(_heading_ctx("Authentication overview"))
        assert not any("HeadingLength" in c for c in _checks(issues))

    def test_no_flag_nine_words(self):
        # Exactly 9 words — should not fire (< 10)
        nine = "How to configure authentication for your production deployment"
        issues = self.runner.check(_heading_ctx(nine))
        assert not any("HeadingLength" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# Clarity.NoQuestionHeadings
# ---------------------------------------------------------------------------

class TestNoQuestionHeadings:
    def setup_method(self):
        self.runner = _runner()

    def test_flags_question_in_general(self):
        issues = self.runner.check(_heading_ctx("Why does this error occur?", genre="general"))
        assert any("NoQuestionHeadings" in c for c in _checks(issues))

    def test_flags_question_in_concept(self):
        issues = self.runner.check(_heading_ctx("What is a webhook?", genre="concept"))
        assert any("NoQuestionHeadings" in c for c in _checks(issues))

    def test_no_flag_in_faq(self):
        issues = self.runner.check(_heading_ctx("Why does this error occur?", genre="faq"))
        assert not any("NoQuestionHeadings" in c for c in _checks(issues))

    def test_no_flag_non_question(self):
        issues = self.runner.check(_heading_ctx("Webhook overview", genre="general"))
        assert not any("NoQuestionHeadings" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# Clarity.ParagraphSentenceCount
# ---------------------------------------------------------------------------

class TestParagraphSentenceCount:
    def setup_method(self):
        self.runner = _runner()

    def test_flags_six_sentences(self):
        text = "First. Second. Third. Fourth. Fifth. Sixth."
        issues = self.runner.check(_para_ctx(text))
        assert any("ParagraphSentenceCount" in c for c in _checks(issues))

    def test_no_flag_five_sentences(self):
        text = "First. Second. Third. Fourth. Fifth."
        issues = self.runner.check(_para_ctx(text))
        assert not any("ParagraphSentenceCount" in c for c in _checks(issues))

    def test_no_flag_two_sentences(self):
        text = "This is the first sentence. This is the second."
        issues = self.runner.check(_para_ctx(text))
        assert not any("ParagraphSentenceCount" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# Genre gate: multi-genre list support
# ---------------------------------------------------------------------------

class TestMultiGenreGate:
    def setup_method(self):
        self.runner = _runner()

    def test_no_gerund_fires_in_tutorial(self):
        issues = self.runner.check(_heading_ctx("Understanding concepts", genre="tutorial"))
        assert any("NoGerundHeadings" in c for c in _checks(issues))

    def test_no_gerund_fires_in_explanation(self):
        issues = self.runner.check(_heading_ctx("Understanding concepts", genre="explanation"))
        assert any("NoGerundHeadings" in c for c in _checks(issues))

    def test_no_question_fires_in_howto(self):
        issues = self.runner.check(_heading_ctx("Why does this fail?", genre="howto"))
        assert any("NoQuestionHeadings" in c for c in _checks(issues))

    def test_no_question_fires_in_tutorial(self):
        issues = self.runner.check(_heading_ctx("Why does this fail?", genre="tutorial"))
        assert any("NoQuestionHeadings" in c for c in _checks(issues))
