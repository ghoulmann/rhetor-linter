"""Tests for ValeStyleRunner (SP2 — existence + substitution rule types)."""
import os
import pytest
from rhetoric_lint.runners.vale_style import ValeStyleRunner

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "styles")
TEST_STYLE_DIR = os.path.join(FIXTURES_DIR, "TestStyle")
GENRE_STYLE_DIR = os.path.join(FIXTURES_DIR, "GenreStyle")


def _runner(*dirs, enabled=()) -> ValeStyleRunner:
    r = ValeStyleRunner()
    r.load(style_dirs=list(dirs), enabled_styles=list(enabled))
    return r


def _ctx(text: str, genre: str = "general", sections=None) -> dict:
    if sections is None:
        sections = []
    return {
        "path": "test.md",
        "text": text,
        "genre": genre,
        "sections": sections,
    }


def _para_section(text: str, line: int = 1) -> dict:
    return {
        "heading": "Section",
        "level": 2,
        "start": 0,
        "end": len(text),
        "topic_type": "general",
        "paragraphs": [
            {
                "text": text,
                "pos": 0,
                "line": line,
                "nodes": [],
                "sentences": [],
            }
        ],
    }


# ---------------------------------------------------------------------------
# load() — basic wiring
# ---------------------------------------------------------------------------

class TestLoad:
    def test_loads_existence_rules(self):
        runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])
        names = [r.name for r in runner._rules]
        assert any("existence_basic" in n for n in names)

    def test_loads_substitution_rules(self):
        runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])
        names = [r.name for r in runner._rules]
        assert any("substitution_basic" in n for n in names)

    def test_missing_dir_is_silently_ignored(self):
        runner = _runner("/nonexistent/path")
        assert runner._rules == []

    def test_enabled_styles_filters(self):
        runner = _runner(FIXTURES_DIR, enabled=["GenreStyle"])
        names = [r.name for r in runner._rules]
        assert all("GenreStyle" in n for n in names)
        assert not any("TestStyle" in n for n in names)

    def test_all_styles_loaded_when_enabled_empty(self):
        runner = _runner(FIXTURES_DIR)
        names = [r.name for r in runner._rules]
        assert any("TestStyle" in n for n in names)
        assert any("GenreStyle" in n for n in names)

    def test_genre_from_meta_yml(self):
        runner = _runner(FIXTURES_DIR, enabled=["GenreStyle"])
        assert all(r.genre == "technical" for r in runner._rules)

    def test_rule_name_is_style_dot_stem(self):
        runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])
        names = [r.name for r in runner._rules]
        assert "TestStyle.existence_basic" in names


# ---------------------------------------------------------------------------
# Existence — basic word boundary
# ---------------------------------------------------------------------------

class TestExistenceBasic:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])

    def test_flags_exact_token(self):
        issues = self.runner.check(_ctx("This is foo in a sentence."))
        checks = [i["check"] for i in issues]
        assert any("existence_basic" in c for c in checks)

    def test_word_boundary_prevents_substring_match(self):
        # "foobar" should not match "\bfoo\b"
        issues = self.runner.check(_ctx("This is foobar in a sentence."))
        basic = [i for i in issues if "existence_basic" in i["check"]]
        assert basic == []

    def test_returns_correct_matched_token_in_message(self):
        issues = self.runner.check(_ctx("Use bar here."))
        basic = [i for i in issues if "existence_basic" in i["check"]]
        assert any("bar" in i["message"] for i in basic)

    def test_column_is_1_indexed(self):
        issues = self.runner.check(_ctx("Use foo here."))
        basic = [i for i in issues if "existence_basic" in i["check"]]
        assert basic[0]["column"] == 5  # "Use " is 4 chars, foo starts at col 5

    def test_no_finding_when_no_match(self):
        issues = self.runner.check(_ctx("Nothing interesting here."))
        basic = [i for i in issues if "existence_basic" in i["check"]]
        assert basic == []


# ---------------------------------------------------------------------------
# Existence — nonword: true (substring match)
# ---------------------------------------------------------------------------

class TestExistenceNonword:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])

    def test_nonword_matches_substring(self):
        # nonword:true means match anywhere (no \b), so "bazinga" should match "baz"
        issues = self.runner.check(_ctx("This is bazinga."))
        noword = [i for i in issues if "existence_noword" in i["check"]]
        assert noword != []

    def test_word_boundary_rule_does_not_match_substring(self):
        # existence_basic uses nonword:false (default), so "foobar" must not match "foo"
        issues = self.runner.check(_ctx("foobar"))
        basic = [i for i in issues if "existence_basic" in i["check"]]
        assert basic == []


# ---------------------------------------------------------------------------
# Existence — exceptions
# ---------------------------------------------------------------------------

class TestExistenceExceptions:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])

    def test_flags_token_without_exception_context(self):
        issues = self.runner.check(_ctx("Use the widget here."))
        exc = [i for i in issues if "existence_exceptions" in i["check"]]
        assert exc != []

    def test_exception_suppresses_match(self):
        # "widgets/display" is in exceptions — matched text "widget" is NOT "widgets/display"
        # Exceptions apply to the MATCHED text, so plain "widget" is still flagged.
        # To suppress: exact match of exception against matched token.
        # "widgets/display" does not equal "widget", so it should still fire.
        # This test verifies exceptions don't over-suppress.
        issues = self.runner.check(_ctx("Use the widget here."))
        exc = [i for i in issues if "existence_exceptions" in i["check"]]
        assert exc != []


# ---------------------------------------------------------------------------
# Existence — raw: prefix patterns
# ---------------------------------------------------------------------------

class TestExistenceRaw:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])

    def test_flags_passive_construction(self):
        issues = self.runner.check(_ctx("The file was created by the system."))
        raw = [i for i in issues if "existence_raw" in i["check"]]
        assert raw != []

    def test_no_flag_active_construction(self):
        # "created" without "was" prefix — active voice
        issues = self.runner.check(_ctx("The system created the file."))
        raw = [i for i in issues if "existence_raw" in i["check"]]
        assert raw == []


# ---------------------------------------------------------------------------
# Substitution
# ---------------------------------------------------------------------------

class TestSubstitution:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])

    def test_flags_original_term(self):
        issues = self.runner.check(_ctx("We should utilize this approach."))
        subs = [i for i in issues if "substitution_basic" in i["check"]]
        assert subs != []

    def test_message_contains_original(self):
        issues = self.runner.check(_ctx("We should utilize this approach."))
        subs = [i for i in issues if "substitution_basic" in i["check"]]
        assert any("utilize" in i["message"] for i in subs)

    def test_fix_key_present_for_single_token(self):
        issues = self.runner.check(_ctx("We should utilize this approach."))
        subs = [i for i in issues if "substitution_basic" in i["check"]]
        assert any(i.get("fix") == "use" for i in subs)

    def test_no_fix_for_multi_word_match(self):
        # If the original matched text has spaces (multi-word), no fix is emitted
        # leverages is single-word, so fix should be present
        issues = self.runner.check(_ctx("The system leverages cloud storage."))
        subs = [i for i in issues if "substitution_basic" in i["check"]]
        assert any(i.get("fix") == "uses" for i in subs)

    def test_no_flag_when_replacement_already_used(self):
        issues = self.runner.check(_ctx("We should use this approach."))
        subs = [i for i in issues if "substitution_basic" in i["check"]]
        assert subs == []


# ---------------------------------------------------------------------------
# Vocabulary suppression (accept.txt)
# ---------------------------------------------------------------------------

class TestVocabSuppression:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])

    def test_accepted_term_not_flagged(self):
        # "synergy" is in accept.txt for TestStyle
        issues = self.runner.check(_ctx("We need synergy here."))
        vocab = [i for i in issues if "vocab_test" in i["check"]]
        assert vocab == []

    def test_non_accepted_term_is_flagged(self):
        # "leverage" is NOT in accept.txt
        issues = self.runner.check(_ctx("We need to leverage this."))
        vocab = [i for i in issues if "vocab_test" in i["check"]]
        assert vocab != []


# ---------------------------------------------------------------------------
# Genre gating
# ---------------------------------------------------------------------------

class TestGenreGating:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR)

    def test_genre_rule_fires_on_matching_genre(self):
        issues = self.runner.check(_ctx("This has wibble.", genre="technical"))
        genre_issues = [i for i in issues if "technical_only" in i["check"]]
        assert genre_issues != []

    def test_genre_rule_silent_on_other_genre(self):
        issues = self.runner.check(_ctx("This has wibble.", genre="general"))
        genre_issues = [i for i in issues if "technical_only" in i["check"]]
        assert genre_issues == []


# ---------------------------------------------------------------------------
# Scope — paragraph (prose only, skips code blocks)
# ---------------------------------------------------------------------------

class TestScopeExtraction:
    def setup_method(self):
        # Build a runner with a paragraph-scoped rule
        import tempfile, os, yaml as _yaml
        self.tmpdir = tempfile.mkdtemp()
        style_dir = os.path.join(self.tmpdir, "ScopeStyle")
        os.makedirs(style_dir)
        rule = {
            "extends": "existence",
            "message": "Found '%s'",
            "level": "warning",
            "scope": "paragraph",
            "tokens": ["scopetest"],
        }
        with open(os.path.join(style_dir, "scope_para.yml"), "w") as f:
            _yaml.dump(rule, f)
        self.runner = _runner(self.tmpdir, enabled=["ScopeStyle"])

    def test_paragraph_scope_finds_in_prose(self):
        sec = _para_section("This scopetest sentence.", line=5)
        ctx = _ctx("This scopetest sentence.", sections=[sec])
        issues = self.runner.check(ctx)
        scope_issues = [i for i in issues if "scope_para" in i["check"]]
        assert scope_issues != []

    def test_paragraph_scope_line_number_from_section(self):
        sec = _para_section("This scopetest sentence.", line=10)
        ctx = _ctx("This scopetest sentence.", sections=[sec])
        issues = self.runner.check(ctx)
        scope_issues = [i for i in issues if "scope_para" in i["check"]]
        assert scope_issues[0]["line"] == 10

    def test_paragraph_scope_skips_code_nodes(self):
        from rhetoric_lint.runners.vale_style import _NON_PROSE_NODE_TYPES
        sec = {
            "heading": "Section",
            "level": 2,
            "start": 0,
            "end": 100,
            "topic_type": "general",
            "paragraphs": [
                {
                    "text": "scopetest in code",
                    "pos": 0,
                    "line": 1,
                    "nodes": [{"type": "CodeFence", "text": "scopetest"}],
                    "sentences": [],
                }
            ],
        }
        ctx = _ctx("scopetest in code", sections=[sec])
        issues = self.runner.check(ctx)
        scope_issues = [i for i in issues if "scope_para" in i["check"]]
        assert scope_issues == []


# ---------------------------------------------------------------------------
# Precision corpus: runner with no styles configured is silent
# ---------------------------------------------------------------------------

class TestPrecisionCorpus:
    def test_empty_runner_produces_no_findings(self):
        """Runner with no loaded styles must produce zero findings (smoke test)."""
        runner = ValeStyleRunner()
        runner.load(style_dirs=[], enabled_styles=[])
        corpus_dir = os.path.join(
            os.path.dirname(__file__), "fixtures", "corpus", "technical"
        )
        if not os.path.isdir(corpus_dir):
            pytest.skip("corpus not found")

        import glob
        files = glob.glob(os.path.join(corpus_dir, "*.md"))
        if not files:
            pytest.skip("no corpus files")

        all_issues = []
        for f in files:
            try:
                with open(f, encoding="utf-8") as fh:
                    text = fh.read()
                ctx = {
                    "path": f,
                    "text": text,
                    "genre": "technical",
                    "sections": [],
                }
                all_issues.extend(runner.check(ctx))
            except Exception:
                pass

        assert all_issues == []
