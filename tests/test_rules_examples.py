import pytest
from rhetoric_lint.engine import RhetoricEngine

# These tests require the AST parser (mistletoe)
pytest.importorskip("mistletoe")


def _run_md(md: str, tmp_path):
    p = tmp_path / "doc.md"
    p.write_text(md, encoding="utf-8")
    engine = RhetoricEngine()
    return engine.lint_files([str(p)])


def test_missing_h1_reports_heading_warning(tmp_path):
    md = """## Section only\n\nThis document has no top-level heading.\n"""
    issues = _run_md(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Heading.H1" in checks


def test_long_sentence_flagged(tmp_path):
    # create a sentence longer than MAX_SENTENCE_TOKENS
    from rhetoric_lint.const import MAX_SENTENCE_TOKENS

    long_sentence = "word " * (MAX_SENTENCE_TOKENS + 5)
    md = f"""# Title\n\nThis paragraph contains a very long sentence: {long_sentence}\n"""
    issues = _run_md(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Attention.LongSentence" in checks


def test_list_parallelism_detects_outlier(tmp_path):
    md = """# Title\n\n- Run the tests\n- Build the project\n- Deploy the app\n- Packaging the release\n"""
    issues = _run_md(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Symmetry.Parallelism" in checks


def test_result_verification_flags_task_list_without_example(tmp_path):
    md = """# Title\n\n## How to deploy\n\n1. Build the container\n2. Push to registry\n3. Deploy to cluster\n\n## Notes\n\nSome other text.\n"""
    issues = _run_md(md, tmp_path)
    checks = {it.get("check") for it in issues}
    assert "Completeness.ResultVerification" in checks
