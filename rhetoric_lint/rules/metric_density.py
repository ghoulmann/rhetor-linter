"""Attention.MetricDensity — excessive numeric/metric values in prose sentences."""
import re
from typing import Any, Dict, List

GENRES = frozenset({"all"})

_SKIP_NODE_TYPES = frozenset({
    "Code", "CodeFence", "FencedCode", "BlockCode",
    "Image", "BlockQuote",
})

_METRIC_RE = re.compile(
    r"\d+(?:\.\d+)?(?:%|ms|MB|GB|TB|KB|px|rem|em|pt|rpm|x\b|°C|°F|Hz|kHz|MHz|GHz|bps|Mbps|Gbps)"
    r"|\b\d{4,}\b"  # bare large numbers (years excluded by context)
)


def _is_numeric_token(token) -> bool:
    return token.like_num or token.is_digit or bool(_METRIC_RE.search(token.text))


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context["path"]
    sections = context.get("sections", [])
    const = context.get("const")
    issues: List[Dict[str, Any]] = []

    ratio_threshold = getattr(const, "METRIC_DENSITY_RATIO", 0.30) if const else 0.30
    window_size = getattr(const, "METRIC_DENSITY_WINDOW", 10) if const else 10
    window_max = getattr(const, "METRIC_DENSITY_WINDOW_MAX", 3) if const else 3
    min_tokens = getattr(const, "METRIC_DENSITY_MIN_TOKENS", 12) if const else 12
    severity = (
        const.RULE_SEVERITY_LEVELS.get("Attention.MetricDensity", "suggestion")
        if const else "suggestion"
    )

    for sec in sections:
        for para in sec.get("paragraphs", []):
            nodes = para.get("nodes", [])
            if nodes and any(n.get("type") in _SKIP_NODE_TYPES for n in nodes):
                continue
            # Skip table rows
            if nodes and any(n.get("type") in ("TableCell", "TableRow") for n in nodes):
                continue
            doc = para.get("doc")
            if not doc:
                continue
            para_line = para.get("line", 1)

            for sent in doc.sents:
                tokens = [t for t in sent if not t.is_space]
                if len(tokens) < min_tokens:
                    continue

                numeric_count = sum(1 for t in tokens if _is_numeric_token(t))
                ratio = numeric_count / len(tokens)

                if ratio > ratio_threshold:
                    issues.append({
                        "path": path,
                        "line": para_line,
                        "column": 1,
                        "message": (
                            f"High metric density in sentence "
                            f"({numeric_count}/{len(tokens)} numeric tokens, "
                            f"ratio {ratio:.2f}) — consider moving metrics to a table."
                        ),
                        "severity": severity,
                        "check": "Attention.MetricDensity",
                    })
    return issues
