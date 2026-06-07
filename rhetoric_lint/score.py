"""
score.py — linter/server boundary.

The server sub-package calls score_file() and imports nothing else from this package.
Rules, runners, engine, and spaCy are invisible to the server.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DimensionScore:
    name: str
    finding_count: int
    density: float  # findings per 1000 words


@dataclass
class ScoreResult:
    path: str
    word_count: int
    genre: str
    doc_template: str
    dimensions: dict[str, DimensionScore] = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    badge_suppressed: bool = False  # True when word_count < const.SCORE_MIN_WORDS


def score_file(
    path: str,
    findings: list[dict],
    context: dict,
    word_count: int | None = None,
) -> ScoreResult:
    """
    Compute a ScoreResult from a completed lint pass.

    Called by the server or CLI score command. Never called by rules or runners.
    context must contain: 'genre', 'doc_template'.
    word_count: pre-computed token count; if None, derived from context['doc'].
    """
    from rhetoric_lint import const

    if word_count is None:
        doc = context.get("doc")
        word_count = len([t for t in doc if not t.is_space and not t.is_punct]) if doc else 0

    badge_suppressed = word_count < const.SCORE_MIN_WORDS

    dimension_map: dict[str, list[str]] = const.DIMENSION_MAP
    dimension_default: str = const.DIMENSION_DEFAULT

    counts: dict[str, int] = {dim: 0 for dim in dimension_map}
    counts[dimension_default] = counts.get(dimension_default, 0)

    for finding in findings:
        check = finding.get("check", "")
        assigned = dimension_default
        for dim, prefixes in dimension_map.items():
            if any(check == p or check.startswith(p + ".") for p in prefixes):
                assigned = dim
                break
        counts[assigned] = counts.get(assigned, 0) + 1

    denominator = max(word_count, 1)
    dimensions = {
        dim: DimensionScore(
            name=dim,
            finding_count=counts.get(dim, 0),
            density=round(counts.get(dim, 0) / denominator * 1000, 2),
        )
        for dim in (set(dimension_map) | {dimension_default})
    }

    return ScoreResult(
        path=path,
        word_count=word_count,
        genre=context.get("genre", ""),
        doc_template=context.get("doc_template", ""),
        dimensions=dimensions,
        findings=findings,
        badge_suppressed=badge_suppressed,
    )
