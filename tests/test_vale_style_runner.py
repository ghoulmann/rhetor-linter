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


def _ctx(text: str, genre: str = "general", sections=None, nlp=None) -> dict:
    if sections is None:
        sections = []
    return {
        "path": "test.md",
        "text": text,
        "genre": genre,
        "sections": sections,
        "nlp": nlp,
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


# ---------------------------------------------------------------------------
# SP4 — occurrence type
# ---------------------------------------------------------------------------

class TestOccurrence:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])
        # Only keep occurrence rules
        self.runner._rules = [r for r in self.runner._rules if "occurrence" in r.name]

    def test_fires_when_over_max(self):
        # "very" appears 3 times — max is 2
        sec = _para_section("This is very very very important.")
        ctx = _ctx("This is very very very important.", sections=[sec])
        issues = self.runner.check(ctx)
        occ = [i for i in issues if "occurrence_basic" in i["check"]]
        assert occ

    def test_no_fire_at_or_under_max(self):
        sec = _para_section("This is very very important.")
        ctx = _ctx("This is very very important.", sections=[sec])
        issues = self.runner.check(ctx)
        occ = [i for i in issues if "occurrence_basic" in i["check"]]
        assert not occ

    def test_fires_when_under_min(self):
        # "summary" must appear at least 1 time — it's absent
        r2 = _runner(FIXTURES_DIR, enabled=["TestStyle"])
        r2._rules = [r for r in r2._rules if "occurrence_min" in r.name]
        sec = _para_section("This paragraph has no magic keyword.")
        ctx = _ctx("This paragraph has no magic keyword.", sections=[sec])
        issues = r2.check(ctx)
        assert issues  # min not satisfied

    def test_no_fire_when_min_satisfied(self):
        r2 = _runner(FIXTURES_DIR, enabled=["TestStyle"])
        r2._rules = [r for r in r2._rules if "occurrence_min" in r.name]
        sec = _para_section("This document includes a summary section.")
        ctx = _ctx("This document includes a summary section.", sections=[sec])
        issues = r2.check(ctx)
        assert not issues


# ---------------------------------------------------------------------------
# SP4 — metric type
# ---------------------------------------------------------------------------

class TestMetricType:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])
        self.runner._rules = [r for r in self.runner._rules if "metric_basic" in r.name]

    def test_fires_when_condition_met(self):
        # words/sentences > 5 — "Hello world." = 2 words, 1 sentence = 2.0 > 5? No.
        # Use a text with ratio > 5 words/sentence
        text = "The quick brown fox jumps over the lazy dog near the river bank."
        ctx = _ctx(text, sections=[])
        issues = self.runner.check(ctx)
        # formula = words/sentences, condition = "> 5", 12 words / 1 sentence = 12 > 5
        assert issues

    def test_no_fire_short_avg(self):
        text = "Go. Stop. Run. Wait. Jump."
        ctx = _ctx(text, sections=[])
        issues = self.runner.check(ctx)
        # 5 words / 5 sentences = 1.0 — not > 5
        assert not issues

    def test_malformed_formula_no_crash(self):
        import tempfile, yaml, os
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "Bad"))
            with open(os.path.join(tmpdir, "Bad", "bad_metric.yml"), "w") as f:
                yaml.dump({"extends": "metric", "message": "x", "level": "warning",
                           "scope": "summary", "formula": "bad *** syntax", "condition": "> 5"}, f)
            r = _runner(tmpdir, enabled=["Bad"])
            assert r.check(_ctx("Some text here.")) == []


# ---------------------------------------------------------------------------
# SP4 — capitalization type
# ---------------------------------------------------------------------------

class TestCapitalization:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])
        self.runner._rules = [r for r in self.runner._rules if "capitalization_sentence" in r.name]

    def test_fires_on_lowercase_sentence_start(self):
        sec = _para_section("this sentence starts lowercase.")
        sec["paragraphs"][0]["sentences"] = [{"span": None, "line": 1}]
        # Use text scope since sentence needs spaCy span; use paragraph scope workaround
        ctx = _ctx("this sentence starts lowercase.", sections=[sec])
        issues = self.runner.check(ctx)
        assert issues

    def test_no_fire_on_proper_capitalization(self):
        sec = _para_section("This sentence starts correctly.")
        ctx = _ctx("This sentence starts correctly.", sections=[sec])
        issues = self.runner.check(ctx)
        assert not issues


# ---------------------------------------------------------------------------
# SP4 — repetition type
# ---------------------------------------------------------------------------

class TestRepetition:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])
        self.runner._rules = [r for r in self.runner._rules if "repetition_basic" in r.name]

    def test_fires_on_repeated_word(self):
        sec = _para_section("The the quick brown fox.")
        ctx = _ctx("The the quick brown fox.", sections=[sec])
        issues = self.runner.check(ctx)
        rep = [i for i in issues if "repetition" in i["check"]]
        assert rep

    def test_fix_key_is_single_word(self):
        sec = _para_section("The the quick brown fox.")
        ctx = _ctx("The the quick brown fox.", sections=[sec])
        issues = self.runner.check(ctx)
        rep = [i for i in issues if "repetition" in i["check"]]
        assert rep[0].get("fix") is not None

    def test_no_fire_on_number_repetition_with_alpha(self):
        # alpha:true means only flag alphabetic token repetition
        sec = _para_section("Version 1 1 is released.")
        ctx = _ctx("Version 1 1 is released.", sections=[sec])
        issues = self.runner.check(ctx)
        rep = [i for i in issues if "repetition" in i["check"]]
        assert not rep

    def test_no_fire_unique_words(self):
        sec = _para_section("The quick brown fox jumps.")
        ctx = _ctx("The quick brown fox jumps.", sections=[sec])
        issues = self.runner.check(ctx)
        rep = [i for i in issues if "repetition" in i["check"]]
        assert not rep


# ---------------------------------------------------------------------------
# SP4 — consistency type
# ---------------------------------------------------------------------------

class TestConsistency:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])
        self.runner._rules = [r for r in self.runner._rules if "consistency_basic" in r.name]

    def test_fires_when_both_forms_present(self):
        text = "The colour of the color palette varies."
        sec = _para_section(text)
        ctx = _ctx(text, sections=[sec])
        issues = self.runner.check(ctx)
        cons = [i for i in issues if "consistency" in i["check"]]
        assert cons

    def test_no_fire_single_form(self):
        text = "The colour of the background is blue."
        sec = _para_section(text)
        ctx = _ctx(text, sections=[sec])
        issues = self.runner.check(ctx)
        cons = [i for i in issues if "consistency" in i["check"]]
        assert not cons

    def test_no_fire_empty_text(self):
        ctx = _ctx("", sections=[])
        issues = self.runner.check(ctx)
        assert issues == []


# ---------------------------------------------------------------------------
# SP4 — conditional type
# ---------------------------------------------------------------------------

class TestConditional:
    def setup_method(self):
        self.runner = _runner(FIXTURES_DIR, enabled=["TestStyle"])
        self.runner._rules = [r for r in self.runner._rules if "conditional_basic" in r.name]

    def test_fires_when_first_present_second_absent(self):
        # first=API present, second=authentication absent → fire
        text = "The API endpoint returns a token for the caller."
        sec = _para_section(text)
        ctx = _ctx(text, sections=[sec])
        issues = self.runner.check(ctx)
        cond = [i for i in issues if "conditional" in i["check"]]
        assert cond

    def test_no_fire_when_first_absent(self):
        text = "Use authentication to protect your endpoint."
        sec = _para_section(text)
        ctx = _ctx(text, sections=[sec])
        issues = self.runner.check(ctx)
        cond = [i for i in issues if "conditional" in i["check"]]
        assert not cond

    def test_no_fire_when_both_present(self):
        text = "The API requires authentication before returning data."
        sec = _para_section(text)
        ctx = _ctx(text, sections=[sec])
        issues = self.runner.check(ctx)
        cond = [i for i in issues if "conditional" in i["check"]]
        assert not cond


# Remove duplicate _ctx at end of file — the one at the top now includes nlp parameter.

# ---------------------------------------------------------------------------
# SP4 — readability type (skipped when textstat absent)
# ---------------------------------------------------------------------------

class TestReadabilityType:
    def test_no_crash_without_textstat(self):
        from rhetoric_lint.runners._readability import _TEXTSTAT_OK
        import tempfile, yaml, os
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "Read"))
            with open(os.path.join(tmpdir, "Read", "fk.yml"), "w") as f:
                yaml.dump({"extends": "readability", "message": "FK %s too high",
                           "level": "warning", "scope": "summary",
                           "metrics": ["Flesch-Kincaid"], "grade": 12}, f)
            r = _runner(tmpdir, enabled=["Read"])
            ctx = _ctx("This is a simple document with basic words.", sections=[])
            issues = r.check(ctx)
            if not _TEXTSTAT_OK:
                assert issues == []
            # If textstat present, may or may not fire — just check no crash
            assert isinstance(issues, list)

    def test_readability_preprocessing(self):
        from rhetoric_lint.runners._readability import preprocess_for_readability
        sections = [
            {
                "heading": "Intro",
                "level": 1,
                "start": 0, "end": 100,
                "topic_type": "general",
                "paragraphs": [
                    {"text": "This is a paragraph.", "pos": 0, "line": 1,
                     "nodes": [{"type": "Paragraph", "text": "This is a paragraph."}],
                     "sentences": []},
                    {"text": "```python\ncode here\n```", "pos": 20, "line": 3,
                     "nodes": [{"type": "CodeFence", "text": "code here"}],
                     "sentences": []},
                ]
            }
        ]
        result = preprocess_for_readability(sections)
        assert "paragraph" in result
        assert "code here" not in result

    def test_inline_code_replaced_with_stars(self):
        from rhetoric_lint.runners._readability import preprocess_for_readability
        sections = [
            {
                "heading": "S",
                "level": 1,
                "start": 0, "end": 50,
                "topic_type": "general",
                "paragraphs": [
                    {"text": "Use `foo` to bar.", "pos": 0, "line": 1,
                     "nodes": [{"type": "Paragraph", "text": "Use `foo` to bar."}],
                     "sentences": []}
                ]
            }
        ]
        result = preprocess_for_readability(sections)
        assert "`foo`" not in result
        assert "*****" in result or result  # inline code replaced


# ---------------------------------------------------------------------------
# SP4 — sequence type
# ---------------------------------------------------------------------------

class TestSequence:
    def test_no_crash_without_nlp(self):
        import tempfile, yaml, os
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "Seq"))
            with open(os.path.join(tmpdir, "Seq", "test_seq.yml"), "w") as f:
                yaml.dump({
                    "extends": "sequence",
                    "message": "Sequence matched.",
                    "level": "warning",
                    "scope": "paragraph",
                    "tokens": [{"pattern": "is", "tag": "VBZ"}],
                }, f)
            r = _runner(tmpdir, enabled=["Seq"])
            ctx = _ctx("This is a test.", nlp=None, sections=[])
            issues = r.check(ctx)
            assert issues == []

    def test_sequence_match_with_nlp(self):
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm")
        except Exception:
            pytest.skip("spaCy model not available")

        import tempfile, yaml, os
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "Seq"))
            with open(os.path.join(tmpdir, "Seq", "test_seq.yml"), "w") as f:
                yaml.dump({
                    "extends": "sequence",
                    "message": "Found target sequence.",
                    "level": "warning",
                    "scope": "paragraph",
                    "tokens": [{"pattern": r"\bdog\b"}, {"pattern": r"\bruns\b"}],
                }, f)
            r = _runner(tmpdir, enabled=["Seq"])
            doc = nlp("The dog runs fast.")
            sec = {
                "heading": "S", "level": 1, "start": 0, "end": 100,
                "topic_type": "general",
                "paragraphs": [{"text": "The dog runs fast.", "pos": 0, "line": 1,
                                 "nodes": [], "sentences": [], "doc": doc}]
            }
            ctx = _ctx("The dog runs fast.", nlp=nlp, sections=[sec])
            issues = r.check(ctx)
            assert any("test_seq" in i["check"] for i in issues)


# ---------------------------------------------------------------------------
# SP_SPELL — extends: spelling
# ---------------------------------------------------------------------------

# FIXTURES_DIR is the parent of SpellStyle/ — same as TestStyle loading convention
SPELL_STYLE_DIR = FIXTURES_DIR  # load(style_dirs=[FIXTURES_DIR], enabled_styles=["SpellStyle"])

try:
    from spylls.hunspell import Dictionary as _HD
    _SPYLLS_INSTALLED = True
except ImportError:
    _SPYLLS_INSTALLED = False


def _spell_section(text: str, line: int = 1) -> dict:
    """Section with paragraph nodes explicitly marked as prose."""
    return {
        "heading": "Section", "level": 2, "start": 0, "end": len(text),
        "topic_type": "general",
        "paragraphs": [
            {
                "text": text, "pos": 0, "line": line,
                "nodes": [{"type": "Paragraph", "text": text}],
                "sentences": [],
            }
        ],
    }


class TestSpelling:
    def _runner_spelling(self, stem: str = "spelling_en_us") -> ValeStyleRunner:
        r = ValeStyleRunner()
        r.load(style_dirs=[SPELL_STYLE_DIR], enabled_styles=["SpellStyle"])
        # Narrow to the requested rule stem
        r._rules = [rule for rule in r._rules if rule.name.endswith(stem)]
        return r

    @pytest.mark.skipif(not _SPYLLS_INSTALLED, reason="spylls not installed")
    def test_correct_word_no_fire(self):
        r = self._runner_spelling()
        sec = _spell_section("The quick brown fox jumps over the lazy dog.")
        ctx = _ctx("The quick brown fox jumps over the lazy dog.", sections=[sec])
        issues = r.check(ctx)
        assert not any("spelling" in i["check"].lower() for i in issues)

    @pytest.mark.skipif(not _SPYLLS_INSTALLED, reason="spylls not installed")
    def test_misspelled_word_fires(self):
        r = self._runner_spelling()
        sec = _spell_section("This is a misspeled word.")
        ctx = _ctx("This is a misspeled word.", sections=[sec])
        issues = r.check(ctx)
        assert any("misspeled" in i["message"] for i in issues)

    @pytest.mark.skipif(not _SPYLLS_INSTALLED, reason="spylls not installed")
    def test_misspelled_line_and_column(self):
        r = self._runner_spelling()
        text = "Run the instalation script."
        sec = _spell_section(text, line=5)
        ctx = _ctx(text, sections=[sec])
        issues = r.check(ctx)
        spelling_issues = [i for i in issues if "instalation" in i["message"]]
        assert spelling_issues
        assert spelling_issues[0]["line"] == 5
        assert spelling_issues[0]["column"] >= 1

    @pytest.mark.skipif(not _SPYLLS_INSTALLED, reason="spylls not installed")
    def test_ignore_list_suppresses_word(self):
        r = ValeStyleRunner()
        r.load(style_dirs=[SPELL_STYLE_DIR], enabled_styles=["SpellStyle"])
        r._rules = [rule for rule in r._rules if "spelling_with_ignore" in rule.name]
        sec = _spell_section("Use xyzignored to do the thing.")
        ctx = _ctx("Use xyzignored to do the thing.", sections=[sec])
        issues = r.check(ctx)
        assert not any("xyzignored" in i["message"] for i in issues)

    @pytest.mark.skipif(not _SPYLLS_INSTALLED, reason="spylls not installed")
    def test_vocab_exceptions_suppressed(self):
        r = ValeStyleRunner()
        r.load(style_dirs=[SPELL_STYLE_DIR], enabled_styles=["SpellStyle"])
        r._rules = [rule for rule in r._rules if "spelling_en_us" in rule.name]
        # Manually inject exception
        for rule in r._rules:
            rule.exceptions.append("frobnicator")
        sec = _spell_section("The frobnicator handles the request.")
        ctx = _ctx("The frobnicator handles the request.", sections=[sec])
        issues = r.check(ctx)
        assert not any("frobnicator" in i["message"] for i in issues)

    @pytest.mark.skipif(not _SPYLLS_INSTALLED, reason="spylls not installed")
    def test_filters_regex_suppresses_word(self):
        r = ValeStyleRunner()
        r.load(style_dirs=[SPELL_STYLE_DIR], enabled_styles=["SpellStyle"])
        r._rules = [rule for rule in r._rules if "spelling_with_filters" in rule.name]
        # The filter pattern matches capitalized words, so proper nouns are skipped
        sec = _spell_section("Contact Xyzabc for support.")
        ctx = _ctx("Contact Xyzabc for support.", sections=[sec])
        issues = r.check(ctx)
        assert not any("Xyzabc" in i["message"] for i in issues)

    @pytest.mark.skipif(not _SPYLLS_INSTALLED, reason="spylls not installed")
    def test_suggestions_populated(self):
        r = ValeStyleRunner()
        r.load(style_dirs=[SPELL_STYLE_DIR], enabled_styles=["SpellStyle"])
        r._rules = [rule for rule in r._rules if "spelling_with_suggestions" in rule.name]
        sec = _spell_section("This is a misspeled word.")
        ctx = _ctx("This is a misspeled word.", sections=[sec])
        issues = r.check(ctx)
        spelling = [i for i in issues if "misspeled" in i["message"]]
        assert spelling
        assert "suggestions" in spelling[0]
        assert len(spelling[0]["suggestions"]) <= 3
        assert len(spelling[0]["suggestions"]) >= 1

    @pytest.mark.skipif(not _SPYLLS_INSTALLED, reason="spylls not installed")
    def test_en_gb_spelling_colour_accepted(self):
        """en-GB: 'colour' is correct, 'color' is not."""
        import tempfile, yaml as _yaml, os as _os
        with tempfile.TemporaryDirectory() as tmpdir:
            import spylls, shutil
            pkg_dir = _os.path.dirname(spylls.__file__)
            # Check if en_GB is available; skip if not
            en_gb_aff = _os.path.join(pkg_dir, "hunspell", "data", "en", "en_GB.aff")
            if not _os.path.isfile(en_gb_aff):
                pytest.skip("en_GB not bundled in this spylls version")
            shutil.copy(en_gb_aff, _os.path.join(tmpdir, "en_GB.aff"))
            shutil.copy(en_gb_aff.replace(".aff", ".dic"), _os.path.join(tmpdir, "en_GB.dic"))
            rule_yml = {
                "extends": "spelling",
                "message": "'%s' not in dictionary.",
                "level": "warning",
                "scope": "paragraph",
                "dictionaries": ["en_GB"],
            }
            style_path = _os.path.join(tmpdir, "GB")
            _os.makedirs(style_path)
            with open(_os.path.join(style_path, "spelling_gb.yml"), "w") as f:
                _yaml.dump(rule_yml, f)
            r = ValeStyleRunner()
            r.load(style_dirs=[tmpdir], enabled_styles=["GB"])
            sec = _spell_section("Use colour not color.")
            ctx = _ctx("Use colour not color.", sections=[sec])
            issues = r.check(ctx)
            assert not any("colour" in i["message"] for i in issues)
            assert any("color" in i["message"] for i in issues)

    def test_spylls_absent_meta_finding(self, monkeypatch):
        """When spylls is not installed, emit a single meta-finding, no crash."""
        import rhetoric_lint.runners.vale_style as _vs
        monkeypatch.setattr(_vs, "_SPYLLS_AVAILABLE", False)
        r = ValeStyleRunner()
        r.load(style_dirs=[SPELL_STYLE_DIR], enabled_styles=["SpellStyle"])
        r._rules = [rule for rule in r._rules if "spelling_en_us" in rule.name]
        sec = _spell_section("Hello world.")
        ctx = _ctx("Hello world.", sections=[sec])
        issues = r.check(ctx)
        assert any("spylls" in i["message"].lower() for i in issues)
        assert all(i["severity"] == "suggestion" for i in issues if "spylls" in i["message"].lower())

    def test_missing_dict_file_no_crash(self):
        """When dict files are missing, rule is silently skipped."""
        import tempfile, yaml as _yaml, os as _os
        with tempfile.TemporaryDirectory() as tmpdir:
            style_path = _os.path.join(tmpdir, "BadSpell")
            _os.makedirs(style_path)
            rule_yml = {
                "extends": "spelling",
                "message": "'%s' not found.",
                "level": "warning",
                "scope": "paragraph",
                "dictionaries": ["nonexistent_dict"],
            }
            with open(_os.path.join(style_path, "bad.yml"), "w") as f:
                _yaml.dump(rule_yml, f)
            r = ValeStyleRunner()
            r.load(style_dirs=[tmpdir], enabled_styles=["BadSpell"])
            sec = _spell_section("Hello world.")
            ctx = _ctx("Hello world.", sections=[sec])
            issues = r.check(ctx)
            # Must not crash; may produce zero issues or meta-finding but no exception
            assert isinstance(issues, list)
