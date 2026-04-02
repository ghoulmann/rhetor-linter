import pytest
from pathlib import Path

from rhetoric_lint.engine import RhetoricEngine

# Skip these tests if mistletoe isn't installed
pytest.importorskip("mistletoe")


def run_engine_on_text(text: str, tmp_path: Path):
    p = tmp_path / "test.md"
    p.write_text(text, encoding="utf-8")
    eng = RhetoricEngine()
    issues = eng.lint_files([str(p)])
    return issues


def test_island_sentence(tmp_path):
    md = """# Section

This is a sentence about apples.

Completely unrelated island sentence about quantum mechanics.
"""
    issues = run_engine_on_text(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Cohesion.Break" in checks


def test_transition_exception(tmp_path):
    md = """# Section

This is a sentence about deployment.

However, the next sentence clarifies deployment steps.
"""
    issues = run_engine_on_text(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Cohesion.Break" not in checks


def test_lemma_bridge(tmp_path):
    md = """# Section

Install the package using the setup tool.

The setup will create necessary directories and files.
"""
    issues = run_engine_on_text(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Cohesion.Break" not in checks


def test_multiword_connective_with_overlap_is_allowed(tmp_path):
    md = """# Section

Deployments can fail during rollback windows.

On the other hand, deployments can recover after retries.
"""
    issues = run_engine_on_text(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Cohesion.Break" not in checks


def test_connective_without_overlap_still_breaks(tmp_path):
    md = """# Section

Deploy the package to the registry.

As a result, orchids require indirect sunlight and humidity.
"""
    issues = run_engine_on_text(md, tmp_path)
    checks = {it.get("check") for it in issues}
    # "As a result" is causal with zero noun overlap — now caught as MisusedConnective
    # (previously flagged as Cohesion.Break before MisusedConnective existed)
    assert "Cohesion.MisusedConnective" in checks or "Cohesion.Break" in checks


def test_givenness_break_pronoun_heavy_without_antecedent(tmp_path):
    md = """# Section

Deploy the service to production.

It they this that failed unexpectedly.
"""
    issues = run_engine_on_text(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Cohesion.GivennessBreak" in checks


def test_givenness_break_not_flagged_with_repeated_content(tmp_path):
    md = """# Section

Deploy the service to production.

It deploys the service and reports deployment status.
"""
    issues = run_engine_on_text(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Cohesion.GivennessBreak" not in checks


def test_no_cohesion_break_across_code_block_surface_divergence(tmp_path):
    # "mkdocs" (PROPN → "mkdocs") vs "mkdocs" (NN → "mkdoc") — surface fallback bridges them.
    md = """# Section

Install the MkDocs package using pip.

```
pip install mkdocs
```

You should now have the mkdocs command installed on your system.
"""
    issues = run_engine_on_text(md, tmp_path)
    cohesion_breaks = [it for it in issues if it.get("check") == "Cohesion.Break"]
    assert cohesion_breaks == []


def test_no_cohesion_break_stem_bridge(tmp_path):
    # "requirements" → "requirement" vs "requires" → "require" — stem "requir" bridges them.
    md = """# Section

Check the requirements before installing the package.

This tool requires Python 3.8 or later to run correctly.
"""
    issues = run_engine_on_text(md, tmp_path)
    cohesion_breaks = [it for it in issues if it.get("check") == "Cohesion.Break"]
    assert cohesion_breaks == []


def test_no_cohesion_break_5char_stem_bridge(tmp_path):
    # Regression for spaCy OOV lemmatization inconsistency: the same token can be
    # assigned different lemmas across sentence positions (e.g. "mkdocs" → "mkdoc"
    # in one position and "mkdocs" in another). The 6-char bridge cannot catch this
    # because "mkdoc"[:6]="mkdoc" != "mkdocs"[:6]="mkdocs". The 5-char secondary
    # bridge resolves it: "mkdoc"[:5]="mkdoc" == "mkdocs"[:5]="mkdoc".
    md = """# Section

The mkdocs command builds the documentation site.

Run mkdocs to verify the build succeeded.
"""
    issues = run_engine_on_text(md, tmp_path)
    cohesion_breaks = [it for it in issues if it.get("check") == "Cohesion.Break"]
    assert cohesion_breaks == []


# --- Cohesion.MisusedConnective tests ---


def test_misused_adversative_high_overlap(tmp_path):
    """'However' between highly similar sentences should flag."""
    md = """# Section

Deploy the application to the production server immediately.

However, deploy the application to the staging server first.
"""
    issues = run_engine_on_text(md, tmp_path)
    misused = [it for it in issues if it.get("check") == "Cohesion.MisusedConnective"]
    assert len(misused) > 0
    assert "contrast" in misused[0].get("message", "").lower()


def test_misused_causal_no_shared_nouns(tmp_path):
    """'Therefore' with no shared nouns should flag."""
    md = """# Section

Configure the database connection pool for optimal throughput.

Therefore, orchids require indirect sunlight and high humidity levels.
"""
    issues = run_engine_on_text(md, tmp_path)
    misused = [it for it in issues if it.get("check") == "Cohesion.MisusedConnective"]
    assert len(misused) > 0
    assert "cause" in misused[0].get("message", "").lower()


def test_correct_adversative_no_flag(tmp_path):
    """'However' with genuinely different content should not flag."""
    md = """# Section

The legacy API returns all responses in XML format.

However, the redesigned API exclusively uses JSON for all responses.
"""
    issues = run_engine_on_text(md, tmp_path)
    misused = [it for it in issues if it.get("check") == "Cohesion.MisusedConnective"]
    assert misused == []


def test_sequential_connective_not_validated(tmp_path):
    """Sequential connectives like 'first' and 'next' should not be validated."""
    md = """# Section

First, install the required dependencies for the project.

Next, configure the database connection settings properly.
"""
    issues = run_engine_on_text(md, tmp_path)
    misused = [it for it in issues if it.get("check") == "Cohesion.MisusedConnective"]
    assert misused == []
