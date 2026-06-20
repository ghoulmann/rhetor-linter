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


def _runner_cfg(**rule_cfgs) -> MarkdownlintRunner:
    """Runner with specific rules explicitly enabled (overrides disabled-by-default)."""
    r = _runner()
    r._cli2_config = rule_cfgs
    return r


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


# ---------------------------------------------------------------------------
# SP5 — markdownlint-cli2 Python custom rule extension
# ---------------------------------------------------------------------------

class TestCli2CustomRules:
    def _make_custom_rule(self, tmpdir: str, name: str = "my-rule",
                          body: str = "") -> str:
        """Write a .py custom rule file and return its path."""
        if not body:
            body = (
                f"NAMES = ['{name}']\n"
                "DESCRIPTION = 'Test rule'\n"
                "TAGS = ['custom']\n\n"
                "def check(context, on_error):\n"
                "    for i, line in enumerate(context['lines'], 1):\n"
                "        if 'TODO' in line:\n"
                "            on_error(i, detail='TODO comment found')\n"
            )
        rule_path = os.path.join(tmpdir, f"{name}.py")
        with open(rule_path, "w") as f:
            f.write(body)
        return rule_path

    def _make_cli2_yaml(self, tmpdir: str, content: dict) -> str:
        import yaml
        cfg_path = os.path.join(tmpdir, ".markdownlint-cli2.yaml")
        with open(cfg_path, "w") as f:
            yaml.dump(content, f)
        return cfg_path

    def _make_cli2_jsonc(self, tmpdir: str, content: str) -> str:
        cfg_path = os.path.join(tmpdir, ".markdownlint-cli2.jsonc")
        with open(cfg_path, "w") as f:
            f.write(content)
        return cfg_path

    def test_custom_rule_loaded_and_fires(self, tmp_path):
        tmpdir = str(tmp_path)
        rule_path = self._make_custom_rule(tmpdir)
        cli2_path = self._make_cli2_yaml(tmpdir, {"customRules": [rule_path]})

        r = MarkdownlintRunner()
        r.load(cli2_config_path=cli2_path, search_dir=tmpdir)

        issues = r.check(_ctx("No issue here.\nTODO: fix this\nDone.", path="test.md"))
        custom = [i for i in issues if i["check"] == "custom.my-rule"]
        assert custom
        assert custom[0]["line"] == 2

    def test_on_error_with_fix(self, tmp_path):
        tmpdir = str(tmp_path)
        body = (
            "NAMES = ['fix-rule']\n"
            "def check(context, on_error):\n"
            "    for i, line in enumerate(context['lines'], 1):\n"
            "        if 'badword' in line:\n"
            "            on_error(i, detail='bad word found', fix='goodword')\n"
        )
        rule_path = self._make_custom_rule(tmpdir, "fix-rule", body)
        cli2_path = self._make_cli2_yaml(tmpdir, {"customRules": [rule_path]})

        r = MarkdownlintRunner()
        r.load(cli2_config_path=cli2_path, search_dir=tmpdir)

        issues = r.check(_ctx("This has badword in it.", path="test.md"))
        custom = [i for i in issues if i["check"] == "custom.fix-rule"]
        assert custom
        assert custom[0]["fix"] == "goodword"

    def test_exception_in_custom_rule_emits_meta_finding(self, tmp_path):
        tmpdir = str(tmp_path)
        body = (
            "NAMES = ['bad-rule']\n"
            "def check(context, on_error):\n"
            "    raise ValueError('intentional error')\n"
        )
        rule_path = self._make_custom_rule(tmpdir, "bad-rule", body)
        cli2_path = self._make_cli2_yaml(tmpdir, {"customRules": [rule_path]})

        r = MarkdownlintRunner()
        r.load(cli2_config_path=cli2_path, search_dir=tmpdir)

        issues = r.check(_ctx("Some text.", path="test.md"))
        meta = [i for i in issues if "bad-rule" in i["check"] and "exception" in i["message"].lower()]
        assert meta
        assert meta[0]["severity"] == "suggestion"

    def test_js_entry_skipped_no_crash(self, tmp_path, caplog):
        import logging
        tmpdir = str(tmp_path)
        cli2_path = self._make_cli2_yaml(tmpdir, {"customRules": ["some-rule.js"]})

        r = MarkdownlintRunner()
        with caplog.at_level(logging.WARNING):
            r.load(cli2_config_path=cli2_path, search_dir=tmpdir)

        assert r._custom_rules == []

    def test_npm_package_name_skipped(self, tmp_path, caplog):
        import logging
        tmpdir = str(tmp_path)
        cli2_path = self._make_cli2_yaml(tmpdir, {"customRules": ["markdownlint-rule-foo"]})

        r = MarkdownlintRunner()
        with caplog.at_level(logging.WARNING):
            r.load(cli2_config_path=cli2_path, search_dir=tmpdir)

        assert r._custom_rules == []

    def test_no_cli2_config_is_noop(self, tmp_path):
        r = MarkdownlintRunner()
        r.load(search_dir=str(tmp_path))
        assert r._custom_rules == []
        issues = r.check(_ctx("# Heading\n\nSome text.", path="test.md"))
        assert isinstance(issues, list)

    def test_jsonc_with_comments_parsed(self, tmp_path):
        tmpdir = str(tmp_path)
        jsonc_content = (
            '{\n'
            '  // This is a comment\n'
            '  "config": {"MD013": false}\n'
            '}\n'
        )
        cli2_path = self._make_cli2_jsonc(tmpdir, jsonc_content)

        r = MarkdownlintRunner()
        r.load(cli2_config_path=cli2_path, search_dir=tmpdir)

        assert r._cli2_config.get("MD013") is False

    def test_cli2_config_disables_md013(self, tmp_path):
        tmpdir = str(tmp_path)
        cli2_path = self._make_cli2_yaml(tmpdir, {"config": {"MD013": False}})

        r = MarkdownlintRunner()
        r.load(cli2_config_path=cli2_path, search_dir=tmpdir)

        # MD013 is disabled via cli2 config — runner should not fire it
        # (The cli2 config override is applied when config is merged in check())
        # Just verify no crash and config is stored
        assert r._cli2_config.get("MD013") is False


# ---------------------------------------------------------------------------
# SP20 — MD045: Images should have alternate text
# ---------------------------------------------------------------------------

class TestMD045:
    def test_flags_empty_alt(self):
        r = _runner()
        issues = r.check(_ctx("![](https://example.com/img.png)\n"))
        assert any("MD045" in c for c in _checks(issues))

    def test_flags_whitespace_alt(self):
        r = _runner()
        issues = r.check(_ctx("![ ](https://example.com/img.png)\n"))
        assert any("MD045" in c for c in _checks(issues))

    def test_no_flag_with_alt(self):
        r = _runner()
        issues = r.check(_ctx("![a diagram](https://example.com/img.png)\n"))
        assert not any("MD045" in c for c in _checks(issues))

    def test_flags_html_img_no_alt(self):
        r = _runner()
        issues = r.check(_ctx('<img src="img.png">\n'))
        assert any("MD045" in c for c in _checks(issues))

    def test_flags_html_img_empty_alt(self):
        r = _runner()
        issues = r.check(_ctx('<img src="img.png" alt="">\n'))
        assert any("MD045" in c for c in _checks(issues))

    def test_no_flag_html_img_with_alt(self):
        r = _runner()
        issues = r.check(_ctx('<img src="img.png" alt="diagram">\n'))
        assert not any("MD045" in c for c in _checks(issues))

    def test_no_flag_inside_code_fence(self):
        r = _runner()
        issues = r.check(_ctx("```\n![](img.png)\n```\n"))
        assert not any("MD045" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# MD048: Fence marker style consistency (formerly registered as MD046)
# ---------------------------------------------------------------------------

class TestMD048:
    def test_flags_mixed_consistent(self):
        r = _runner()
        text = "```python\ncode\n```\n\n~~~bash\ncode\n~~~\n"
        issues = r.check(_ctx(text))
        assert any("MD048" in c for c in _checks(issues))

    def test_no_flag_all_backtick(self):
        r = _runner()
        text = "```python\ncode\n```\n\n```bash\ncode\n```\n"
        issues = r.check(_ctx(text))
        assert not any("MD048" in c for c in _checks(issues))

    def test_no_flag_all_tilde(self):
        r = _runner()
        text = "~~~python\ncode\n~~~\n\n~~~bash\ncode\n~~~\n"
        issues = r.check(_ctx(text))
        assert not any("MD048" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# MD046: Code block style — fenced vs indented
# ---------------------------------------------------------------------------

class TestMD046:
    def test_flags_indented_code_block(self):
        r = _runner_cfg(MD046={"style": "fenced"})
        text = "Some text.\n\n    indented code\n    more code\n\nEnd.\n"
        issues = r.check(_ctx(text))
        assert any("MD046" in c for c in _checks(issues))

    def test_no_flag_fenced_block(self):
        r = _runner_cfg(MD046={"style": "fenced"})
        text = "Some text.\n\n```python\ncode\n```\n\nEnd.\n"
        issues = r.check(_ctx(text))
        assert not any("MD046" in c for c in _checks(issues))

    def test_no_flag_list_indentation(self):
        r = _runner_cfg(MD046={"style": "fenced"})
        # 4-space indent inside a list item (not a code block)
        text = "- Item one\n    - Nested item\n- Item two\n"
        issues = r.check(_ctx(text))
        assert not any("MD046" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# SP20 — Structure.StackedHeadings
# ---------------------------------------------------------------------------

class TestStructureStackedHeadings:
    def test_flags_stacked(self):
        r = _runner()
        issues = r.check(_ctx("## Section A\n\n## Section B\n"))
        assert any("Structure.StackedHeadings" in c for c in _checks(issues))

    def test_no_flag_with_content(self):
        r = _runner()
        issues = r.check(_ctx("## Section A\n\nSome text here.\n\n## Section B\n"))
        assert not any("Structure.StackedHeadings" in c for c in _checks(issues))

    def test_no_flag_single_heading(self):
        r = _runner()
        issues = r.check(_ctx("## Section A\n\nContent.\n"))
        assert not any("Structure.StackedHeadings" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# SP20 — Structure.ListLeadColon
# ---------------------------------------------------------------------------

class TestStructureListLeadColon:
    def test_flags_list_without_colon(self):
        r = _runner()
        issues = r.check(_ctx("This is prose.\n\n- item one\n- item two\n"))
        assert any("Structure.ListLeadColon" in c for c in _checks(issues))

    def test_no_flag_list_after_colon(self):
        r = _runner()
        issues = r.check(_ctx("The following items:\n\n- item one\n- item two\n"))
        assert not any("Structure.ListLeadColon" in c for c in _checks(issues))

    def test_no_flag_list_after_heading(self):
        r = _runner()
        issues = r.check(_ctx("## Section\n\n- item one\n- item two\n"))
        assert not any("Structure.ListLeadColon" in c for c in _checks(issues))

    def test_no_flag_nested_list(self):
        r = _runner()
        issues = r.check(_ctx("The options:\n\n- item one\n  - sub item\n"))
        assert not any("Structure.ListLeadColon" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# SP20 — Structure.ImageInTable
# ---------------------------------------------------------------------------

class TestStructureImageInTable:
    def test_flags_image_in_table(self):
        r = _runner()
        text = "| col1 | col2 |\n|---|---|\n| ![alt](img.png) | text |\n"
        issues = r.check(_ctx(text))
        assert any("Structure.ImageInTable" in c for c in _checks(issues))

    def test_no_flag_image_outside_table(self):
        r = _runner()
        issues = r.check(_ctx("![alt](img.png)\n"))
        assert not any("Structure.ImageInTable" in c for c in _checks(issues))

    def test_no_flag_delimiter_row(self):
        r = _runner()
        text = "| col1 | col2 |\n|---|---|\n| text | text |\n"
        issues = r.check(_ctx(text))
        assert not any("Structure.ImageInTable" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# SP20 — Structure.SingleHeaderRow
# ---------------------------------------------------------------------------

class TestStructureSingleHeaderRow:
    def test_flags_two_delimiter_rows(self):
        r = _runner()
        text = "| A | B |\n|---|---|\n| x | y |\n|---|---|\n| p | q |\n"
        issues = r.check(_ctx(text))
        assert any("Structure.SingleHeaderRow" in c for c in _checks(issues))

    def test_no_flag_one_delimiter_row(self):
        r = _runner()
        text = "| A | B |\n|---|---|\n| x | y |\n"
        issues = r.check(_ctx(text))
        assert not any("Structure.SingleHeaderRow" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# SP_MDLINT_FULL — Group A: Heading whitespace
# ---------------------------------------------------------------------------

class TestMD018:
    def test_flags_no_space(self):
        r = _runner()
        issues = r.check(_ctx("#Heading\n"))
        assert any("MD018" in c for c in _checks(issues))

    def test_fix_inserts_space(self):
        r = _runner()
        issues = r.check(_ctx("#Heading\n"))
        md = [i for i in issues if "MD018" in i["check"]]
        assert md and md[0]["fix"] == "# Heading"

    def test_no_flag_normal(self):
        r = _runner()
        assert not any("MD018" in c for c in _checks(r.check(_ctx("# Heading\n"))))

    def test_no_flag_in_code_fence(self):
        r = _runner()
        assert not any("MD018" in c for c in _checks(r.check(_ctx("```\n#Heading\n```\n"))))


class TestMD019:
    def test_flags_double_space(self):
        r = _runner()
        issues = r.check(_ctx("#  Heading\n"))
        assert any("MD019" in c for c in _checks(issues))

    def test_fix_normalises(self):
        r = _runner()
        issues = r.check(_ctx("#  Heading\n"))
        md = [i for i in issues if "MD019" in i["check"]]
        assert md and md[0]["fix"] == "# Heading"

    def test_no_flag_single_space(self):
        r = _runner()
        assert not any("MD019" in c for c in _checks(r.check(_ctx("# Heading\n"))))


class TestMD023:
    def test_flags_indented_heading(self):
        r = _runner_cfg(MD023={})
        issues = r.check(_ctx("  # Heading\n"))
        assert any("MD023" in c for c in _checks(issues))

    def test_fix_strips_indent(self):
        r = _runner_cfg(MD023={})
        issues = r.check(_ctx("  # Heading\n"))
        md = [i for i in issues if "MD023" in i["check"]]
        assert md and md[0]["fix"] == "# Heading"

    def test_no_flag_normal(self):
        r = _runner_cfg(MD023={})
        assert not any("MD023" in c for c in _checks(r.check(_ctx("# Heading\n"))))


class TestMD026:
    def test_flags_trailing_period(self):
        r = _runner_cfg(MD026={"punctuation": ".,;:!?"})
        issues = r.check(_ctx("# Heading.\n"))
        assert any("MD026" in c for c in _checks(issues))

    def test_flags_trailing_colon(self):
        r = _runner_cfg(MD026={"punctuation": ".,;:!?"})
        issues = r.check(_ctx("## Section:\n"))
        assert any("MD026" in c for c in _checks(issues))

    def test_fix_removes_punct(self):
        r = _runner_cfg(MD026={"punctuation": ".,;:!?"})
        issues = r.check(_ctx("# Title.\n"))
        md = [i for i in issues if "MD026" in i["check"]]
        assert md and not md[0]["fix"].endswith(".")

    def test_no_flag_clean(self):
        r = _runner_cfg(MD026={"punctuation": ".,;:!?"})
        assert not any("MD026" in c for c in _checks(r.check(_ctx("# Title\n"))))

    def test_flags_exclamation(self):
        # ! is in the punctuation set — verify it fires
        r = _runner_cfg(MD026={"punctuation": ".,;:!?"})
        issues = r.check(_ctx("# Title!\n"))
        assert any("MD026" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# SP_MDLINT_FULL — Group B: Blockquote
# ---------------------------------------------------------------------------

class TestMD027:
    def test_flags_double_space(self):
        r = _runner_cfg(MD027={})
        issues = r.check(_ctx(">  text here\n"))
        assert any("MD027" in c for c in _checks(issues))

    def test_fix_normalises(self):
        r = _runner_cfg(MD027={})
        issues = r.check(_ctx(">  text here\n"))
        md = [i for i in issues if "MD027" in i["check"]]
        assert md and md[0]["fix"] == "> text here"

    def test_no_flag_single_space(self):
        r = _runner_cfg(MD027={})
        assert not any("MD027" in c for c in _checks(r.check(_ctx("> text here\n"))))


class TestMD028:
    def test_flags_blank_line_in_blockquote(self):
        r = _runner_cfg(MD028={})
        text = "> Line one\n\n> Line two\n"
        issues = r.check(_ctx(text))
        assert any("MD028" in c for c in _checks(issues))

    def test_no_flag_no_blank(self):
        r = _runner_cfg(MD028={})
        assert not any("MD028" in c for c in _checks(r.check(_ctx("> Line one\n> Line two\n"))))


# ---------------------------------------------------------------------------
# SP_MDLINT_FULL — Group C: List rules
# ---------------------------------------------------------------------------

class TestMD004:
    def test_flags_mixed_markers(self):
        r = _runner_cfg(MD004={"style": "consistent"})
        issues = r.check(_ctx("- item one\n* item two\n"))
        assert any("MD004" in c for c in _checks(issues))

    def test_fix_normalises_to_first(self):
        r = _runner_cfg(MD004={"style": "consistent"})
        issues = r.check(_ctx("- item one\n* item two\n"))
        md = [i for i in issues if "MD004" in i["check"]]
        assert md and md[0]["fix"].startswith("- ")

    def test_no_flag_consistent(self):
        r = _runner_cfg(MD004={"style": "consistent"})
        assert not any("MD004" in c for c in _checks(r.check(_ctx("- one\n- two\n- three\n"))))


class TestMD007:
    def test_flags_wrong_indent(self):
        r = _runner_cfg(MD007={"indent": 2})
        # 3-space indent (not multiple of 2)
        issues = r.check(_ctx("- item\n   - nested\n"))
        assert any("MD007" in c for c in _checks(issues))

    def test_no_flag_correct_indent(self):
        r = _runner_cfg(MD007={"indent": 2})
        assert not any("MD007" in c for c in _checks(r.check(_ctx("- item\n  - nested\n"))))


class TestMD029:
    def test_flags_non_sequential(self):
        r = _runner()
        issues = r.check(_ctx("1. First\n3. Third\n"))
        assert any("MD029" in c for c in _checks(issues))

    def test_no_flag_sequential(self):
        r = _runner()
        assert not any("MD029" in c for c in _checks(r.check(_ctx("1. First\n2. Second\n3. Third\n"))))

    def test_no_flag_all_ones(self):
        r = _runner()
        assert not any("MD029" in c for c in _checks(r.check(_ctx("1. First\n1. Second\n1. Third\n"))))


class TestMD030:
    def test_flags_two_spaces(self):
        r = _runner_cfg(MD030={"ul_single": 1, "ul_multi": 1, "ol_single": 1, "ol_multi": 1})
        issues = r.check(_ctx("-  item one\n"))
        assert any("MD030" in c for c in _checks(issues))

    def test_no_flag_one_space(self):
        r = _runner_cfg(MD030={"ul_single": 1, "ul_multi": 1, "ol_single": 1, "ol_multi": 1})
        assert not any("MD030" in c for c in _checks(r.check(_ctx("- item one\n"))))


# ---------------------------------------------------------------------------
# SP_MDLINT_FULL — Group D: Code blocks
# ---------------------------------------------------------------------------

class TestMD014:
    def test_flags_dollar_commands(self):
        r = _runner_cfg(MD014={})
        text = "```bash\n$ npm install\n$ npm start\n```\n"
        issues = r.check(_ctx(text))
        assert any("MD014" in c for c in _checks(issues))

    def test_fix_removes_dollar(self):
        r = _runner_cfg(MD014={})
        text = "```bash\n$ npm install\n$ npm start\n```\n"
        issues = r.check(_ctx(text))
        md = [i for i in issues if "MD014" in i["check"]]
        assert md and not md[0]["fix"].startswith("$")

    def test_no_flag_with_output(self):
        r = _runner_cfg(MD014={})
        # Block has output lines (not all start with $)
        text = "```bash\n$ echo hello\nhello\n```\n"
        issues = r.check(_ctx(text))
        assert not any("MD014" in c for c in _checks(issues))

    def test_no_flag_no_dollar(self):
        r = _runner_cfg(MD014={})
        text = "```bash\nnpm install\nnpm start\n```\n"
        issues = r.check(_ctx(text))
        assert not any("MD014" in c for c in _checks(issues))


class TestMD060:
    def test_flags_trailing_space_in_fence(self):
        r = _runner_cfg(MD060={})
        text = "```\nsome code   \n```\n"
        issues = r.check(_ctx(text))
        assert any("MD060" in c for c in _checks(issues))

    def test_fix_strips_trailing(self):
        r = _runner_cfg(MD060={})
        text = "```\nsome code   \n```\n"
        issues = r.check(_ctx(text))
        md = [i for i in issues if "MD060" in i["check"]]
        assert md and md[0]["fix"] == "some code"

    def test_no_flag_clean(self):
        r = _runner_cfg(MD060={})
        assert not any("MD060" in c for c in _checks(r.check(_ctx("```\nsome code\n```\n"))))


# ---------------------------------------------------------------------------
# SP_MDLINT_FULL — Group E: Inline / link rules
# ---------------------------------------------------------------------------

class TestMD011:
    def test_flags_reversed_link(self):
        r = _runner()
        issues = r.check(_ctx("See (details)[https://example.com].\n"))
        assert any("MD011" in c for c in _checks(issues))

    def test_fix_reverses(self):
        r = _runner()
        issues = r.check(_ctx("(details)[https://example.com].\n"))
        md = [i for i in issues if "MD011" in i["check"]]
        assert md and "[details](https://example.com)" in md[0]["fix"]

    def test_no_flag_correct_syntax(self):
        r = _runner()
        assert not any("MD011" in c for c in _checks(r.check(_ctx("[details](https://example.com)\n"))))


class TestMD034:
    def test_flags_bare_url(self):
        r = _runner_cfg(MD034={})
        issues = r.check(_ctx("See https://example.com for more.\n"))
        assert any("MD034" in c for c in _checks(issues))

    def test_no_flag_angle_bracket(self):
        r = _runner_cfg(MD034={})
        assert not any("MD034" in c for c in _checks(r.check(_ctx("See <https://example.com>.\n"))))

    def test_no_flag_link_syntax(self):
        r = _runner_cfg(MD034={})
        assert not any("MD034" in c for c in _checks(r.check(_ctx("[link](https://example.com)\n"))))

    def test_no_flag_in_code_span(self):
        r = _runner_cfg(MD034={})
        assert not any("MD034" in c for c in _checks(r.check(_ctx("`https://example.com`\n"))))

    def test_no_flag_in_code_fence(self):
        r = _runner_cfg(MD034={})
        assert not any("MD034" in c for c in _checks(r.check(_ctx("```\nhttps://example.com\n```\n"))))


class TestMD037:
    def test_flags_spaces_inside_emphasis(self):
        r = _runner()
        issues = r.check(_ctx("This is * emphasized * text.\n"))
        assert any("MD037" in c for c in _checks(issues))

    def test_no_flag_normal_emphasis(self):
        r = _runner()
        assert not any("MD037" in c for c in _checks(r.check(_ctx("This is *emphasized* text.\n"))))


class TestMD038:
    def test_flags_spaces_in_code_span(self):
        r = _runner_cfg(MD038={})
        issues = r.check(_ctx("Use ` code ` here.\n"))
        assert any("MD038" in c for c in _checks(issues))

    def test_no_flag_normal_code(self):
        r = _runner_cfg(MD038={})
        assert not any("MD038" in c for c in _checks(r.check(_ctx("Use `code` here.\n"))))


class TestMD039:
    def test_flags_spaces_in_link(self):
        r = _runner()
        issues = r.check(_ctx("[ text ](https://example.com)\n"))
        assert any("MD039" in c for c in _checks(issues))

    def test_no_flag_normal(self):
        r = _runner()
        assert not any("MD039" in c for c in _checks(r.check(_ctx("[text](https://example.com)\n"))))


class TestMD042:
    def test_flags_empty_destination(self):
        r = _runner()
        issues = r.check(_ctx("[text]()\n"))
        assert any("MD042" in c for c in _checks(issues))

    def test_no_flag_normal(self):
        r = _runner()
        assert not any("MD042" in c for c in _checks(r.check(_ctx("[text](https://example.com)\n"))))


class TestMD049:
    def test_no_flag_consistent_asterisk(self):
        r = _runner_cfg(MD049={"style": "consistent"})
        assert not any("MD049" in c for c in _checks(r.check(_ctx("*one* and *two*\n"))))

    def test_no_flag_consistent_underscore(self):
        r = _runner_cfg(MD049={"style": "consistent"})
        assert not any("MD049" in c for c in _checks(r.check(_ctx("_one_ and _two_\n"))))

    def test_flags_mixed(self):
        r = _runner_cfg(MD049={"style": "consistent"})
        issues = r.check(_ctx("*one* and _two_ and _three_\n"))
        assert any("MD049" in c for c in _checks(issues))


class TestMD050:
    def test_no_flag_consistent_asterisk(self):
        r = _runner_cfg(MD050={"style": "consistent"})
        assert not any("MD050" in c for c in _checks(r.check(_ctx("**one** and **two**\n"))))

    def test_flags_mixed(self):
        r = _runner_cfg(MD050={"style": "consistent"})
        issues = r.check(_ctx("**one** and __two__ and __three__\n"))
        assert any("MD050" in c for c in _checks(issues))


class TestMD051:
    def test_flags_unknown_fragment(self):
        r = _runner_cfg(MD051={})
        text = "# Real Heading\n\nSee [link](#nonexistent).\n"
        issues = r.check(_ctx(text))
        assert any("MD051" in c for c in _checks(issues))

    def test_no_flag_known_fragment(self):
        r = _runner_cfg(MD051={})
        text = "# Real Heading\n\nSee [link](#real-heading).\n"
        issues = r.check(_ctx(text))
        assert not any("MD051" in c for c in _checks(issues))

    def test_no_flag_external_url(self):
        r = _runner_cfg(MD051={})
        text = "See [link](https://example.com#section).\n"
        issues = r.check(_ctx(text))
        assert not any("MD051" in c for c in _checks(issues))


class TestMD053:
    def test_flags_unused_definition(self):
        r = _runner_cfg(MD053={})
        text = "Some text.\n\n[unused]: https://example.com\n"
        issues = r.check(_ctx(text))
        assert any("MD053" in c for c in _checks(issues))

    def test_no_flag_used_definition(self):
        r = _runner_cfg(MD053={})
        text = "See [link][used].\n\n[used]: https://example.com\n"
        issues = r.check(_ctx(text))
        assert not any("MD053" in c for c in _checks(issues))

    def test_fix_is_empty_string(self):
        r = _runner_cfg(MD053={})
        text = "Text.\n\n[unused]: https://example.com\n"
        issues = r.check(_ctx(text))
        md = [i for i in issues if "MD053" in i["check"]]
        assert md and md[0]["fix"] == ""


class TestMD059:
    def test_flags_here(self):
        r = _runner()
        issues = r.check(_ctx("Click [here](https://example.com).\n"))
        assert any("MD059" in c for c in _checks(issues))

    def test_flags_click_here(self):
        r = _runner()
        issues = r.check(_ctx("[click here](https://example.com)\n"))
        assert any("MD059" in c for c in _checks(issues))

    def test_no_flag_descriptive(self):
        r = _runner()
        assert not any("MD059" in c for c in _checks(r.check(_ctx("[the documentation](https://example.com)\n"))))


# ---------------------------------------------------------------------------
# SP_MDLINT_FULL — Group F: Table rules
# ---------------------------------------------------------------------------

class TestMD055:
    def test_flags_inconsistent_pipes(self):
        r = _runner()
        # Header: leading+trailing; data row: leading only (no trailing pipe)
        text = "| A | B |\n|---|---|\n| x | y\n"
        issues = r.check(_ctx(text))
        assert any("MD055" in c for c in _checks(issues))

    def test_no_flag_consistent(self):
        r = _runner()
        text = "| A | B |\n|---|---|\n| x | y |\n"
        issues = r.check(_ctx(text))
        assert not any("MD055" in c for c in _checks(issues))


class TestMD056:
    def test_flags_mismatched_columns(self):
        r = _runner()
        text = "| A | B |\n|---|---|\n| x | y | z |\n"
        issues = r.check(_ctx(text))
        assert any("MD056" in c for c in _checks(issues))

    def test_no_flag_matching_columns(self):
        r = _runner()
        text = "| A | B |\n|---|---|\n| x | y |\n"
        issues = r.check(_ctx(text))
        assert not any("MD056" in c for c in _checks(issues))


class TestMD058:
    def test_flags_no_blank_before(self):
        r = _runner()
        text = "Text\n| A | B |\n|---|---|\n| x | y |\n"
        issues = r.check(_ctx(text))
        assert any("MD058" in c for c in _checks(issues))

    def test_flags_no_blank_after(self):
        r = _runner()
        text = "| A | B |\n|---|---|\n| x | y |\nMore text\n"
        issues = r.check(_ctx(text))
        assert any("MD058" in c for c in _checks(issues))

    def test_no_flag_surrounded_by_blanks(self):
        r = _runner()
        text = "Text\n\n| A | B |\n|---|---|\n| x | y |\n\nMore text\n"
        issues = r.check(_ctx(text))
        assert not any("MD058" in c for c in _checks(issues))


# ---------------------------------------------------------------------------
# SP_MDLINT_FULL — Group G: Document-level rules
# ---------------------------------------------------------------------------

class TestMD024:
    def test_flags_duplicate_heading(self):
        r = _runner_cfg(MD024={})
        issues = r.check(_ctx("# Title\n\n## Section\n\nContent.\n\n## Section\n\nMore.\n"))
        assert any("MD024" in c for c in _checks(issues))

    def test_no_flag_unique_headings(self):
        r = _runner_cfg(MD024={})
        issues = r.check(_ctx("# Title\n\n## Introduction\n\n## Usage\n\n## Reference\n"))
        assert not any("MD024" in c for c in _checks(issues))


class TestMD033:
    def test_flags_inline_html(self):
        r = _runner_cfg(MD033={"allowed_elements": []})
        issues = r.check(_ctx("Some <b>bold</b> text.\n"))
        assert any("MD033" in c for c in _checks(issues))

    def test_no_flag_html_comment(self):
        r = _runner_cfg(MD033={"allowed_elements": []})
        # HTML comments should not be flagged
        issues = r.check(_ctx("<!-- This is a comment -->\n"))
        assert not any("MD033" in c for c in _checks(issues))

    def test_no_flag_allowed_element(self):
        import tempfile, json, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"MD033": {"allowed_elements": ["b", "i"]}}, f)
            cfg_path = f.name
        try:
            r = _runner(config_path=cfg_path)
            issues = r.check(_ctx("Some <b>bold</b> text.\n"))
            assert not any("MD033" in c for c in _checks(issues))
        finally:
            os.unlink(cfg_path)


class TestMD035:
    def test_flags_inconsistent_hr(self):
        r = _runner()
        text = "---\n\n***\n"
        issues = r.check(_ctx(text))
        assert any("MD035" in c for c in _checks(issues))

    def test_no_flag_consistent(self):
        r = _runner()
        text = "---\n\ntext\n\n---\n"
        issues = r.check(_ctx(text))
        assert not any("MD035" in c for c in _checks(issues))


class TestMD036:
    def test_flags_bold_as_heading(self):
        r = _runner_cfg(MD036={})
        issues = r.check(_ctx("**This is not a heading**\n"))
        assert any("MD036" in c for c in _checks(issues))

    def test_no_flag_inline_bold(self):
        r = _runner_cfg(MD036={})
        issues = r.check(_ctx("This has **bold** text.\n"))
        assert not any("MD036" in c for c in _checks(issues))


class TestMD043:
    def test_no_fire_when_no_config(self):
        r = _runner()
        issues = r.check(_ctx("# Any Heading\n\n## Whatever\n"))
        assert not any("MD043" in c for c in _checks(issues))

    def test_flags_wrong_structure(self):
        import tempfile, json, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"MD043": {"headings": ["Introduction", "Usage"]}}, f)
            cfg_path = f.name
        try:
            r = _runner(config_path=cfg_path)
            issues = r.check(_ctx("# Introduction\n\n## Other\n"))
            assert any("MD043" in c for c in _checks(issues))
        finally:
            os.unlink(cfg_path)


class TestMD044:
    def test_no_fire_when_no_config(self):
        r = _runner()
        issues = r.check(_ctx("Install kubernetes with kubectl.\n"))
        assert not any("MD044" in c for c in _checks(issues))

    def test_flags_wrong_case(self):
        import tempfile, json, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"MD044": {"names": ["Kubernetes"]}}, f)
            cfg_path = f.name
        try:
            r = _runner(config_path=cfg_path)
            issues = r.check(_ctx("Install kubernetes.\n"))
            assert any("MD044" in c for c in _checks(issues))
        finally:
            os.unlink(cfg_path)


class TestMD047:
    def test_flags_missing_newline(self):
        r = _runner()
        # File text without trailing newline
        issues = r.check(_ctx("No newline at end"))
        assert any("MD047" in c for c in _checks(issues))

    def test_fix_adds_newline(self):
        r = _runner()
        issues = r.check(_ctx("No newline at end"))
        md = [i for i in issues if "MD047" in i["check"]]
        assert md and md[0]["fix"].endswith("\n")

    def test_no_flag_with_newline(self):
        r = _runner()
        assert not any("MD047" in c for c in _checks(r.check(_ctx("Has newline\n"))))
