"""Shared readability preprocessing and scoring — used by ValeStyleRunner and rules/readability.py."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    import textstat as _textstat
    _TEXTSTAT_OK = True
except ImportError:
    _textstat = None  # type: ignore[assignment]
    _TEXTSTAT_OK = False

_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_SHORT_ITEM_RE = re.compile(r"^\s*\S+(?:\s+\S+){0,2}\s*$")  # < 4 words

_PROSE_NODE_TYPES = frozenset({"Paragraph", "ListItem", "BlockQuote"})
_SKIP_NODE_TYPES = frozenset({
    "Heading", "CodeFence", "FencedCode", "BlockCode",
    "Table", "TableRow", "TableCell", "HTMLBlock", "Image",
})


def preprocess_for_readability(sections: List[Dict[str, Any]], raw_text: str = "") -> str:
    """
    Collect paragraph, list item, and blockquote text; exclude headings and code.
    Inline code characters replaced with '*'. Colons → periods. Short list items removed.
    Returns a single prose string suitable for readability metric computation.
    """
    chunks: List[str] = []

    for sec in sections:
        for para in sec.get("paragraphs", []):
            nodes = para.get("nodes", [])
            if not nodes:
                text = para.get("text", "").strip()
                if text:
                    chunks.append(_clean_chunk(text))
                continue

            for node in nodes:
                ntype = node.get("type", "")
                if ntype in _SKIP_NODE_TYPES:
                    continue
                if ntype in _PROSE_NODE_TYPES or not ntype:
                    node_text = node.get("text", "").strip()
                    if not node_text:
                        continue
                    # For list items, skip very short ones (< 4 words)
                    if ntype == "ListItem" and _SHORT_ITEM_RE.match(node_text):
                        continue
                    chunks.append(_clean_chunk(node_text))

    return " ".join(chunks)


def _clean_chunk(text: str) -> str:
    # Replace inline code chars with *
    def _replace_inline(m: re.Match) -> str:
        inner = m.group(0)
        return "*" * len(inner)

    text = _INLINE_CODE_RE.sub(_replace_inline, text)
    # Colons → periods (helps sentence detection)
    text = text.replace(":", ".")
    return text.strip()


VALE_METRIC_FN: Dict[str, Any] = {}
if _TEXTSTAT_OK:
    VALE_METRIC_FN = {
        "Flesch-Kincaid":          _textstat.flesch_kincaid_grade,
        "SMOG":                    _textstat.smog_index,
        "Gunning Fog":             _textstat.gunning_fog,
        "Coleman-Liau":            _textstat.coleman_liau_index,
        "Automated Readability":   _textstat.automated_readability_index,
        "Flesch Reading Ease":     _textstat.flesch_reading_ease,
    }

_METRIC_RANGES: Dict[str, Dict[str, float]] = {
    "flesch_reading_ease":         {"min": 0.0,  "max": 100.0},
    "gunning_fog":                 {"min": 19.0, "max": 6.0},
    "automated_readability_index": {"min": 22.0, "max": 6.0},
    "dale_chall_readability_score":{"min": 11.0, "max": 4.9},
    "coleman_liau_index":          {"min": 19.0, "max": 6.0},
}
_WEIGHTS: Dict[str, float] = {
    "flesch_reading_ease":          0.1653977378,
    "gunning_fog":                  0.2228367277,
    "automated_readability_index":  0.2325290236,
    "dale_chall_readability_score": 0.1960641698,
    "coleman_liau_index":           0.1831723411,
}


def composite_score(text: str) -> Optional[float]:
    """Return Lexi composite score 0–100 (higher = more readable), or None if textstat absent."""
    if not _TEXTSTAT_OK or not text.strip():
        return None
    score = 0.0
    for key, weight in _WEIGHTS.items():
        fn_map = {
            "flesch_reading_ease":          _textstat.flesch_reading_ease,
            "gunning_fog":                  _textstat.gunning_fog,
            "automated_readability_index":  _textstat.automated_readability_index,
            "dale_chall_readability_score": _textstat.dale_chall_readability_score,
            "coleman_liau_index":           _textstat.coleman_liau_index,
        }
        fn = fn_map.get(key)
        if not fn:
            continue
        raw = fn(text)
        rng = _METRIC_RANGES[key]
        lo, hi = rng["min"], rng["max"]
        if lo < hi:
            normed = max(0.0, min(1.0, (raw - lo) / (hi - lo)))
        else:
            normed = max(0.0, min(1.0, (lo - raw) / (lo - hi)))
        score += normed * weight
    return round(score * 100, 1)
