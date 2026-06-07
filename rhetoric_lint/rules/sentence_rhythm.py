"""Attention.SentenceRhythm — monotonous or wildly uneven sentence-length pacing."""
import statistics
from typing import Any, Dict, List

GENRES = frozenset({"all"})

_SKIP_NODE_TYPES = frozenset({
    "Code", "CodeFence", "FencedCode", "BlockCode", "Image",
})


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context["path"]
    sections = context.get("sections", [])
    const = context.get("const")
    issues: List[Dict[str, Any]] = []

    cv_max = getattr(const, "SENTENCE_RHYTHM_CV_MAX", 0.8) if const else 0.8
    spike_ratio = getattr(const, "SENTENCE_RHYTHM_SPIKE_RATIO", 4.0) if const else 4.0
    min_sentences = getattr(const, "SENTENCE_RHYTHM_MIN_SENTENCES", 4) if const else 4
    severity = (
        const.RULE_SEVERITY_LEVELS.get("Attention.SentenceRhythm", "suggestion")
        if const else "suggestion"
    )

    for sec in sections:
        lengths: List[int] = []
        first_line = None

        for para in sec.get("paragraphs", []):
            nodes = para.get("nodes", [])
            if nodes and any(n.get("type") in _SKIP_NODE_TYPES for n in nodes):
                continue
            doc = para.get("doc")
            if not doc:
                continue
            if first_line is None:
                first_line = para.get("line", 1)

            for sent in doc.sents:
                tokens = [t for t in sent if not t.is_space and not t.is_punct]
                if tokens:
                    lengths.append(len(tokens))

        if len(lengths) < min_sentences:
            continue

        mean = statistics.mean(lengths)
        if mean == 0:
            continue

        stdev = statistics.stdev(lengths) if len(lengths) > 1 else 0.0
        cv = stdev / mean
        lo, hi = min(lengths), max(lengths)
        ratio = hi / lo if lo > 0 else 0.0

        fired = False
        if cv > cv_max:
            issues.append({
                "path": path,
                "line": first_line or 1,
                "column": 1,
                "message": (
                    f"Uneven sentence rhythm in '{sec.get('heading', 'section')}' "
                    f"(CV={cv:.2f}, mean={mean:.0f} tokens, "
                    f"range {lo}–{hi}) — vary sentence length more evenly."
                ),
                "severity": severity,
                "check": "Attention.SentenceRhythm",
            })
            fired = True

        if not fired and ratio > spike_ratio:
            issues.append({
                "path": path,
                "line": first_line or 1,
                "column": 1,
                "message": (
                    f"Sentence length spike in '{sec.get('heading', 'section')}' "
                    f"(longest {hi} tokens vs shortest {lo}) — "
                    "consider breaking the longest sentence."
                ),
                "severity": severity,
                "check": "Attention.SentenceRhythm",
            })

    return issues
