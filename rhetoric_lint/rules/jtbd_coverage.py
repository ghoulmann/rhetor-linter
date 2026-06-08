"""
SP12 — Coverage.MissingJobCoverage

Fires a warning for each job in a jtbd-manifest.json where coverage == "missing"
and this file's paragraphs do not meet JTBD_COVERAGE_JACCARD_MIN.

Disabled when const.JTBD_MANIFEST_PATH is empty (default).
"""

from __future__ import annotations

import re

from rhetoric_lint.overlap import set_overlap_metrics

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "in", "of", "to", "for", "with",
    "on", "at", "by", "from", "is", "are", "be", "was", "were",
    "it", "its", "this", "that", "these", "those", "not", "no",
})


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"\b[a-z]{2,}\b", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


def check(context: dict) -> list[dict]:
    if not context.get("const").JTBD_MANIFEST_PATH:
        return []

    manifest = context.get("jtbd_manifest")
    if not manifest:
        return []

    threshold = context["const"].JTBD_COVERAGE_JACCARD_MIN
    sections = context.get("sections", [])
    path = context["path"]

    findings = []
    for job in manifest.get("jobs", []):
        if job.get("coverage") != "missing":
            continue

        job_tokens = _tokenize(job.get("statement_text", ""))
        if not job_tokens:
            continue

        best = 0.0
        for section in sections:
            for para in section.get("paragraphs", []):
                para_tokens = _tokenize(para.get("text", ""))
                score = set_overlap_metrics(job_tokens, para_tokens).get("jaccard", 0.0)
                if score > best:
                    best = score

        if best < threshold:
            findings.append({
                "path":     path,
                "line":     1,
                "column":   0,
                "check":    "Coverage.MissingJobCoverage",
                "severity": "warning",
                "message": (
                    f"Job '{job['statement_text']}' ({job['job_map_step']}) "
                    f"has no documentation coverage (best Jaccard: {best:.3f} < {threshold}). "
                    f"SWEBOK ref: {job.get('swebok_ref', '')}"
                ),
            })

    return findings
