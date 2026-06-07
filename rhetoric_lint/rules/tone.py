"""Rhetoric.ToneImbalance — authoritative or negative framing that alienates readers."""
import re
from typing import Any, Dict, List

GENRES = frozenset({"all"})


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context["path"]
    text = context.get("text", "")
    doc = context.get("doc")
    genre = context.get("genre", "general")
    const = context.get("const")

    if not text or not doc:
        return []

    authoritative = getattr(const, "AUTHORITATIVE_MODALS", [
        "must", "shall", "required", "have to", "need to", "always", "never",
    ]) if const else ["must", "shall", "required", "have to", "need to", "always", "never"]

    negative = getattr(const, "NEGATIVE_FRAMING", [
        "cannot", "can't", "won't", "will not", "do not", "don't", "never",
        "fail", "error", "invalid", "broken", "missing", "unable",
    ]) if const else [
        "cannot", "can't", "won't", "will not", "do not", "don't", "never",
        "fail", "error", "invalid", "broken", "missing", "unable",
    ]

    auth_max = getattr(const, "TONE_AUTHORITATIVE_MAX", 0.15) if const else 0.15
    neg_max = getattr(const, "TONE_NEGATIVE_MAX", 0.20) if const else 0.20
    instructional = getattr(const, "TONE_INSTRUCTIONAL_GENRES", frozenset({"howto", "tutorial"})) if const else frozenset({"howto", "tutorial"})

    severity = (
        const.RULE_SEVERITY_LEVELS.get("Rhetoric.ToneImbalance", "suggestion")
        if const else "suggestion"
    )

    alpha_tokens = [t for t in doc if t.is_alpha]
    if not alpha_tokens:
        return []

    text_lower = text.lower()
    total = len(alpha_tokens)

    def _count_phrases(phrases: List[str]) -> int:
        count = 0
        for phrase in phrases:
            if " " in phrase:
                count += len(re.findall(re.escape(phrase), text_lower))
            else:
                pattern = r"\b" + re.escape(phrase) + r"\b"
                count += len(re.findall(pattern, text_lower))
        return count

    auth_count = _count_phrases(authoritative)
    neg_count = _count_phrases(negative)

    auth_ratio = auth_count / max(1, total)
    neg_ratio = neg_count / max(1, total)

    issues: List[Dict[str, Any]] = []

    if genre in instructional and auth_ratio > auth_max:
        issues.append({
            "path": path,
            "line": 1,
            "column": 1,
            "message": (
                f"Authoritative tone in instructional document "
                f"(ratio {auth_ratio:.2f} > {auth_max}) — "
                f"prefer empathetic language that respects reader autonomy."
            ),
            "severity": severity,
            "check": "Rhetoric.ToneImbalance",
        })
    elif neg_ratio > neg_max:
        issues.append({
            "path": path,
            "line": 1,
            "column": 1,
            "message": (
                f"High negative framing (ratio {neg_ratio:.2f} > {neg_max}) — "
                f"consider reframing constraints as positive guidance where possible."
            ),
            "severity": severity,
            "check": "Rhetoric.ToneImbalance",
        })

    return issues
