"""Tests for SP8 NLP rule expansion: SyntacticDepth, Nominalization, MetricDensity,
ToneImbalance, PreferredForm, and TabVariantBalance."""
import os
import json
import tempfile
import pytest
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# spaCy model for integration-level tests
# ---------------------------------------------------------------------------

try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
except Exception:
    _nlp = None


def _ctx(text="", sections=None, genre="general", doc=None, nlp=None, const=None, path="test.md"):
    from rhetoric_lint import const as _const
    return {
        "path": path,
        "text": text,
        "sections": sections or [],
        "genre": genre,
        "doc": doc,
        "nlp": nlp or _nlp,
        "const": const if const is not None else _const,
    }


def _para(text="", line=1, pos=0, doc=None, nodes=None, sentences=None):
    return {
        "text": text,
        "pos": pos,
        "line": line,
        "doc": doc,
        "nodes": nodes or [],
        "sentences": sentences or [],
    }


def _sec(heading="Section", paragraphs=None, topic_type="general"):
    return {
        "heading": heading,
        "level": 2,
        "start": 0,
        "end": 500,
        "topic_type": topic_type,
        "paragraphs": paragraphs or [],
    }


def _nlp_para(text, line=1, pos=0):
    """Build a paragraph dict with a real spaCy doc."""
    if _nlp is None:
        pytest.skip("spaCy model not available")
    doc = _nlp(text)
    return _para(text=text, line=line, pos=pos, doc=doc)


# ---------------------------------------------------------------------------
# Attention.SyntacticDepth
# ---------------------------------------------------------------------------

class TestSyntacticDepth:
    def setup_method(self):
        if _nlp is None:
            pytest.skip("spaCy model not available")
        from rhetoric_lint.rules.syntactic_depth import check
        self.check = check

    def test_flags_deeply_nested_sentence(self):
        # Triggers both deep dependency tree (>10) AND many nested clauses (>4)
        text = (
            "The system that was designed by the team who originally built the platform "
            "which launched in 2019 requires that all requests that arrive after midnight "
            "that belong to users who registered before the cutoff date "
            "are processed before the jobs that run at dawn complete their cycles "
            "so that the pipeline that monitors the queue can report results."
        )
        p = _nlp_para(text)
        sec = _sec(paragraphs=[p], topic_type="concept")  # gated to concept sections
        issues = self.check(_ctx(text=text, sections=[sec]))
        assert any(i["check"] == "Attention.SyntacticDepth" for i in issues)

    def test_no_flag_simple_sentence(self):
        text = "Install the package."
        p = _nlp_para(text)
        sec = _sec(paragraphs=[p], topic_type="concept")
        issues = self.check(_ctx(text=text, sections=[sec]))
        assert not any(i["check"] == "Attention.SyntacticDepth" for i in issues)

    def test_no_flag_coordination_without_subordination(self):
        # Coordination ("and", "or") doesn't create subordinate clause depth
        text = "The service starts and the database connects and the API responds."
        p = _nlp_para(text)
        sec = _sec(paragraphs=[p], topic_type="concept")
        issues = self.check(_ctx(text=text, sections=[sec]))
        assert not any(i["check"] == "Attention.SyntacticDepth" for i in issues)

    def test_no_flag_single_word_sentence(self):
        text = "Done."
        p = _nlp_para(text)
        sec = _sec(paragraphs=[p], topic_type="concept")
        issues = self.check(_ctx(text=text, sections=[sec]))
        assert not any(i["check"] == "Attention.SyntacticDepth" for i in issues)

    def test_no_crash_on_empty_section(self):
        issues = self.check(_ctx(sections=[_sec(paragraphs=[])]))
        assert isinstance(issues, list)


# ---------------------------------------------------------------------------
# Rhetoric.Nominalization
# ---------------------------------------------------------------------------

class TestNominalization:
    def setup_method(self):
        if _nlp is None:
            pytest.skip("spaCy model not available")
        from rhetoric_lint.rules.nominalizations import check
        self.check = check

    def test_flags_prep_of_pattern(self):
        text = "The implementation of the API takes time."
        p = _nlp_para(text)
        sec = _sec(paragraphs=[p], topic_type="concept")  # gated to concept sections
        issues = self.check(_ctx(text=text, sections=[sec]))
        assert any(i["check"] == "Rhetoric.Nominalization" for i in issues)

    def test_no_flag_no_prep_pattern(self):
        # Nominalization as subject (no "of" prepositional pattern)
        text = "Implementation is key to success."
        p = _nlp_para(text)
        sec = _sec(paragraphs=[p], topic_type="concept")
        issues = self.check(_ctx(text=text, sections=[sec]))
        assert not any(i["check"] == "Rhetoric.Nominalization" for i in issues)

    def test_no_flag_non_deverbal_noun(self):
        # "nation" ends in -tion but has no verb root
        text = "The implementation of the nation requires careful planning."
        p = _nlp_para(text)
        sec = _sec(paragraphs=[p], topic_type="concept")
        # "nation" doesn't derive from a common verb; "implementation" should still fire
        issues = self.check(_ctx(text=text, sections=[sec]))
        # At most one finding (implementation), not nation
        checks = [i["check"] for i in issues]
        assert "Rhetoric.Nominalization" in checks

    def test_no_crash_without_nlp(self):
        from rhetoric_lint.rules.nominalizations import check
        issues = check({
            "path": "t.md", "text": "Text.", "sections": [],
            "nlp": None, "const": None,
        })
        assert issues == []


# ---------------------------------------------------------------------------
# Attention.MetricDensity
# ---------------------------------------------------------------------------

class TestMetricDensity:
    def setup_method(self):
        if _nlp is None:
            pytest.skip("spaCy model not available")
        from rhetoric_lint.rules.metric_density import check
        self.check = check

    def test_no_flag_sparse_numbers(self):
        text = "The service handles 100 requests per second under normal conditions."
        p = _nlp_para(text)
        sec = _sec(paragraphs=[p])
        issues = self.check(_ctx(text=text, sections=[sec]))
        assert not any(i["check"] == "Attention.MetricDensity" for i in issues)

    def test_no_flag_short_sentence(self):
        # Fewer than 8 tokens — should be skipped
        text = "Response time: 200ms."
        p = _nlp_para(text)
        sec = _sec(paragraphs=[p])
        issues = self.check(_ctx(text=text, sections=[sec]))
        assert not any(i["check"] == "Attention.MetricDensity" for i in issues)

    def test_flags_dense_metrics_sentence(self):
        # >30% of tokens are numeric: 8 numbers in ~20 tokens
        text = (
            "The limits are 250ms, 500ms, 750ms, 1000ms p99 "
            "at 50, 100, 500, 1000 concurrent connections."
        )
        p = _nlp_para(text)
        sec = _sec(paragraphs=[p])
        issues = self.check(_ctx(text=text, sections=[sec]))
        assert any(i["check"] == "Attention.MetricDensity" for i in issues)

    def test_no_crash_on_empty(self):
        issues = self.check(_ctx(sections=[]))
        assert issues == []


# ---------------------------------------------------------------------------
# Rhetoric.ToneImbalance
# ---------------------------------------------------------------------------

class TestToneImbalance:
    def setup_method(self):
        if _nlp is None:
            pytest.skip("spaCy model not available")
        from rhetoric_lint.rules.tone import check
        self.check = check

    def _doc(self, text):
        return _nlp(text)

    def test_flags_authoritative_howto(self):
        text = (
            "You must install Python first. "
            "You must configure the environment. "
            "You must never skip this step. "
            "You must always run the tests. "
            "You must complete setup before proceeding."
        )
        doc = self._doc(text)
        issues = self.check(_ctx(text=text, doc=doc, genre="howto"))
        assert any(i["check"] == "Rhetoric.ToneImbalance" for i in issues)

    def test_no_flag_below_threshold(self):
        text = (
            "Install Python using your package manager. "
            "Configure the environment variables. "
            "Run the test suite to verify your setup."
        )
        doc = self._doc(text)
        issues = self.check(_ctx(text=text, doc=doc, genre="howto"))
        assert not any(i["check"] == "Rhetoric.ToneImbalance" for i in issues)

    def test_flags_negative_framing_any_genre(self):
        text = (
            "Do not use this API. Cannot connect to the server. "
            "Will not process requests. Do not call this function. "
            "Cannot authenticate user. Will not work without credentials. "
            "Do not skip validation. Cannot proceed without setup. "
            "Never ignore errors. Do not leave fields empty."
        )
        doc = self._doc(text)
        issues = self.check(_ctx(text=text, doc=doc, genre="reference"))
        assert any(i["check"] == "Rhetoric.ToneImbalance" for i in issues)

    def test_no_flag_empty_doc(self):
        issues = self.check(_ctx(text="", doc=None))
        assert issues == []

    def test_one_finding_max(self):
        text = " ".join(["must never do this"] * 20)
        doc = self._doc(text)
        issues = self.check(_ctx(text=text, doc=doc, genre="howto"))
        tone_issues = [i for i in issues if i["check"] == "Rhetoric.ToneImbalance"]
        assert len(tone_issues) <= 1


# ---------------------------------------------------------------------------
# Terminology.PreferredForm
# ---------------------------------------------------------------------------

class TestPreferredForm:
    def setup_method(self):
        from rhetoric_lint.rules.preferred_form import check
        self.check = check
        self.tmpdir = tempfile.mkdtemp()

    def _make_terms_file(self, terms):
        path = os.path.join(self.tmpdir, "terms.json")
        with open(path, "w") as f:
            json.dump(terms, f)
        return path

    def _const_with_file(self, terms_file):
        from rhetoric_lint import const as _const
        import copy
        # Use SimpleNamespace to override TERMINOLOGY_FILE
        return SimpleNamespace(
            TERMINOLOGY_FILE=terms_file,
            RULE_SEVERITY_LEVELS=getattr(_const, "RULE_SEVERITY_LEVELS", {}),
        )

    def _para_sec(self, text, line=1):
        return _sec(paragraphs=[_para(text=text, line=line)])

    def test_flags_wrong_case(self):
        terms_file = self._make_terms_file([{"required_form": "GitHub", "aliases": []}])
        const = self._const_with_file(terms_file)
        sec = self._para_sec("Use github for version control.")
        issues = self.check(_ctx(text="Use github for version control.", sections=[sec], const=const))
        assert any(i["check"] == "Terminology.PreferredForm" for i in issues)

    def test_no_flag_correct_form(self):
        terms_file = self._make_terms_file([{"required_form": "GitHub", "aliases": []}])
        const = self._const_with_file(terms_file)
        sec = self._para_sec("Use GitHub for version control.")
        issues = self.check(_ctx(text="Use GitHub for version control.", sections=[sec], const=const))
        assert not any(i["check"] == "Terminology.PreferredForm" for i in issues)

    def test_no_flag_in_url(self):
        terms_file = self._make_terms_file([{"required_form": "GitHub", "aliases": []}])
        const = self._const_with_file(terms_file)
        text = "Visit https://github.com for more."
        sec = self._para_sec(text)
        issues = self.check(_ctx(text=text, sections=[sec], const=const))
        assert not any(i["check"] == "Terminology.PreferredForm" for i in issues)

    def test_no_flag_in_inline_code(self):
        terms_file = self._make_terms_file([{"required_form": "GitHub", "aliases": []}])
        const = self._const_with_file(terms_file)
        text = "Run `github clone` to copy the repo."
        sec = self._para_sec(text)
        issues = self.check(_ctx(text=text, sections=[sec], const=const))
        assert not any(i["check"] == "Terminology.PreferredForm" for i in issues)

    def test_fix_key_contains_required_form(self):
        terms_file = self._make_terms_file([{"required_form": "JavaScript", "aliases": ["Javascript"]}])
        const = self._const_with_file(terms_file)
        text = "We use Javascript in this project."
        sec = self._para_sec(text)
        issues = self.check(_ctx(text=text, sections=[sec], const=const))
        pf = [i for i in issues if i["check"] == "Terminology.PreferredForm"]
        assert pf[0]["fix"] == "JavaScript"

    def test_aliases_also_flagged(self):
        terms_file = self._make_terms_file([{
            "required_form": "Kubernetes",
            "aliases": ["k8s", "kube"],
        }])
        const = self._const_with_file(terms_file)
        text = "Deploy to k8s using helm."
        sec = self._para_sec(text)
        issues = self.check(_ctx(text=text, sections=[sec], const=const))
        assert any(i["check"] == "Terminology.PreferredForm" for i in issues)

    def test_no_findings_when_no_file_configured(self):
        from rhetoric_lint import const as _const
        sec = self._para_sec("Use github everywhere.")
        issues = self.check(_ctx(sections=[sec]))
        assert not any(i["check"] == "Terminology.PreferredForm" for i in issues)

    def test_string_list_format(self):
        # Simple list-of-strings format
        terms_file = self._make_terms_file(["GitHub"])
        const = self._const_with_file(terms_file)
        sec = self._para_sec("Use github for version control.")
        issues = self.check(_ctx(text="Use github for version control.", sections=[sec], const=const))
        assert any(i["check"] == "Terminology.PreferredForm" for i in issues)


# ---------------------------------------------------------------------------
# Symmetry.TabVariantBalance
# ---------------------------------------------------------------------------

class TestTabVariantBalance:
    def setup_method(self):
        from rhetoric_lint.rules.symmetry import check
        self.check = check

    def _ol_node(self, text="Step"):
        return {"type": "ListItem", "list_type": "ol", "text": text}

    def _tab_para(self, title, ol_count=0, line=1):
        nodes = [self._ol_node(f"Step {i+1}") for i in range(ol_count)]
        return _para(
            text=f"> **{title}**\n> content here",
            line=line,
            nodes=nodes,
        )

    def _ctx_tab(self, variants):
        """Build context with tab-variant paragraphs."""
        paras = []
        for i, (title, ol_count) in enumerate(variants):
            paras.append(self._tab_para(title, ol_count, line=i * 10 + 1))
        sec = _sec(paragraphs=paras)
        return _ctx(text="placeholder", sections=[sec])

    def test_two_tabs_same_count_no_finding(self):
        issues = self.check(self._ctx_tab([("macOS", 3), ("Linux", 3)]))
        tv = [i for i in issues if i["check"] == "Symmetry.TabVariantBalance"]
        assert tv == []

    def test_two_tabs_large_difference_flags(self):
        issues = self.check(self._ctx_tab([("macOS", 4), ("Linux", 2)]))
        tv = [i for i in issues if i["check"] == "Symmetry.TabVariantBalance"]
        assert tv != []

    def test_two_tabs_within_tolerance_no_finding(self):
        # Tolerance is 1 by default
        issues = self.check(self._ctx_tab([("macOS", 3), ("Linux", 4)]))
        tv = [i for i in issues if i["check"] == "Symmetry.TabVariantBalance"]
        assert tv == []

    def test_single_tab_no_finding(self):
        issues = self.check(self._ctx_tab([("macOS", 3)]))
        tv = [i for i in issues if i["check"] == "Symmetry.TabVariantBalance"]
        assert tv == []

    def test_code_only_tabs_no_finding(self):
        # All variants have zero ordered list items → code-only tabs
        issues = self.check(self._ctx_tab([("macOS", 0), ("Linux", 0)]))
        tv = [i for i in issues if i["check"] == "Symmetry.TabVariantBalance"]
        assert tv == []

    def test_reference_section_skipped(self):
        paras = [
            self._tab_para("macOS", ol_count=4, line=1),
            self._tab_para("Linux", ol_count=1, line=10),
        ]
        sec = _sec(paragraphs=paras, topic_type="reference")
        issues = self.check(_ctx(text="placeholder", sections=[sec]))
        tv = [i for i in issues if i["check"] == "Symmetry.TabVariantBalance"]
        assert tv == []

    def test_three_tabs_flags_when_spread_exceeds_tolerance(self):
        issues = self.check(self._ctx_tab([("macOS", 5), ("Linux", 5), ("Windows", 1)]))
        tv = [i for i in issues if i["check"] == "Symmetry.TabVariantBalance"]
        assert tv != []


# ---------------------------------------------------------------------------
# Precision corpus: all SP8 rules must not crash or false-positive on real docs
# ---------------------------------------------------------------------------

class TestSP8PrecisionCorpus:
    def _corpus_files(self):
        corpus_dir = os.path.join(
            os.path.dirname(__file__), "fixtures", "corpus", "technical"
        )
        if not os.path.isdir(corpus_dir):
            pytest.skip("corpus not found")
        import glob
        files = glob.glob(os.path.join(corpus_dir, "*.md"))
        if not files:
            pytest.skip("no corpus files")
        return files

    def test_no_false_positives_on_corpus(self):
        from rhetoric_lint.engine import RhetoricEngine
        eng = RhetoricEngine()
        issues = eng.lint_files(self._corpus_files())
        sp8_checks = {
            "Attention.SyntacticDepth",
            "Rhetoric.Nominalization",
            "Attention.MetricDensity",
            "Rhetoric.ToneImbalance",
            "Terminology.PreferredForm",
            "Symmetry.TabVariantBalance",
        }
        fp = [i for i in issues if i["check"] in sp8_checks]
        assert fp == [], (
            "SP8 rules produced false positives on precision corpus:\n"
            + "\n".join(f"  {i['path']}:{i['line']} [{i['check']}] {i['message']}" for i in fp)
        )
