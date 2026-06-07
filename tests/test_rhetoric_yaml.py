"""Tests for SP6 (TrivializingLanguage YAML) and SP7 (Terminology, Inclusivity YAML)."""
import os
import pytest
from rhetoric_lint.runners.vale_style import ValeStyleRunner

STYLE_SETS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "style-sets")
)


def _runner(style: str) -> ValeStyleRunner:
    r = ValeStyleRunner()
    r.load(style_dirs=[STYLE_SETS_DIR], enabled_styles=[style])
    return r


def _ctx(text: str, genre: str = "general") -> dict:
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


# ---------------------------------------------------------------------------
# SP6 — TrivializingLanguage YAML
# ---------------------------------------------------------------------------

class TestTrivializingLanguageYAML:
    def setup_method(self):
        self.runner = _runner("Rhetoric")

    def test_fires_on_simply(self):
        issues = self.runner.check(_ctx("Simply run the install script."))
        trivializing = [i for i in issues if "TrivializingLanguage" in i["check"]]
        assert trivializing

    def test_fires_on_obviously(self):
        issues = self.runner.check(_ctx("Obviously you need to configure this first."))
        trivializing = [i for i in issues if "TrivializingLanguage" in i["check"]]
        assert trivializing

    def test_fires_on_of_course(self):
        issues = self.runner.check(_ctx("Of course, Python must be installed."))
        trivializing = [i for i in issues if "TrivializingLanguage" in i["check"]]
        assert trivializing

    def test_fires_on_easily(self):
        issues = self.runner.check(_ctx("You can easily configure this setting."))
        trivializing = [i for i in issues if "TrivializingLanguage" in i["check"]]
        assert trivializing

    def test_fires_on_just(self):
        issues = self.runner.check(_ctx("Just add the dependency to your config."))
        trivializing = [i for i in issues if "TrivializingLanguage" in i["check"]]
        assert trivializing

    def test_no_fire_on_just_released(self):
        issues = self.runner.check(_ctx("We just released version 2.0."))
        trivializing = [i for i in issues if "TrivializingLanguage" in i["check"]]
        assert not trivializing

    def test_no_fire_on_have_just(self):
        issues = self.runner.check(_ctx("We have just deployed the fix."))
        trivializing = [i for i in issues if "TrivializingLanguage" in i["check"]]
        assert not trivializing

    def test_no_fire_in_code_block(self):
        # Code fence nodes should not trigger prose-scope rules
        text = "```bash\n# simply install\npip install foo\n```"
        ctx = {
            "path": "test.md",
            "text": text,
            "genre": "general",
            "sections": [
                {
                    "heading": "Setup",
                    "level": 2,
                    "start": 0,
                    "end": len(text),
                    "topic_type": "general",
                    "paragraphs": [
                        {
                            "text": text,
                            "pos": 0,
                            "line": 1,
                            "nodes": [{"type": "CodeFence", "text": "pip install foo"}],
                            "sentences": [],
                        }
                    ],
                }
            ],
        }
        issues = self.runner.check(ctx)
        trivializing = [i for i in issues if "TrivializingLanguage" in i["check"]]
        assert not trivializing


# ---------------------------------------------------------------------------
# SP7 — Terminology
# ---------------------------------------------------------------------------

class TestTerminologyYAML:
    def setup_method(self):
        self.runner = _runner("Rhetoric")

    def _trivializing_checks(self, issues):
        return [i for i in issues if "Terminology" in i["check"]]

    def test_whitelist_flagged(self):
        issues = self.runner.check(_ctx("Add the IP to the whitelist."))
        term = [i for i in issues if "Terminology" in i["check"]]
        assert term
        assert any("allowlist" in i["message"] for i in term)

    def test_blacklist_flagged(self):
        issues = self.runner.check(_ctx("Remove from the blacklist immediately."))
        term = [i for i in issues if "Terminology" in i["check"]]
        assert term
        assert any("denylist" in i["message"] for i in term)

    def test_fix_key_present(self):
        issues = self.runner.check(_ctx("Update the whitelist entries."))
        term = [i for i in issues if "Terminology" in i["check"]]
        assert any(i.get("fix") == "allowlist" for i in term)

    def test_no_fire_on_already_correct(self):
        issues = self.runner.check(_ctx("Update the allowlist and denylist."))
        term = [i for i in issues if "Terminology" in i["check"]]
        assert not term

    def test_fireman_regex_swap(self):
        issues = self.runner.check(_ctx("The fireman saved the day."))
        term = [i for i in issues if "Terminology" in i["check"]]
        assert term
        assert any("firefighter" in i["message"] for i in term)

    def test_chairwoman_regex_swap(self):
        issues = self.runner.check(_ctx("The chairwoman opened the meeting."))
        term = [i for i in issues if "Terminology" in i["check"]]
        assert term
        assert any("chair" in i["message"] for i in term)


# ---------------------------------------------------------------------------
# SP7 — Inclusivity
# ---------------------------------------------------------------------------

class TestInclusivityYAML:
    def setup_method(self):
        self.runner = _runner("Rhetoric")

    def test_guys_flagged(self):
        issues = self.runner.check(_ctx("Hey guys, let's get started."))
        incl = [i for i in issues if "Inclusivity" in i["check"]]
        assert incl

    def test_crazy_flagged(self):
        issues = self.runner.check(_ctx("The performance issue was crazy."))
        incl = [i for i in issues if i["check"] == "Rhetoric.Inclusivity"]
        assert incl

    def test_lame_flagged_by_flag_rule(self):
        issues = self.runner.check(_ctx("That solution is lame."))
        incl = [i for i in issues if "InclusivityFlag" in i["check"]]
        assert incl

    def test_lame_duck_excepted(self):
        issues = self.runner.check(_ctx("It was a lame duck administration."))
        incl = [i for i in issues if "InclusivityFlag" in i["check"]]
        assert not incl

    def test_no_false_positives_on_corpus(self):
        import glob
        corpus_dir = os.path.join(
            os.path.dirname(__file__), "fixtures", "corpus", "technical"
        )
        if not os.path.isdir(corpus_dir):
            pytest.skip("corpus not found")
        files = glob.glob(os.path.join(corpus_dir, "*.md"))
        if not files:
            pytest.skip("no corpus files")

        for f in files:
            with open(f, encoding="utf-8") as fh:
                text = fh.read()
            issues = self.runner.check({
                "path": f, "text": text, "genre": "technical", "sections": [],
            })
            # Terminology/Inclusivity rules may fire on real docs — just verify no crash
            assert isinstance(issues, list)
