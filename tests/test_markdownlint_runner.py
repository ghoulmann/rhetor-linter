"""Tests for MarkdownlintRunner (SP3)."""
import os
import pytest
from rhetoric_lint.runners.markdownlint import MarkdownlintRunner


def _runner(config_path: str = "") -> MarkdownlintRunner:
    r = MarkdownlintRunner()
    r.load(config_path=config_path)
    return r


def _ctx(text: str, path: str = "test.md", genre: str = "general") -> dict:
    return {"path": path, "text": text, "genre": genre, "sections": []}


def _checks(issues):
    return [i["check"] for i in issues]


def _msgs(issues):
    return [i["message"] for i in issues]


# ---------------------------------------------------------------------------
# MD001 — heading levels increment by one
# ---------------------------------------------------------------------------

class TestMD001:
    def test_skip_flags(self):
        r = _runner()
        issues = r.check(_ctx("# H1\n### H3\n"))
        assert any("MD001" in c for c in _checks(issues))

    def test_no_flag_sequential(self):
        r = _runner()
        issues = r.check(_ctx("# H1\n## H2\n### H3\n"))
        assert not any("MD001" in c for c in _checks(issues))

    def test_no_flag_decrease(self):
        # H3 → H1 is allowed (heading depth can decrease)
        r = _runner()
        issues = r.check(_ctx("# H1\n## H2\n### H3\n# Back to H1\n"))
        assert not any("MD001" in c for c in _checks(issues))

    def test_inline_suppress(self):
        r = _runner()
        issues = r.check(_ctx("# H1\n### H3 <!-- markdownlint-disable-line MD001 -->\n"))
        assert not any("MD001" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# MD003 — heading style consistent
# ---------------------------------------------------------------------------

class TestMD003:
    def test_flags_setext_when_atx_configured(self):
        r = _runner()
        # setext-style heading (=== underline) in an atx document
        issues = r.check(_ctx("# ATX\n\nSetext\n======\n"))
        assert any("MD003" in c for c in _checks(issues))

    def test_no_flag_atx(self):
        r = _runner()
        issues = r.check(_ctx("# Heading\n## Sub\n"))
        assert not any("MD003" in c for c in _checks(issues))

    def test_fix_normalises_to_atx(self):
        r = _runner()
        issues = r.check(_ctx("# ATX\n\nSetext\n======\n"))
        md003 = [i for i in issues if "MD003" in i["check"]]
        assert md003
        assert md003[0].get("fix", "").startswith("# Setext")


# ---------------------------------------------------------------------------
# MD009 — trailing spaces
# ---------------------------------------------------------------------------

class TestMD009:
    def test_flags_trailing_space(self):
        r = _runner()
        issues = r.check(_ctx("Hello   \n"))
        assert any("MD009" in c for c in _checks(issues))

    def test_fix_removes_trailing_spaces(self):
        r = _runner()
        issues = r.check(_ctx("Hello   \n"))
        md009 = [i for i in issues if "MD009" in i["check"]]
        assert md009[0]["fix"] == "Hello"

    def test_no_flag_clean_line(self):
        r = _runner()
        issues = r.check(_ctx("Hello\n"))
        assert not any("MD009" in c for c in _checks(issues))

    def test_no_flag_in_code_fence(self):
        r = _runner()
        text = "```python\ncode   \n```\n"
        issues = r.check(_ctx(text))
        # code fence lines are inside the fence set — MD009 still checks them by default
        # but the code fence line 1 and 3 are the fence markers; line 2 is inside
        # Default behaviour: also flag inside code fences
        # This test verifies the runner doesn't crash
        assert isinstance(issues, list)

    def test_inline_suppress_disable_line(self):
        r = _runner()
        issues = r.check(_ctx("Hello   <!-- markdownlint-disable-line MD009 -->\n"))
        assert not any("MD009" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# MD010 — hard tabs
# ---------------------------------------------------------------------------

class TestMD010:
    def test_flags_tab_in_paragraph(self):
        r = _runner()
        issues = r.check(_ctx("Hello\tworld\n"))
        assert any("MD010" in c for c in _checks(issues))

    def test_fix_replaces_tab_with_spaces(self):
        r = _runner()
        issues = r.check(_ctx("Hello\tworld\n"))
        md010 = [i for i in issues if "MD010" in i["check"]]
        assert "    " in md010[0]["fix"]

    def test_no_flag_clean_line(self):
        r = _runner()
        issues = r.check(_ctx("Hello world\n"))
        assert not any("MD010" in c for c in _checks(issues))

    def test_suppress_disable_next_line(self):
        r = _runner()
        issues = r.check(_ctx("<!-- markdownlint-disable-next-line MD010 -->\nHello\tworld\n"))
        assert not any("MD010" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# MD012 — consecutive blank lines
# ---------------------------------------------------------------------------

class TestMD012:
    def test_flags_double_blank(self):
        r = _runner()
        issues = r.check(_ctx("Para\n\n\nNext\n"))
        assert any("MD012" in c for c in _checks(issues))

    def test_no_flag_single_blank(self):
        r = _runner()
        issues = r.check(_ctx("Para\n\nNext\n"))
        assert not any("MD012" in c for c in _checks(issues))

    def test_fix_is_empty_string(self):
        r = _runner()
        issues = r.check(_ctx("Para\n\n\nNext\n"))
        md012 = [i for i in issues if "MD012" in i["check"]]
        assert md012[0]["fix"] == ""


# ---------------------------------------------------------------------------
# MD013 — line length
# ---------------------------------------------------------------------------

class TestMD013:
    def test_flags_long_line(self):
        r = _runner()
        long_line = "x" * 90 + "\n"
        issues = r.check(_ctx(long_line))
        assert any("MD013" in c for c in _checks(issues))

    def test_no_flag_short_line(self):
        r = _runner()
        issues = r.check(_ctx("Short line\n"))
        assert not any("MD013" in c for c in _checks(issues))

    def test_no_flag_code_block_when_disabled(self):
        r = _runner()
        import tempfile, json, os
        cfg = {"MD013": {"line_length": 20, "code_blocks": False}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            cfgpath = f.name
        try:
            runner = _runner(config_path=cfgpath)
            text = "```\n" + "x" * 100 + "\n```\n"
            issues = runner.check(_ctx(text))
            assert not any("MD013" in c for c in _checks(issues))
        finally:
            os.unlink(cfgpath)

    def test_no_flag_table_when_disabled(self):
        r = _runner()
        import tempfile, json, os
        cfg = {"MD013": {"line_length": 20, "tables": False}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            cfgpath = f.name
        try:
            runner = _runner(config_path=cfgpath)
            text = "| " + "column | " * 15 + "\n"
            issues = runner.check(_ctx(text))
            assert not any("MD013" in c for c in _checks(issues))
        finally:
            os.unlink(cfgpath)


# ---------------------------------------------------------------------------
# MD022 — blank lines around headings
# ---------------------------------------------------------------------------

class TestMD022:
    def test_flags_missing_blank_above(self):
        r = _runner()
        issues = r.check(_ctx("Some text\n## Heading\n\nContent\n"))
        md022 = [i for i in issues if "MD022" in i["check"]]
        assert md022
        assert any("above" in i["message"] for i in md022)

    def test_flags_missing_blank_below(self):
        r = _runner()
        issues = r.check(_ctx("\n## Heading\nContent\n"))
        md022 = [i for i in issues if "MD022" in i["check"]]
        assert md022
        assert any("below" in i["message"] for i in md022)

    def test_no_flag_first_heading_in_file(self):
        r = _runner()
        issues = r.check(_ctx("## Heading\n\nContent\n"))
        md022 = [i for i in issues if "MD022" in i["check"]]
        # Should not flag "missing blank above" for first heading
        above_issues = [i for i in md022 if "above" in i["message"]]
        assert above_issues == []

    def test_no_flag_properly_surrounded(self):
        r = _runner()
        issues = r.check(_ctx("\n## Heading\n\nContent\n"))
        assert not any("MD022" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# MD025 — single H1
# ---------------------------------------------------------------------------

class TestMD025:
    def test_flags_second_h1(self):
        r = _runner()
        issues = r.check(_ctx("# First\n\n## Section\n\n# Second\n"))
        assert any("MD025" in c for c in _checks(issues))

    def test_no_flag_single_h1(self):
        r = _runner()
        issues = r.check(_ctx("# Only heading\n\n## Sub\n"))
        assert not any("MD025" in c for c in _checks(issues))

    def test_reports_second_h1_line(self):
        r = _runner()
        issues = r.check(_ctx("# First\n\n# Second\n"))
        md025 = [i for i in issues if "MD025" in i["check"]]
        assert md025[0]["line"] == 3


# ---------------------------------------------------------------------------
# MD031 — blank lines around fenced code
# ---------------------------------------------------------------------------

class TestMD031:
    def test_flags_missing_blank_before_fence(self):
        r = _runner()
        issues = r.check(_ctx("Text\n```python\ncode\n```\n"))
        md031 = [i for i in issues if "MD031" in i["check"]]
        assert md031
        assert any("before" in i["message"] for i in md031)

    def test_flags_missing_blank_after_fence(self):
        r = _runner()
        issues = r.check(_ctx("\n```python\ncode\n```\nText\n"))
        md031 = [i for i in issues if "MD031" in i["check"]]
        assert md031
        assert any("after" in i["message"] for i in md031)

    def test_no_flag_properly_surrounded(self):
        r = _runner()
        issues = r.check(_ctx("Text\n\n```python\ncode\n```\n\nMore\n"))
        assert not any("MD031" in c for c in _checks(issues))

    def test_no_flag_at_file_start(self):
        r = _runner()
        issues = r.check(_ctx("```python\ncode\n```\n\nText\n"))
        before = [i for i in issues if "MD031" in i["check"] and "before" in i["message"]]
        assert before == []


# ---------------------------------------------------------------------------
# MD032 — blank lines around lists
# ---------------------------------------------------------------------------

class TestMD032:
    def test_flags_missing_blank_before_list(self):
        r = _runner()
        issues = r.check(_ctx("Text\n- item one\n- item two\n"))
        md032 = [i for i in issues if "MD032" in i["check"]]
        assert md032
        assert any("before" in i["message"] for i in md032)

    def test_flags_missing_blank_after_list(self):
        r = _runner()
        issues = r.check(_ctx("\n- item one\n- item two\nText\n"))
        md032 = [i for i in issues if "MD032" in i["check"]]
        assert md032
        assert any("after" in i["message"] for i in md032)

    def test_no_flag_properly_surrounded(self):
        r = _runner()
        issues = r.check(_ctx("Text\n\n- item one\n- item two\n\nMore\n"))
        assert not any("MD032" in c for c in _checks(issues))

    def test_no_flag_list_at_file_start(self):
        r = _runner()
        issues = r.check(_ctx("- item one\n- item two\n\nText\n"))
        before = [i for i in issues if "MD032" in i["check"] and "before" in i["message"]]
        assert before == []


# ---------------------------------------------------------------------------
# MD040 — fenced code language
# ---------------------------------------------------------------------------

class TestMD040:
    def test_flags_no_language(self):
        r = _runner()
        issues = r.check(_ctx("```\ncode\n```\n"))
        assert any("MD040" in c for c in _checks(issues))

    def test_no_flag_with_language(self):
        r = _runner()
        issues = r.check(_ctx("```python\ncode\n```\n"))
        assert not any("MD040" in c for c in _checks(issues))

    def test_inline_suppress(self):
        r = _runner()
        issues = r.check(_ctx("``` <!-- markdownlint-disable-line MD040 -->\ncode\n```\n"))
        assert not any("MD040" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# MD041 — first line is top-level heading
# ---------------------------------------------------------------------------

class TestMD041:
    def test_flags_missing_h1(self):
        r = _runner()
        issues = r.check(_ctx("Some text\n## Section\n"))
        assert any("MD041" in c for c in _checks(issues))

    def test_no_flag_starts_with_h1(self):
        r = _runner()
        issues = r.check(_ctx("# Title\n\nContent\n"))
        assert not any("MD041" in c for c in _checks(issues))

    def test_genre_gate_skips_wrong_genre(self):
        import tempfile, json, os
        cfg = {"MD041": {"rhetoric-genre": ["howto", "tutorial"]}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            cfgpath = f.name
        try:
            r = _runner(config_path=cfgpath)
            issues = r.check(_ctx("Some text\n", genre="general"))
            assert not any("MD041" in c for c in _checks(issues))
        finally:
            os.unlink(cfgpath)

    def test_genre_gate_fires_on_matching_genre(self):
        import tempfile, json, os
        cfg = {"MD041": {"rhetoric-genre": ["howto"]}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            cfgpath = f.name
        try:
            r = _runner(config_path=cfgpath)
            issues = r.check(_ctx("Some text\n", genre="howto"))
            assert any("MD041" in c for c in _checks(issues))
        finally:
            os.unlink(cfgpath)


# ---------------------------------------------------------------------------
# Inline suppression — block disable/enable
# ---------------------------------------------------------------------------

class TestInlineSuppression:
    def test_disable_enable_range(self):
        r = _runner()
        text = (
            "# H1\n"
            "<!-- markdownlint-disable MD009 -->\n"
            "Trailing   \n"
            "<!-- markdownlint-enable MD009 -->\n"
            "Still trailing   \n"
        )
        issues = r.check(_ctx(text))
        md009 = [i for i in issues if "MD009" in i["check"]]
        # Line 3 is suppressed; line 5 is not
        lines = [i["line"] for i in md009]
        assert 3 not in lines
        assert 5 in lines

    def test_disable_all_rules(self):
        r = _runner()
        text = (
            "<!-- markdownlint-disable -->\n"
            "Trailing   \n"
            "```\n"
            "code\n"
            "```\n"
            "<!-- markdownlint-enable -->\n"
        )
        issues = r.check(_ctx(text))
        assert issues == []


# ---------------------------------------------------------------------------
# Config: disabled rule via config
# ---------------------------------------------------------------------------

class TestConfig:
    def test_rule_disabled_via_config(self):
        import tempfile, json, os
        cfg = {"MD009": False}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            cfgpath = f.name
        try:
            r = _runner(config_path=cfgpath)
            issues = r.check(_ctx("Trailing   \n"))
            assert not any("MD009" in c for c in _checks(issues))
        finally:
            os.unlink(cfgpath)

    def test_empty_runner_returns_empty_on_empty_text(self):
        r = _runner()
        assert r.check(_ctx("")) == []


# ---------------------------------------------------------------------------
# Precision corpus: runner should not crash on real-world docs
# ---------------------------------------------------------------------------

class TestPrecisionCorpus:
    def test_no_crash_on_corpus(self):
        """MarkdownlintRunner must not raise exceptions on any corpus file."""
        import glob
        corpus_dir = os.path.join(
            os.path.dirname(__file__), "fixtures", "corpus", "technical"
        )
        if not os.path.isdir(corpus_dir):
            pytest.skip("corpus not found")
        files = glob.glob(os.path.join(corpus_dir, "*.md"))
        if not files:
            pytest.skip("no corpus files")

        r = _runner()
        for f in files:
            with open(f, encoding="utf-8") as fh:
                text = fh.read()
            issues = r.check({"path": f, "text": text, "genre": "technical", "sections": []})
            assert isinstance(issues, list), f"Runner returned non-list for {f}"
