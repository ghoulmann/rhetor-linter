"""Tests for topic_type classifier and topic-type rule files."""
import pytest
from types import SimpleNamespace
from rhetoric_lint.topic_type import classify_section_topic, _classify_section_by_body
from rhetoric_lint.rules.concept import check as concept_check
from rhetoric_lint.rules.troubleshooting import check as ts_check
from rhetoric_lint.rules.howto import check as howto_check
from rhetoric_lint.rules.faq import check as faq_check
from rhetoric_lint.rules.tutorial import check as tutorial_check
from rhetoric_lint.rules.reference import check as reference_check
from rhetoric_lint.rules.explanation import check as explanation_check


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sec(heading, body="", ol_items=None, ul_items=None, topic_type=None,
         start=0, end=100, level=2):
    nodes = []
    if ol_items:
        nodes.extend({"type": "ListItem", "list_type": "ol", "text": t} for t in ol_items)
    if ul_items:
        nodes.extend({"type": "ListItem", "list_type": "ul", "text": t} for t in ul_items)
    paras = []
    if body:
        paras.append({"text": body, "pos": 0, "end": 50, "line": 2,
                      "doc": None, "sentences": [], "nodes": nodes})
    elif nodes:
        paras.append({"text": "", "pos": 0, "end": 50, "line": 2,
                      "doc": None, "sentences": [], "nodes": nodes})
    sec = {"heading": heading, "paragraphs": paras,
           "start": start, "end": end, "level": level}
    if topic_type:
        sec["topic_type"] = topic_type
    return sec


def _ctx(sections, text=""):
    return {"path": "test.md", "text": text, "sections": sections, "nlp": None}


# ---------------------------------------------------------------------------
# Classifier tests
# ---------------------------------------------------------------------------

class TestClassifier:
    def test_faq_heading(self):
        assert classify_section_topic(_sec("FAQ")) == "faq"

    def test_question_heading(self):
        assert classify_section_topic(_sec("How do I reset my password?")) == "faq"

    def test_troubleshooting_heading(self):
        assert classify_section_topic(_sec("Troubleshooting")) == "troubleshooting"

    def test_reference_heading(self):
        assert classify_section_topic(_sec("API Reference")) == "reference"

    def test_howto_heading(self):
        assert classify_section_topic(_sec("Installing the CLI")) == "howto"

    def test_howto_how_to_prefix(self):
        assert classify_section_topic(_sec("How to Configure TLS")) == "howto"

    def test_tutorial_heading(self):
        assert classify_section_topic(_sec("Tutorial")) == "tutorial"

    def test_concept_heading(self):
        assert classify_section_topic(_sec("Overview")) == "concept"

    def test_explanation_heading(self):
        assert classify_section_topic(_sec("Design Rationale")) == "explanation"

    def test_general_fallback(self):
        assert classify_section_topic(_sec("Appendix")) == "general"


# ---------------------------------------------------------------------------
# Concept.ProcedureLeak
# ---------------------------------------------------------------------------

class TestConceptProcedureLeak:
    def test_flags_when_ol_in_concept(self):
        sec = _sec("Overview", ol_items=["Run this", "Then that", "Finally done"],
                   topic_type="concept")
        issues = concept_check(_ctx([sec]))
        assert any(i["check"] == "Concept.ProcedureLeak" for i in issues)

    def test_no_flag_below_threshold(self):
        sec = _sec("Overview", ol_items=["Step one", "Step two"], topic_type="concept")
        issues = concept_check(_ctx([sec]))
        assert issues == []

    def test_no_flag_non_concept_section(self):
        sec = _sec("Installing", ol_items=["Run a", "Run b", "Run c"], topic_type="howto")
        issues = concept_check(_ctx([sec]))
        assert issues == []


# ---------------------------------------------------------------------------
# Troubleshooting.MissingRemediation / UnorderedRemediation
# ---------------------------------------------------------------------------

class TestTroubleshooting:
    def test_flags_missing_remediation(self):
        sec = _sec("Troubleshooting", body="Check the logs.", topic_type="troubleshooting")
        issues = ts_check(_ctx([sec]))
        assert any(i["check"] == "Troubleshooting.MissingRemediation" for i in issues)

    def test_flags_unordered_remediation(self):
        sec = _sec("Troubleshooting", ul_items=["Fix A", "Fix B"], topic_type="troubleshooting")
        issues = ts_check(_ctx([sec]))
        assert any(i["check"] == "Troubleshooting.UnorderedRemediation" for i in issues)

    def test_no_flag_with_ol(self):
        sec = _sec("Troubleshooting", ol_items=["Step 1", "Step 2"], topic_type="troubleshooting")
        issues = ts_check(_ctx([sec]))
        assert issues == []

    def test_no_flag_non_troubleshooting(self):
        sec = _sec("Overview", body="No steps here.", topic_type="concept")
        assert ts_check(_ctx([sec])) == []


# ---------------------------------------------------------------------------
# HowTo.UnorderedSteps / NonImperativeStep
# ---------------------------------------------------------------------------

class TestHowTo:
    def test_flags_unordered_steps(self):
        sec = _sec("Installing", ul_items=["Item a", "Item b"], topic_type="howto")
        issues = howto_check(_ctx([sec]))
        assert any(i["check"] == "HowTo.UnorderedSteps" for i in issues)

    def test_no_flag_with_ol(self):
        sec = _sec("Installing", ol_items=["Run install", "Configure env"],
                   topic_type="howto")
        issues = howto_check(_ctx([sec]))
        assert not any(i["check"] == "HowTo.UnorderedSteps" for i in issues)

    def test_non_imperative_step_flagged(self):
        sec = _sec("Installing", ol_items=["The installation requires Python",
                                           "Configuration is needed", "Testing is done"],
                   topic_type="howto")
        issues = howto_check(_ctx([sec]))
        assert any(i["check"] == "HowTo.NonImperativeStep" for i in issues)

    def test_imperative_step_not_flagged(self):
        sec = _sec("Installing", ol_items=["Install Python", "Configure the env",
                                            "Run the tests"],
                   topic_type="howto")
        issues = howto_check(_ctx([sec]))
        assert not any(i["check"] == "HowTo.NonImperativeStep" for i in issues)

    def test_no_flag_non_howto(self):
        sec = _sec("Overview", ol_items=["A", "B", "C"], topic_type="concept")
        assert not any(i["check"] == "HowTo.UnorderedSteps" for i in howto_check(_ctx([sec])))


# ---------------------------------------------------------------------------
# FAQ.EmptyAnswer / NonQuestionEntry
# ---------------------------------------------------------------------------

class TestFAQ:
    def test_flags_empty_answer(self):
        sec = _sec("How do I reset my password?", body="", topic_type="faq")
        issues = faq_check(_ctx([sec]))
        assert any(i["check"] == "FAQ.EmptyAnswer" for i in issues)

    def test_no_flag_with_answer(self):
        sec = _sec("How do I reset my password?",
                   body="Go to Settings > Security and click Reset Password.",
                   topic_type="faq")
        issues = faq_check(_ctx([sec]))
        assert not any(i["check"] == "FAQ.EmptyAnswer" for i in issues)

    def test_flags_non_question_entry(self):
        parent = _sec("FAQ", topic_type="faq", level=2)
        child = _sec("Password Reset", body="Click the reset link.", topic_type="faq", level=3)
        issues = faq_check(_ctx([parent, child]))
        assert any(i["check"] == "FAQ.NonQuestionEntry" for i in issues)

    def test_no_flag_question_entry(self):
        parent = _sec("FAQ", topic_type="faq", level=2)
        child = _sec("How do I reset my password?",
                     body="Go to Settings and click Reset.", topic_type="faq", level=3)
        issues = faq_check(_ctx([parent, child]))
        assert not any(i["check"] == "FAQ.NonQuestionEntry" for i in issues)


# ---------------------------------------------------------------------------
# Tutorial.NoObservationCues / AlternativesDiversion
# ---------------------------------------------------------------------------

class TestTutorial:
    def test_flags_no_observation_cues(self):
        long_body = "We will build a simple app. " * 10  # > 200 chars
        sec = _sec("Tutorial", body=long_body, topic_type="tutorial")
        issues = tutorial_check(_ctx([sec]))
        assert any(i["check"] == "Tutorial.NoObservationCues" for i in issues)

    def test_no_flag_with_observation_cues(self):
        body = "We will build a simple app. " * 8 + "You should see the output in the terminal."
        sec = _sec("Tutorial", body=body, topic_type="tutorial")
        issues = tutorial_check(_ctx([sec]))
        assert not any(i["check"] == "Tutorial.NoObservationCues" for i in issues)

    def test_no_flag_short_section(self):
        sec = _sec("Tutorial", body="Short.", topic_type="tutorial")
        assert tutorial_check(_ctx([sec])) == []

    def test_flags_alternatives_diversion(self):
        sec = _sec("Tutorial",
                   ol_items=["Install Python", "Or use conda instead", "Run the script"],
                   topic_type="tutorial")
        issues = tutorial_check(_ctx([sec]))
        assert any(i["check"] == "Tutorial.AlternativesDiversion" for i in issues)

    def test_no_flag_single_path(self):
        sec = _sec("Tutorial",
                   ol_items=["Install Python", "Create a virtual env", "Run the script"],
                   topic_type="tutorial")
        issues = tutorial_check(_ctx([sec]))
        assert not any(i["check"] == "Tutorial.AlternativesDiversion" for i in issues)


# ---------------------------------------------------------------------------
# Reference.ContainsInstructions
# ---------------------------------------------------------------------------

class TestReference:
    def test_flags_instructions_in_reference(self):
        sec = _sec("API Reference",
                   ol_items=["Install the package", "Configure credentials", "Run the command"],
                   topic_type="reference")
        issues = reference_check(_ctx([sec]))
        assert any(i["check"] == "Reference.ContainsInstructions" for i in issues)

    def test_no_flag_non_imperative_ol(self):
        sec = _sec("API Reference",
                   ol_items=["The endpoint returns JSON", "The response contains data"],
                   topic_type="reference")
        issues = reference_check(_ctx([sec]))
        assert not any(i["check"] == "Reference.ContainsInstructions" for i in issues)

    def test_no_flag_non_reference(self):
        sec = _sec("Installing", ol_items=["Run a", "Run b", "Run c"], topic_type="howto")
        assert reference_check(_ctx([sec])) == []


# ---------------------------------------------------------------------------
# Explanation.ContainsInstructions / NoConnections
# ---------------------------------------------------------------------------

class TestExplanation:
    def test_flags_instructions_in_explanation(self):
        sec = _sec("Design Rationale",
                   ol_items=["Install the component", "Configure it", "Deploy the service"],
                   topic_type="explanation")
        issues = explanation_check(_ctx([sec]))
        assert any(i["check"] == "Explanation.ContainsInstructions" for i in issues)

    def test_flags_no_connections(self):
        long_body = "The system uses an event-driven architecture for scalability. " * 4
        sec = _sec("Design Rationale", body=long_body, topic_type="explanation",
                   start=0, end=len(long_body))
        ctx = _ctx([sec], text=long_body)
        issues = explanation_check(ctx)
        assert any(i["check"] == "Explanation.NoConnections" for i in issues)

    def test_no_flag_with_links(self):
        body = ("The system uses event sourcing. " * 3
                + "See [Event Sourcing](https://example.com/event-sourcing) for more.")
        sec = _sec("Design Rationale", body=body, topic_type="explanation",
                   start=0, end=len(body))
        ctx = _ctx([sec], text=body)
        issues = explanation_check(ctx)
        assert not any(i["check"] == "Explanation.NoConnections" for i in issues)

    def test_no_flag_short_explanation(self):
        sec = _sec("Why", body="Brief note.", topic_type="explanation", start=0, end=20)
        ctx = _ctx([sec], text="Brief note.")
        assert explanation_check(ctx) == []


# ---------------------------------------------------------------------------
# _classify_section_by_body: body-NLP tiebreaker
# ---------------------------------------------------------------------------

class _FakeToken:
    def __init__(self, text, tag_, is_alpha=True, is_stop=False):
        self.text = text
        self.tag_ = tag_
        self.is_alpha = is_alpha
        self.is_stop = is_stop
        self.lemma_ = text.lower()


class _FakeSent:
    def __init__(self, tokens):
        self._tokens = tokens

    def __iter__(self):
        return iter(self._tokens)


class _FakeDoc:
    def __init__(self, sents):
        self._sents = sents

    @property
    def sents(self):
        return iter(self._sents)


def _make_imperative_doc(n_imperative: int, n_declarative: int) -> _FakeDoc:
    sents = []
    for _ in range(n_imperative):
        sents.append(_FakeSent([_FakeToken("Run", "VB"), _FakeToken("the", "DT", is_alpha=True)]))
    for _ in range(n_declarative):
        sents.append(_FakeSent([_FakeToken("The", "DT", is_alpha=True), _FakeToken("service", "NN", is_alpha=True)]))
    return _FakeDoc(sents)


def _sec_with_doc(heading: str, doc) -> dict:
    return {
        "heading": heading,
        "level": 2,
        "start": 0,
        "end": 100,
        "paragraphs": [{"text": "body", "pos": 0, "doc": doc, "sentences": [], "nodes": []}],
    }


class TestBodyNLPTiebreaker:
    def test_imperative_dominant_returns_howto(self):
        # 4 imperative, 1 declarative → ratio 0.80 ≥ 0.40
        doc = _make_imperative_doc(4, 1)
        sec = _sec_with_doc("Getting ready", doc)
        assert _classify_section_by_body(sec) == "howto"

    def test_declarative_dominant_returns_general(self):
        # 1 imperative, 9 declarative → ratio 0.10 < 0.40
        doc = _make_imperative_doc(1, 9)
        sec = _sec_with_doc("Getting ready", doc)
        assert _classify_section_by_body(sec) == "general"

    def test_no_doc_returns_general(self):
        sec = {
            "heading": "Getting ready",
            "paragraphs": [{"text": "body", "pos": 0, "doc": None, "sentences": [], "nodes": []}],
        }
        assert _classify_section_by_body(sec) == "general"

    def test_no_paragraphs_returns_general(self):
        sec = {"heading": "Getting ready", "paragraphs": []}
        assert _classify_section_by_body(sec) == "general"

    def test_custom_threshold_via_const(self):
        # threshold raised to 0.90 — 4/5 = 0.80 should now return "general"
        doc = _make_imperative_doc(4, 1)
        sec = _sec_with_doc("Getting ready", doc)
        const = SimpleNamespace(SECTION_IMPERATIVE_RATIO_HOWTO=0.90)
        assert _classify_section_by_body(sec, const) == "general"

    def test_classify_section_topic_falls_through_to_tiebreaker(self):
        # Generic heading + imperative body → howto via tiebreaker
        doc = _make_imperative_doc(4, 1)
        sec = _sec_with_doc("Getting ready", doc)
        assert classify_section_topic(sec) == "howto"

    def test_classify_section_topic_keyword_wins_over_tiebreaker(self):
        # Known heading keyword "overview" → concept, despite imperative body
        doc = _make_imperative_doc(4, 1)
        sec = _sec_with_doc("Overview", doc)
        assert classify_section_topic(sec) == "concept"
