"""Tests for Coverage.MissingJobCoverage (SP12)."""

from __future__ import annotations

import json
import pytest

pytest.importorskip("mistletoe")

import rhetoric_lint.const as const
from rhetoric_lint.engine import RhetoricEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manifest(jobs: list[dict]) -> dict:
    return {
        "version": "1.0",
        "source_path": "/fake/src",
        "jobs": jobs,
    }


def _make_job(statement: str, step: str = "Confirm/SCA", coverage: str = "missing") -> dict:
    return {
        "id": "JOB-001",
        "statement_text": statement,
        "job_map_step": step,
        "swebok_ref": "swebok:security/sca",
        "coverage": coverage,
        "actor": "consumer",
        "signal_source": "library_import",
        "confidence": 0.90,
    }


def _run(tmp_path, doc_text: str, manifest: dict | None, *, min_confidence: float = 0.0):
    p = tmp_path / "doc.md"
    p.write_text(doc_text)

    original_path = const.JTBD_MANIFEST_PATH
    try:
        if manifest is not None:
            mf = tmp_path / "manifest.json"
            mf.write_text(json.dumps(manifest))
            const.JTBD_MANIFEST_PATH = str(mf)
        else:
            const.JTBD_MANIFEST_PATH = ""

        eng = RhetoricEngine()
        issues = eng.lint_files([str(p)])
        return [i for i in issues if i["check"] == "Coverage.MissingJobCoverage"]
    finally:
        const.JTBD_MANIFEST_PATH = original_path


# ---------------------------------------------------------------------------
# Must-fire
# ---------------------------------------------------------------------------

def test_fires_for_missing_job(tmp_path):
    manifest = _make_manifest([_make_job("validate dependencies for CVEs", coverage="missing")])
    doc = "# Guide\n\nThis document describes the API.\n"
    findings = _run(tmp_path, doc, manifest)
    assert len(findings) == 1
    assert findings[0]["check"] == "Coverage.MissingJobCoverage"
    assert "validate dependencies for CVEs" in findings[0]["message"]
    assert "swebok:security/sca" in findings[0]["message"]


def test_fires_multiple_missing_jobs(tmp_path):
    manifest = _make_manifest([
        _make_job("validate dependencies for CVEs", coverage="missing"),
        _make_job("deploy application to environment", step="Deploy", coverage="missing"),
    ])
    doc = "# Guide\n\nThis document contains unrelated content.\n"
    findings = _run(tmp_path, doc, manifest)
    assert len(findings) == 2


# ---------------------------------------------------------------------------
# Must-not-fire: job is covered
# ---------------------------------------------------------------------------

def test_no_finding_when_covered(tmp_path):
    manifest = _make_manifest([_make_job("validate dependencies for CVEs", coverage="covered")])
    doc = "# Guide\n\nThis document describes the API.\n"
    findings = _run(tmp_path, doc, manifest)
    assert findings == []


def test_no_finding_when_partial(tmp_path):
    manifest = _make_manifest([_make_job("validate dependencies for CVEs", coverage="partial")])
    doc = "# Guide\n\nThis document describes the API.\n"
    findings = _run(tmp_path, doc, manifest)
    assert findings == []


# ---------------------------------------------------------------------------
# Must-not-fire: paragraph matches job tokens above threshold
# ---------------------------------------------------------------------------

def test_no_finding_when_paragraph_covers_job(tmp_path):
    manifest = _make_manifest([_make_job("validate dependencies for CVEs", coverage="missing")])
    # Short paragraph concentrated on the same tokens as the job statement.
    # job tokens (after stopwords): {validate, dependencies, cves}
    # para tokens: {validate, dependencies, against, cves, check} → Jaccard = 3/5 = 0.60
    doc = (
        "# Security\n\n"
        "Validate dependencies against CVEs. Check each dependency.\n"
    )
    findings = _run(tmp_path, doc, manifest)
    assert findings == []


# ---------------------------------------------------------------------------
# Must-not-fire: no manifest path set
# ---------------------------------------------------------------------------

def test_no_finding_when_manifest_path_empty(tmp_path):
    doc = "# Guide\n\nThis document describes the API.\n"
    findings = _run(tmp_path, doc, manifest=None)
    assert findings == []


def test_no_finding_when_manifest_file_missing(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("# Guide\n\nContent.\n")
    original = const.JTBD_MANIFEST_PATH
    try:
        const.JTBD_MANIFEST_PATH = str(tmp_path / "nonexistent.json")
        eng = RhetoricEngine()
        issues = eng.lint_files([str(p)])
        findings = [i for i in issues if i["check"] == "Coverage.MissingJobCoverage"]
        assert findings == []
    finally:
        const.JTBD_MANIFEST_PATH = original


# ---------------------------------------------------------------------------
# Must-not-fire: corpus precision test
# ---------------------------------------------------------------------------

def test_no_false_positives_on_corpus(tmp_path):
    """Rule must not fire on the technical corpus when no manifest is set."""
    import os
    corpus = os.path.join(
        os.path.dirname(__file__), "fixtures", "corpus", "technical"
    )
    if not os.path.isdir(corpus):
        pytest.skip("corpus not found")

    files = [
        os.path.join(corpus, f)
        for f in os.listdir(corpus)
        if f.endswith(".md")
    ][:5]  # check a subset for speed

    original = const.JTBD_MANIFEST_PATH
    try:
        const.JTBD_MANIFEST_PATH = ""
        eng = RhetoricEngine()
        issues = eng.lint_files(files)
        findings = [i for i in issues if i["check"] == "Coverage.MissingJobCoverage"]
        assert findings == []
    finally:
        const.JTBD_MANIFEST_PATH = original
