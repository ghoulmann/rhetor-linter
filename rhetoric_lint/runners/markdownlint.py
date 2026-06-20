"""SP3/SP5: Native markdownlint rules + markdownlint-cli2 Python custom rule extension."""
from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import yaml

from rhetoric_lint.runners.base import StyleRunner

# ---------------------------------------------------------------------------
# Defaults and constants
# ---------------------------------------------------------------------------

_DEFAULTS: Dict[str, Any] = {
    "MD003": {"style": "atx"},
    # MD004 disabled by default — mixed markers common in real-world docs
    "MD004": {"disabled": True},
    # MD007 disabled by default — list indentation style varies widely
    "MD007": {"disabled": True},
    "MD010": {"code_blocks": True, "spaces_per_tab": 4},
    "MD012": {"maximum": 1},
    "MD013": {"line_length": 80, "code_blocks": True, "tables": True},
    "MD022": {"lines_above": 1, "lines_below": 1},
    "MD026": {"punctuation": ".,;:!?。，；：！？"},
    "MD029": {"style": "one_or_ordered"},
    # MD030 disabled by default — spacing style varies widely in real-world docs
    "MD030": {"disabled": True},
    "MD031": {"list_items": False},
    "MD032": {},
    # MD033 disabled by default — HTML is common in technical docs; enable via allowed_elements config
    "MD033": {"disabled": True},
    "MD035": {"style": "consistent"},
    "MD043": {"headings": [], "match_case": False},
    "MD044": {"names": [], "code_blocks": True},
    # MD046 disabled by default — indented code blocks are widespread; enable via style config
    "MD046": {"disabled": True},
    "MD048": {"style": "consistent"},
    # MD049/MD050 disabled by default — mixed emphasis style is common in existing docs
    "MD049": {"disabled": True},
    "MD050": {"disabled": True},
    "MD054": {"autolink": True, "inline": True, "full": True, "collapsed": True, "shortcut": True},
    "MD055": {"style": "consistent"},
    # Rules disabled by default to avoid false positives on real-world docs
    "MD005": {"disabled": True},   # list indent variance common in real-world docs
    "MD014": {"disabled": True},   # $ in shell commands is common convention
    "MD023": {"disabled": True},   # setext-style headings may appear indented in edge cases
    "MD024": {"disabled": True},   # duplicate headings common in API docs
    "MD026": {"disabled": True},   # ? in headings valid in FAQs
    "MD027": {"disabled": True},   # multi-space after > intentional in some blockquote styles
    "MD028": {"disabled": True},   # blank line in blockquote common for multi-paragraph blocks
    "MD034": {"disabled": True},   # bare URLs extremely common in technical docs
    "MD036": {"disabled": True},   # emphasis-as-heading check is too aggressive
    "MD038": {"disabled": True},   # spaces in code span legitimate in demo/example docs
    "MD051": {"disabled": True},   # link fragments need raw text (engine strips content)
    "MD053": {"disabled": True},   # unused defs need raw text (engine strips defs)
    "MD060": {"disabled": True},   # trailing spaces in code blocks common in YAML alignment
}

_HEADING_ATX_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_HEADING_SETEXT_H1_RE = re.compile(r"^=+\s*$")
_HEADING_SETEXT_H2_RE = re.compile(r"^-+\s*$")
_FENCE_START_RE = re.compile(r"^(`{3,}|~{3,})")
_SUPPRESS_DISABLE_RE = re.compile(r"<!--\s*markdownlint-disable\s*(.*?)-->")
_SUPPRESS_ENABLE_RE = re.compile(r"<!--\s*markdownlint-enable\s*(.*?)-->")
_SUPPRESS_DISABLE_LINE_RE = re.compile(r"<!--\s*markdownlint-disable-line\s*(.*?)-->")
_SUPPRESS_DISABLE_NEXT_RE = re.compile(r"<!--\s*markdownlint-disable-next-line\s*(.*?)-->")


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_config(config_path: str, file_path: str) -> Dict[str, Any]:
    """Merge inline config + discovered project config. Per-rule dicts."""
    config: Dict[str, Any] = {}

    # Walk from file's dir toward root looking for .markdownlint.*
    search_dir = Path(file_path).parent if file_path else Path(".")
    candidates = [
        ".markdownlint.json",
        ".markdownlint.yaml",
        ".markdownlint.yml",
    ]
    for _ in range(12):  # max depth
        for name in candidates:
            candidate = search_dir / name
            if candidate.exists():
                try:
                    raw = candidate.read_text(encoding="utf-8")
                    loaded = json.loads(raw) if name.endswith(".json") else yaml.safe_load(raw)
                    if isinstance(loaded, dict):
                        config = loaded
                except Exception:
                    pass
                break
        parent = search_dir.parent
        if parent == search_dir:
            break
        search_dir = parent

    # Explicit config_path overrides discovery
    if config_path and os.path.exists(config_path):
        try:
            raw = Path(config_path).read_text(encoding="utf-8")
            loaded = json.loads(raw) if config_path.endswith(".json") else yaml.safe_load(raw)
            if isinstance(loaded, dict):
                config = loaded
        except Exception:
            pass

    # Normalize: boolean True → {}, False → disabled
    normalized: Dict[str, Any] = {}
    for key, val in config.items():
        if isinstance(val, bool):
            normalized[key] = {} if val else {"disabled": True}
        elif isinstance(val, dict):
            normalized[key] = val
        else:
            normalized[key] = {}
    return normalized


def _rule_cfg(config: Dict[str, Any], rule_id: str) -> Optional[Dict[str, Any]]:
    """Return per-rule config dict, or None if disabled.

    Rules with ``{"disabled": True}`` in _DEFAULTS are off by default; users can
    re-enable them by setting the rule to ``true`` or a config dict in their
    .markdownlint file.
    """
    default = _DEFAULTS.get(rule_id, {})
    entry = config.get(rule_id)

    if entry is None:
        # No user config — honour the default; if default says disabled, skip
        if isinstance(default, dict) and default.get("disabled"):
            return None
        return dict(default)

    # User explicitly configured this rule
    if entry is False or (isinstance(entry, dict) and entry.get("disabled")):
        return None

    # User enables or overrides the rule — merge defaults (minus "disabled") with user values
    merged = {k: v for k, v in default.items() if k != "disabled"}
    if isinstance(entry, dict):
        merged.update(entry)
    return merged


# ---------------------------------------------------------------------------
# Pre-scan helpers
# ---------------------------------------------------------------------------

def _code_fence_lines(lines: List[str]) -> Set[int]:
    """1-indexed set of line numbers inside fenced code blocks (including fence lines).

    Uses mistletoe AST for correctness — handles indented fences (inside list items
    and blockquotes) and 4+ backtick fences. Falls back to regex scanning on parse error.
    Only CodeFence nodes are included (not BlockCode / indented code blocks), so MD046
    can still detect indented blocks.
    """
    try:
        import mistletoe
        from mistletoe.block_token import CodeFence

        text = "".join(lines)
        doc = mistletoe.Document(text)
        result: Set[int] = set()

        def _walk(node: Any) -> None:
            if isinstance(node, CodeFence):
                start = node.line_number
                content = ""
                if node.children:
                    content = getattr(node.children[0], "content", "") or ""
                n_content = content.count("\n")
                end = start + n_content + 1  # opener + content lines + closer
                result.update(range(start, end + 1))
            if hasattr(node, "children") and node.children:
                for child in node.children:
                    _walk(child)

        _walk(doc)
        return result
    except Exception:
        return _code_fence_lines_regex(lines)


def _code_fence_lines_regex(lines: List[str]) -> Set[int]:
    """Fallback regex-based fence scanner (col-0 fences only)."""
    inside = False
    fence_char: str = ""
    fence_len = 0
    result: Set[int] = set()
    for i, line in enumerate(lines, start=1):
        m = _FENCE_START_RE.match(line)
        if not inside:
            if m:
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                inside = True
                result.add(i)
        else:
            result.add(i)
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len:
                inside = False
    return result


def _suppressed_lines(lines: List[str]) -> Dict[int, Set[str]]:
    """Return dict: line_no → set of suppressed rule IDs (empty set = all)."""
    suppressed: Dict[int, Set[str]] = {}
    globally_disabled: Set[str] = set()  # rules disabled until re-enabled
    all_disabled = False  # all rules disabled

    def _add(line_no: int, rules: Set[str]) -> None:
        if line_no not in suppressed:
            suppressed[line_no] = set()
        suppressed[line_no].update(rules)

    for i, line in enumerate(lines, start=1):
        # Apply global suppression carried forward
        if all_disabled:
            suppressed[i] = set()  # empty = all rules
        elif globally_disabled:
            _add(i, set(globally_disabled))

        # markdownlint-disable-line
        m = _SUPPRESS_DISABLE_LINE_RE.search(line)
        if m:
            rules_str = m.group(1).strip()
            rules = set(rules_str.split()) if rules_str else set()
            _add(i, rules)

        # markdownlint-disable-next-line
        m = _SUPPRESS_DISABLE_NEXT_RE.search(line)
        if m:
            rules_str = m.group(1).strip()
            rules = set(rules_str.split()) if rules_str else set()
            _add(i + 1, rules)

        # markdownlint-disable (block) — takes effect from this line onward
        m = _SUPPRESS_DISABLE_RE.search(line)
        if m and not _SUPPRESS_DISABLE_LINE_RE.search(line) and not _SUPPRESS_DISABLE_NEXT_RE.search(line):
            rules_str = m.group(1).strip()
            if rules_str:
                globally_disabled.update(rules_str.split())
                _add(i, set(rules_str.split()))
            else:
                all_disabled = True
                suppressed[i] = set()  # suppress current line too

        # markdownlint-enable (re-enable)
        m = _SUPPRESS_ENABLE_RE.search(line)
        if m:
            rules_str = m.group(1).strip()
            if rules_str:
                for r in rules_str.split():
                    globally_disabled.discard(r)
            else:
                globally_disabled.clear()
                all_disabled = False

    return suppressed


def _is_suppressed(suppressed: Dict[int, Set[str]], line_no: int, rule_id: str) -> bool:
    entry = suppressed.get(line_no)
    if entry is None:
        return False
    return len(entry) == 0 or rule_id in entry  # empty = all rules


def _heading_info(lines: List[str]) -> List[Tuple[int, int, str, str]]:
    """Return list of (line_no, level, text, style) for each heading.
    style is 'atx', 'atx_closed', or 'setext'.
    """
    results = []
    for i, line in enumerate(lines, start=1):
        m = _HEADING_ATX_RE.match(line)
        if m:
            hashes = m.group(1)
            text = m.group(2).rstrip("#").strip()
            style = "atx_closed" if line.rstrip().endswith("#") and not line.rstrip().endswith(m.group(1)) else "atx"
            results.append((i, len(hashes), text, style))
        elif i > 1:
            prev = lines[i - 2].rstrip()
            if _HEADING_SETEXT_H1_RE.match(line) and prev and not prev.startswith("#"):
                results.append((i - 1, 1, prev, "setext"))
            elif _HEADING_SETEXT_H2_RE.match(line) and prev and not prev.startswith("#") and len(prev) > 1:
                results.append((i - 1, 2, prev, "setext"))
    return results


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------

def _md001(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD001: Heading levels should only increment by one level at a time."""
    issues = []
    headings = _heading_info(lines)
    prev_level = 0
    for line_no, level, text, style in headings:
        if _is_suppressed(suppressed, line_no, "MD001"):
            prev_level = level
            continue
        if prev_level > 0 and level > prev_level + 1:
            issues.append({
                "path": path, "line": line_no, "column": 1,
                "message": f"Heading levels should only increment by one level at a time; expected h{prev_level + 1}, found h{level}",
                "severity": severity, "check": "markdownlint.MD001",
            })
        prev_level = level
    return issues


def _md003(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD003: Heading style — must be consistent (default: atx)."""
    issues = []
    style = cfg.get("style", "atx")
    headings = _heading_info(lines)
    if not headings:
        return []

    # "consistent" = first heading's style sets the rule
    if style == "consistent":
        style = headings[0][3]

    for line_no, level, text, h_style in headings:
        if _is_suppressed(suppressed, line_no, "MD003"):
            continue
        expected = style.replace("_closed", "")  # atx_closed vs atx both target atx lines
        if h_style != style:
            hashes = "#" * level
            fix_line = f"{hashes} {text}"
            issues.append({
                "path": path, "line": line_no, "column": 1,
                "message": f"Heading style should be {style!r}",
                "severity": severity, "check": "markdownlint.MD003",
                "fix": fix_line,
            })
    return issues


def _md009(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD009: Trailing spaces."""
    issues = []
    br_spaces = cfg.get("br_spaces", 0)  # allow N trailing spaces for hard line break
    strict = cfg.get("strict", False)

    for i, line in enumerate(lines, start=1):
        if _is_suppressed(suppressed, i, "MD009"):
            continue
        stripped = line.rstrip("\n\r")
        trailing = len(stripped) - len(stripped.rstrip(" \t"))
        if trailing == 0:
            continue
        if not strict and br_spaces > 0 and trailing == br_spaces:
            continue
        if i in fence_set:
            continue
        issues.append({
            "path": path, "line": i, "column": len(stripped.rstrip(" \t")) + 1,
            "message": f"Trailing spaces: {trailing} space(s)",
            "severity": severity, "check": "markdownlint.MD009",
            "fix": stripped.rstrip(" \t"),
        })
    return issues


def _md010(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD010: Hard tabs."""
    issues = []
    code_blocks = cfg.get("code_blocks", True)
    spaces = " " * cfg.get("spaces_per_tab", 4)

    for i, line in enumerate(lines, start=1):
        if _is_suppressed(suppressed, i, "MD010"):
            continue
        if not code_blocks and i in fence_set:
            continue
        if "\t" not in line:
            continue
        col = line.index("\t") + 1
        fix = line.rstrip("\n").replace("\t", spaces)
        issues.append({
            "path": path, "line": i, "column": col,
            "message": "Hard tabs found",
            "severity": severity, "check": "markdownlint.MD010",
            "fix": fix,
        })
    return issues


def _md012(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD012: Multiple consecutive blank lines."""
    issues = []
    maximum = cfg.get("maximum", 1)
    blank_run = 0
    run_start = 0

    for i, line in enumerate(lines, start=1):
        if line.strip() == "":
            if blank_run == 0:
                run_start = i
            blank_run += 1
            if blank_run > maximum and not _is_suppressed(suppressed, i, "MD012"):
                # Report once per run (at the first excess line)
                if blank_run == maximum + 1:
                    issues.append({
                        "path": path, "line": i, "column": 1,
                        "message": f"Multiple consecutive blank lines: found {blank_run}, maximum {maximum}",
                        "severity": severity, "check": "markdownlint.MD012",
                        "fix": "",  # delete the excess line
                    })
        else:
            blank_run = 0
    return issues


def _md013(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD013: Line length."""
    issues = []
    limit = cfg.get("line_length", 80)
    check_code = cfg.get("code_blocks", True)
    check_tables = cfg.get("tables", True)

    for i, line in enumerate(lines, start=1):
        if _is_suppressed(suppressed, i, "MD013"):
            continue
        actual = len(line.rstrip("\n\r"))
        if actual <= limit:
            continue
        if not check_code and i in fence_set:
            continue
        if not check_tables and line.lstrip().startswith("|"):
            continue
        issues.append({
            "path": path, "line": i, "column": limit + 1,
            "message": f"Line length {actual} exceeds {limit}",
            "severity": severity, "check": "markdownlint.MD013",
        })
    return issues


def _md022(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD022: Headings should be surrounded by blank lines."""
    issues = []
    above = cfg.get("lines_above", 1)
    below = cfg.get("lines_below", 1)
    n = len(lines)

    headings = _heading_info(lines)
    for line_no, level, text, style in headings:
        if _is_suppressed(suppressed, line_no, "MD022"):
            continue
        idx = line_no - 1  # 0-indexed

        # Check blank lines above (skip for first line in file)
        if above > 0 and idx > 0:
            # Count blank lines immediately above
            blanks = 0
            for k in range(idx - 1, max(-1, idx - above - 1), -1):
                if lines[k].strip() == "":
                    blanks += 1
                else:
                    break
            if blanks < above:
                issues.append({
                    "path": path, "line": line_no, "column": 1,
                    "message": f"Headings should be surrounded by blank lines (missing blank line above)",
                    "severity": severity, "check": "markdownlint.MD022",
                    "fix": "\n" + lines[idx].rstrip("\n"),
                })

        # Check blank lines below
        if below > 0 and idx + 1 < n:
            blanks = 0
            for k in range(idx + 1, min(n, idx + below + 1)):
                if lines[k].strip() == "":
                    blanks += 1
                else:
                    break
            if blanks < below:
                issues.append({
                    "path": path, "line": line_no, "column": 1,
                    "message": f"Headings should be surrounded by blank lines (missing blank line below)",
                    "severity": severity, "check": "markdownlint.MD022",
                    "fix": lines[idx].rstrip("\n") + "\n",
                })
    return issues


def _md025(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD025: Single H1 per document."""
    issues = []
    h1_lines = []
    for line_no, level, text, style in _heading_info(lines):
        if level == 1:
            h1_lines.append(line_no)

    for line_no in h1_lines[1:]:  # flag all H1s after the first
        if not _is_suppressed(suppressed, line_no, "MD025"):
            issues.append({
                "path": path, "line": line_no, "column": 1,
                "message": "Multiple top-level headings in the same document",
                "severity": severity, "check": "markdownlint.MD025",
            })
    return issues


_LIST_ITEM_RE = re.compile(r"^(\s*)([-*+]|\d+[.)]) ")
_TABLE_ROW_RE = re.compile(r"^\s*\|")
_TABLE_DELIM_RE = re.compile(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$")
_IMG_EMPTY_ALT_RE = re.compile(r"!\[\s*\]\(")
_IMG_HTML_RE = re.compile(r"<img\b([^>]*)>", re.IGNORECASE)
_IMG_ALT_ATTR_RE = re.compile(r'\balt\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.IGNORECASE)

# --- Additional regexes for new rules ---
_HORIZ_RULE_RE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
_ORDERED_MARKER_RE = re.compile(r"^(\s*)(\d+)([.)]) ")
_UNORDERED_MARKER_RE = re.compile(r"^(\s*)([-*+]) ")
_BARE_URL_RE = re.compile(r"(?<![<\[(\"'`])\bhttps?://\S+")
_REF_DEF_RE = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s+\S")
_REF_LINK_USE_RE = re.compile(r"\[([^\]]+)\]\[([^\]]*)\]")
_INLINE_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_INLINE_CODE_SPAN_RE = re.compile(r"`+")
_HTML_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)(\s[^>]*)?>", re.IGNORECASE)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_NON_DESC_LINK_TEXT_RE = re.compile(
    r"\[(?:here|click here|this link|read more|learn more|more|link|this|click)\]\(",
    re.IGNORECASE,
)


def _blockquote_regions(lines: List[str]) -> List[Tuple[int, int]]:
    """Return (start_1idx, end_1idx) ranges for contiguous blockquote blocks."""
    regions: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for i, line in enumerate(lines, start=1):
        is_bq = line.lstrip().startswith(">")
        if is_bq and start is None:
            start = i
        elif not is_bq and start is not None:
            regions.append((start, i - 1))
            start = None
    if start is not None:
        regions.append((start, len(lines)))
    return regions


def _link_ref_definitions(lines: List[str], fence_set: Set[int]) -> Dict[str, int]:
    """Return lowercase label → 1-based line_no for [label]: url definition lines."""
    result: Dict[str, int] = {}
    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            continue
        m = _REF_DEF_RE.match(line)
        if m:
            result[m.group(1).lower()] = i
    return result


def _heading_to_anchor(text: str) -> str:
    """GitHub-style anchor slug from heading text."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # strip inline links
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def _inline_code_spans(line: str) -> List[Tuple[int, int]]:
    """Return list of (start, end) char ranges occupied by inline code spans."""
    spans: List[Tuple[int, int]] = []
    i = 0
    while i < len(line):
        if line[i] == "`":
            j = i
            while j < len(line) and line[j] == "`":
                j += 1
            tick_len = j - i
            # Find matching closing ticks
            k = j
            while k < len(line):
                if line[k] == "`":
                    m = k
                    while m < len(line) and line[m] == "`":
                        m += 1
                    if m - k == tick_len:
                        spans.append((i, m))
                        i = m
                        break
                    k = m
                else:
                    k += 1
            else:
                i = j
        else:
            i += 1
    return spans


def _in_code_span(col: int, spans: List[Tuple[int, int]]) -> bool:
    return any(s <= col < e for s, e in spans)


def _md031(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD031: Fenced code blocks should be surrounded by blank lines."""
    issues = []
    n = len(lines)
    fence_starts: List[int] = []
    fence_ends: List[int] = []
    inside = False
    fence_char = ""
    fence_len = 0

    for i, line in enumerate(lines, start=1):
        m = _FENCE_START_RE.match(line)
        if not inside:
            if m:
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                inside = True
                fence_starts.append(i)
        else:
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len:
                inside = False
                fence_ends.append(i)

    for start in fence_starts:
        if _is_suppressed(suppressed, start, "MD031"):
            continue
        # Check blank line above (not first line)
        if start > 1 and lines[start - 2].strip() != "":
            prev_line = lines[start - 2]
            # Allow if inside a list item
            if not cfg.get("list_items", False) and _LIST_ITEM_RE.match(prev_line):
                continue
            issues.append({
                "path": path, "line": start, "column": 1,
                "message": "Fenced code blocks should be surrounded by blank lines (missing blank line before)",
                "severity": severity, "check": "markdownlint.MD031",
                "fix": "\n" + lines[start - 1].rstrip("\n"),
            })

    for end in fence_ends:
        if _is_suppressed(suppressed, end, "MD031"):
            continue
        # Check blank line below (not last line)
        if end < n and lines[end].strip() != "":
            issues.append({
                "path": path, "line": end, "column": 1,
                "message": "Fenced code blocks should be surrounded by blank lines (missing blank line after)",
                "severity": severity, "check": "markdownlint.MD031",
                "fix": lines[end - 1].rstrip("\n") + "\n",
            })
    return issues


def _md032(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD032: Lists should be surrounded by blank lines."""
    issues = []
    n = len(lines)

    # Find list start/end line numbers
    in_list = False
    list_start = 0

    def _is_list_item(line: str) -> bool:
        return bool(_LIST_ITEM_RE.match(line))

    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            if in_list:
                in_list = False
            continue
        is_item = _is_list_item(line)
        if is_item and not in_list:
            in_list = True
            list_start = i
            # Check blank line above
            if list_start > 1 and lines[list_start - 2].strip() != "":
                prev = lines[list_start - 2]
                # Don't flag if previous line is also a list item
                if not _is_list_item(prev) and not _is_suppressed(suppressed, list_start, "MD032"):
                    issues.append({
                        "path": path, "line": list_start, "column": 1,
                        "message": "Lists should be surrounded by blank lines (missing blank line before)",
                        "severity": severity, "check": "markdownlint.MD032",
                        "fix": "\n" + line.rstrip("\n"),
                    })
        elif not is_item and in_list:
            in_list = False
            list_end = i - 1
            # Check blank line after
            if i <= n and line.strip() != "":
                if not _is_suppressed(suppressed, list_end, "MD032"):
                    issues.append({
                        "path": path, "line": list_end, "column": 1,
                        "message": "Lists should be surrounded by blank lines (missing blank line after)",
                        "severity": severity, "check": "markdownlint.MD032",
                        "fix": lines[list_end - 1].rstrip("\n") + "\n",
                    })
    return issues


def _md045(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD045: Images should have alternate text."""
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            continue
        if _is_suppressed(suppressed, i, "MD045"):
            continue
        stripped = line.rstrip("\n\r")
        # Markdown image with empty alt: ![](...) or ![ ](...)
        if _IMG_EMPTY_ALT_RE.search(stripped):
            issues.append({
                "path": path, "line": i, "column": 1,
                "message": "Images should have alternate text (alt text)",
                "severity": severity, "check": "markdownlint.MD045",
            })
            continue
        # HTML <img> with missing or empty alt attribute
        for m in _IMG_HTML_RE.finditer(stripped):
            attrs = m.group(1)
            alt_m = _IMG_ALT_ATTR_RE.search(attrs)
            if alt_m is None or (alt_m.group(1) or alt_m.group(2) or "") == "":
                issues.append({
                    "path": path, "line": i, "column": m.start() + 1,
                    "message": "Images should have alternate text (alt text)",
                    "severity": severity, "check": "markdownlint.MD045",
                })
    return issues


def _md048(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD048: Fence marker style — backtick vs tilde consistency."""
    style_cfg = cfg.get("style", "consistent")

    # Collect all fence openers and their style
    backtick_lines: List[int] = []
    tilde_lines: List[int] = []
    inside = False
    open_char = ""
    open_len = 0

    for i, line in enumerate(lines, start=1):
        m = _FENCE_START_RE.match(line)
        if not inside:
            if m:
                ch = m.group(1)[0]
                open_char = ch
                open_len = len(m.group(1))
                inside = True
                if ch == "`":
                    backtick_lines.append(i)
                else:
                    tilde_lines.append(i)
        else:
            if m and m.group(1)[0] == open_char and len(m.group(1)) >= open_len:
                inside = False

    issues = []

    if style_cfg == "consistent":
        if not backtick_lines or not tilde_lines:
            return []
        # Minority style = whichever has fewer occurrences
        if len(backtick_lines) <= len(tilde_lines):
            minority_lines = backtick_lines
            majority_char = "~"
        else:
            minority_lines = tilde_lines
            majority_char = "`"
        for line_no in minority_lines:
            if _is_suppressed(suppressed, line_no, "MD048"):
                continue
            raw = lines[line_no - 1].rstrip("\n\r")
            fence_match = _FENCE_START_RE.match(raw)
            if fence_match:
                fix = majority_char * len(fence_match.group(1)) + raw[fence_match.end():]
            else:
                fix = None
            issue: Dict[str, Any] = {
                "path": path, "line": line_no, "column": 1,
                "message": "Fence marker style should be consistent; use the majority style",
                "severity": severity, "check": "markdownlint.MD048",
            }
            if fix is not None:
                issue["fix"] = fix
            issues.append(issue)
    elif style_cfg == "backtick":
        for line_no in tilde_lines:
            if _is_suppressed(suppressed, line_no, "MD048"):
                continue
            raw = lines[line_no - 1].rstrip("\n\r")
            fence_match = _FENCE_START_RE.match(raw)
            fix = "`" * len(fence_match.group(1)) + raw[fence_match.end():] if fence_match else None
            issue = {
                "path": path, "line": line_no, "column": 1,
                "message": "Fence marker style should use backticks",
                "severity": severity, "check": "markdownlint.MD048",
            }
            if fix is not None:
                issue["fix"] = fix
            issues.append(issue)
    elif style_cfg == "tilde":
        for line_no in backtick_lines:
            if _is_suppressed(suppressed, line_no, "MD048"):
                continue
            raw = lines[line_no - 1].rstrip("\n\r")
            fence_match = _FENCE_START_RE.match(raw)
            fix = "~" * len(fence_match.group(1)) + raw[fence_match.end():] if fence_match else None
            issue = {
                "path": path, "line": line_no, "column": 1,
                "message": "Fence marker style should use tildes",
                "severity": severity, "check": "markdownlint.MD048",
            }
            if fix is not None:
                issue["fix"] = fix
            issues.append(issue)

    return issues


def _md040(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD040: Fenced code blocks should have a language specified."""
    issues = []
    inside = False
    fence_char = ""
    fence_len = 0

    for i, line in enumerate(lines, start=1):
        m = _FENCE_START_RE.match(line)
        if not inside:
            if m:
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                inside = True
                rest = line[m.end():].strip()
                if not rest and not _is_suppressed(suppressed, i, "MD040"):
                    issues.append({
                        "path": path, "line": i, "column": 1,
                        "message": "Fenced code blocks should have a language specified",
                        "severity": severity, "check": "markdownlint.MD040",
                    })
        else:
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len:
                inside = False
    return issues


def _md041(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
    genre: str,
) -> List[Dict[str, Any]]:
    """MD041: First line should be a top-level heading."""
    genre_gate = cfg.get("rhetoric-genre")
    if genre_gate and genre not in genre_gate:
        return []

    for i, line in enumerate(lines, start=1):
        if _is_suppressed(suppressed, i, "MD041"):
            return []
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            return []
        return [{
            "path": path, "line": 1, "column": 1,
            "message": "First line in a file should be a top-level heading",
            "severity": severity, "check": "markdownlint.MD041",
        }]
    return []


# ---------------------------------------------------------------------------
# Group A — Heading whitespace (MD018–MD021, MD023, MD026)
# ---------------------------------------------------------------------------

def _md018(lines, cfg, suppressed, fence_set, path, severity):
    """MD018: No space after hash on atx heading."""
    _RE = re.compile(r"^(#{1,6})([^ #\t\n\r])")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD018"):
            continue
        m = _RE.match(line)
        if m:
            hashes = m.group(1)
            rest = line[len(hashes):].rstrip("\n\r")
            issues.append({
                "path": path, "line": i, "column": 1,
                "message": "No space after hash on atx heading",
                "severity": severity, "check": "markdownlint.MD018",
                "fix": f"{hashes} {rest}",
            })
    return issues


def _md019(lines, cfg, suppressed, fence_set, path, severity):
    """MD019: Multiple spaces after hash on atx heading."""
    _RE = re.compile(r"^(#{1,6})  +")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD019"):
            continue
        m = _RE.match(line)
        if m:
            hashes = m.group(1)
            rest = line[m.end():].rstrip("\n\r")
            issues.append({
                "path": path, "line": i, "column": 1,
                "message": "Multiple spaces after hash on atx heading",
                "severity": severity, "check": "markdownlint.MD019",
                "fix": f"{hashes} {rest}",
            })
    return issues


def _md020(lines, cfg, suppressed, fence_set, path, severity):
    """MD020: No space inside closed atx heading."""
    # Closed ATX: #+ <content> #+  — flag when space is missing between hash and content.
    # Require non-empty content surrounded by at least one non-hash char on each side so
    # that bare `### ` (empty heading) and `### text` (non-closed ATX) don't match.
    _RE = re.compile(r"^(#{1,6})([^#\n]+?)(#{1,6})\s*$")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD020"):
            continue
        raw = line.rstrip("\n\r")
        m = _RE.match(raw)
        if not m:
            continue
        hashes_open = m.group(1)
        inner = m.group(2)
        hashes_close = m.group(3)
        # Only closed atx (ends with hashes)
        if not inner.strip():
            continue
        text = inner.strip()
        if inner.startswith(" ") and inner.endswith(" "):
            continue  # already has spaces
        issues.append({
            "path": path, "line": i, "column": 1,
            "message": "No space inside closed atx heading",
            "severity": severity, "check": "markdownlint.MD020",
            "fix": f"{hashes_open} {text} {hashes_close}",
        })
    return issues


def _md021(lines, cfg, suppressed, fence_set, path, severity):
    """MD021: Multiple spaces inside closed atx heading."""
    _RE = re.compile(r"^(#{1,6})\s+(.*?)\s+(#{1,6})\s*$")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD021"):
            continue
        raw = line.rstrip("\n\r")
        m = _RE.match(raw)
        if not m:
            continue
        hashes_open = m.group(1)
        inner = m.group(2)
        hashes_close = m.group(3)
        # Check if leading/trailing spaces > 1
        after_open = raw[len(hashes_open):]
        before_close = raw[:raw.rindex(hashes_close)].rstrip()
        leading = len(after_open) - len(after_open.lstrip())
        trailing_text = before_close[len(hashes_open):]
        trailing = len(trailing_text) - len(trailing_text.rstrip())
        if leading > 1 or trailing > 1:
            text = inner.strip()
            issues.append({
                "path": path, "line": i, "column": 1,
                "message": "Multiple spaces inside closed atx heading",
                "severity": severity, "check": "markdownlint.MD021",
                "fix": f"{hashes_open} {text} {hashes_close}",
            })
    return issues


def _md023(lines, cfg, suppressed, fence_set, path, severity):
    """MD023: Headings must start at the beginning of the line."""
    _RE = re.compile(r"^(\s+)(#{1,6})\s")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD023"):
            continue
        m = _RE.match(line)
        if m:
            hashes = m.group(2)
            rest = line[m.end(1):].rstrip("\n\r")
            issues.append({
                "path": path, "line": i, "column": 1,
                "message": "Headings must start at the beginning of the line",
                "severity": severity, "check": "markdownlint.MD023",
                "fix": rest,
            })
    return issues


def _md026(lines, cfg, suppressed, fence_set, path, severity):
    """MD026: Trailing punctuation in heading."""
    punct = cfg.get("punctuation", ".,;:!?。，；：！？")
    issues = []
    for line_no, level, text, style in _heading_info(lines):
        if _is_suppressed(suppressed, line_no, "MD026"):
            continue
        if line_no in fence_set:
            continue
        if text and text[-1] in punct:
            raw = lines[line_no - 1].rstrip("\n\r")
            fix = raw.rstrip(punct)
            issues.append({
                "path": path, "line": line_no, "column": 1,
                "message": f"Trailing punctuation in heading: {text[-1]!r}",
                "severity": severity, "check": "markdownlint.MD026",
                "fix": fix,
            })
    return issues


# ---------------------------------------------------------------------------
# Group B — Blockquote (MD027, MD028)
# ---------------------------------------------------------------------------

def _md027(lines, cfg, suppressed, fence_set, path, severity):
    """MD027: Multiple spaces after blockquote symbol."""
    _RE = re.compile(r"^(\s*>)( {2,})(.*)")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD027"):
            continue
        m = _RE.match(line.rstrip("\n\r"))
        if m:
            prefix = m.group(1)
            rest = m.group(3)
            issues.append({
                "path": path, "line": i, "column": 1,
                "message": "Multiple spaces after blockquote symbol",
                "severity": severity, "check": "markdownlint.MD027",
                "fix": f"{prefix} {rest}",
            })
    return issues


def _md028(lines, cfg, suppressed, fence_set, path, severity):
    """MD028: Blank line inside blockquote (between two blockquote blocks)."""
    issues = []
    n = len(lines)
    for i, line in enumerate(lines, start=1):
        if i in fence_set or line.strip() != "":
            continue
        if _is_suppressed(suppressed, i, "MD028"):
            continue
        # Check that previous non-blank line is a blockquote line
        prev_bq = False
        for j in range(i - 2, -1, -1):
            if j + 1 in fence_set:
                break
            if lines[j].strip():
                prev_bq = lines[j].lstrip().startswith(">")
                break
        if not prev_bq:
            continue
        # Check that next non-blank line is also a blockquote line
        next_bq = False
        for j in range(i, n):
            if j + 1 in fence_set:
                break
            if lines[j].strip():
                next_bq = lines[j].lstrip().startswith(">")
                break
        if next_bq:
            issues.append({
                "path": path, "line": i, "column": 1,
                "message": "Blank line found inside blockquote",
                "severity": severity, "check": "markdownlint.MD028",
            })
    return issues


# ---------------------------------------------------------------------------
# Group C — List rules (MD004, MD005, MD007, MD029, MD030)
# ---------------------------------------------------------------------------

def _md004(lines, cfg, suppressed, fence_set, path, severity):
    """MD004: Unordered list marker style consistency."""
    style_cfg = cfg.get("style", "consistent")
    ul_items: List[Tuple[int, str]] = []  # (line_no, marker)
    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            continue
        m = _UNORDERED_MARKER_RE.match(line)
        if m:
            ul_items.append((i, m.group(2)))

    if not ul_items:
        return []

    if style_cfg == "consistent":
        first_marker = ul_items[0][1]
        issues = []
        for line_no, marker in ul_items:
            if marker != first_marker and not _is_suppressed(suppressed, line_no, "MD004"):
                raw = lines[line_no - 1].rstrip("\n\r")
                fix = first_marker + raw[raw.index(marker) + 1:]
                issues.append({
                    "path": path, "line": line_no, "column": 1,
                    "message": f"Unordered list marker {marker!r} inconsistent; expected {first_marker!r}",
                    "severity": severity, "check": "markdownlint.MD004",
                    "fix": fix,
                })
        return issues

    # Named styles: dash, asterisk, plus
    expected = {
        "dash": "-", "asterisk": "*", "plus": "+",
        "sublist": None,  # complex; skip
    }.get(style_cfg)
    if not expected:
        return []

    issues = []
    for line_no, marker in ul_items:
        if marker != expected and not _is_suppressed(suppressed, line_no, "MD004"):
            raw = lines[line_no - 1].rstrip("\n\r")
            m = _UNORDERED_MARKER_RE.match(raw)
            if m:
                indent = m.group(1)
                rest = raw[m.end():]
                issues.append({
                    "path": path, "line": line_no, "column": 1,
                    "message": f"Unordered list marker {marker!r}; expected {expected!r}",
                    "severity": severity, "check": "markdownlint.MD004",
                    "fix": f"{indent}{expected} {rest}",
                })
    return issues


def _md005(lines, cfg, suppressed, fence_set, path, severity):
    """MD005: Inconsistent indentation for list items at the same level."""
    # Track expected indent at each nesting level for current list run
    issues = []
    indent_stack: List[int] = []  # expected indent for each nesting level

    in_list = False
    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            in_list = False
            indent_stack = []
            continue
        ul_m = _UNORDERED_MARKER_RE.match(line)
        ol_m = _ORDERED_MARKER_RE.match(line)
        m = ul_m or ol_m
        if not m:
            if line.strip():
                in_list = False
                indent_stack = []
            continue
        in_list = True
        indent = len(m.group(1))

        # Determine nesting level by indent
        if not indent_stack:
            indent_stack.append(indent)
        elif indent > indent_stack[-1]:
            indent_stack.append(indent)
        elif indent < indent_stack[-1]:
            # Pop back
            while len(indent_stack) > 1 and indent < indent_stack[-1]:
                indent_stack.pop()

        expected_indent = indent_stack[-1]
        if indent != expected_indent and not _is_suppressed(suppressed, i, "MD005"):
            raw = lines[i - 1].rstrip("\n\r")
            rest = raw.lstrip()
            issues.append({
                "path": path, "line": i, "column": 1,
                "message": f"Inconsistent indentation: expected {expected_indent} spaces, found {indent}",
                "severity": severity, "check": "markdownlint.MD005",
                "fix": " " * expected_indent + rest,
            })
    return issues


def _md007(lines, cfg, suppressed, fence_set, path, severity):
    """MD007: Unordered list indentation."""
    indent_size = cfg.get("indent", 2)
    start_indented = cfg.get("start_indented", False)
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD007"):
            continue
        m = _UNORDERED_MARKER_RE.match(line)
        if not m:
            continue
        indent = len(m.group(1))
        if start_indented:
            if indent % indent_size != 0:
                raw = line.rstrip("\n\r")
                rest = raw.lstrip()
                corrected = (indent // indent_size) * indent_size
                issues.append({
                    "path": path, "line": i, "column": 1,
                    "message": f"Unordered list indentation should be a multiple of {indent_size}",
                    "severity": severity, "check": "markdownlint.MD007",
                    "fix": " " * corrected + rest,
                })
        else:
            if indent > 0 and indent % indent_size != 0:
                raw = line.rstrip("\n\r")
                rest = raw.lstrip()
                corrected = ((indent + indent_size - 1) // indent_size) * indent_size
                issues.append({
                    "path": path, "line": i, "column": 1,
                    "message": f"Unordered list indentation should be a multiple of {indent_size}",
                    "severity": severity, "check": "markdownlint.MD007",
                    "fix": " " * corrected + rest,
                })
    return issues


def _md029(lines, cfg, suppressed, fence_set, path, severity):
    """MD029: Ordered list item prefix style."""
    style_cfg = cfg.get("style", "one_or_ordered")
    issues = []

    # Collect ordered list runs: list of [(line_no, number, delim, raw)]
    runs: List[List[Tuple[int, int, str, str]]] = []
    current_run: List[Tuple[int, int, str, str]] = []
    in_list = False
    prev_indent = -1

    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            if current_run:
                runs.append(current_run)
                current_run = []
            in_list = False
            continue
        m = _ORDERED_MARKER_RE.match(line)
        if m:
            indent = len(m.group(1))
            num = int(m.group(2))
            delim = m.group(3)
            if not in_list or indent != prev_indent:
                if current_run and indent != prev_indent:
                    runs.append(current_run)
                    current_run = []
            current_run.append((i, num, delim, line.rstrip("\n\r")))
            in_list = True
            prev_indent = indent
        elif line.strip():
            if current_run:
                runs.append(current_run)
                current_run = []
            in_list = False
            prev_indent = -1

    if current_run:
        runs.append(current_run)

    for run in runs:
        if len(run) < 1:
            continue
        first_num = run[0][1]
        delim = run[0][2]

        for idx, (line_no, num, d, raw) in enumerate(run):
            if _is_suppressed(suppressed, line_no, "MD029"):
                continue
            expected = None
            if style_cfg == "one":
                expected = 1
            elif style_cfg == "zero":
                expected = 0
            elif style_cfg == "ordered":
                expected = (first_num or 1) + idx
            elif style_cfg == "one_or_ordered":
                # Detect: are all items "1." or properly ordered?
                all_one = all(r[1] == 1 for r in run)
                if all_one:
                    expected = 1
                else:
                    expected = (run[0][1] or 1) + idx

            if expected is not None and num != expected:
                m = _ORDERED_MARKER_RE.match(raw)
                if m:
                    indent = m.group(1)
                    rest = raw[m.end():]
                    issues.append({
                        "path": path, "line": line_no, "column": 1,
                        "message": f"Ordered list prefix {num}{delim} does not match style {style_cfg!r}",
                        "severity": severity, "check": "markdownlint.MD029",
                        "fix": f"{indent}{expected}{delim} {rest}",
                    })
    return issues


def _md030(lines, cfg, suppressed, fence_set, path, severity):
    """MD030: Spaces after list markers."""
    ul_single = cfg.get("ul_single", 1)
    ul_multi = cfg.get("ul_multi", 1)
    ol_single = cfg.get("ol_single", 1)
    ol_multi = cfg.get("ol_multi", 1)

    issues = []
    # Determine if each list item is single-line or multi-line
    # Multi-line = next line is not a list item AND is non-blank (continuation)
    n = len(lines)
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD030"):
            continue
        ul_m = _UNORDERED_MARKER_RE.match(line)
        ol_m = _ORDERED_MARKER_RE.match(line)
        if not (ul_m or ol_m):
            continue
        # Check if next non-fence line is continuation (non-blank, non-item)
        is_multi = False
        for j in range(i, min(i + 3, n)):
            next_line = lines[j]  # 0-indexed, so lines[j] is line j+1
            if j + 1 in fence_set:
                break
            if next_line.strip() == "":
                break
            if _UNORDERED_MARKER_RE.match(next_line) or _ORDERED_MARKER_RE.match(next_line):
                break
            # Indented continuation
            if next_line.startswith("  ") or next_line.startswith("\t"):
                is_multi = True
                break

        if ul_m:
            expected_spaces = ul_multi if is_multi else ul_single
            marker = ul_m.group(2)
            after_marker = line[ul_m.end(2):]  # text after the marker char
            actual_spaces = len(after_marker) - len(after_marker.lstrip(" "))
            if actual_spaces != expected_spaces:
                indent = ul_m.group(1)
                content = after_marker.lstrip(" ").rstrip("\n\r")
                issues.append({
                    "path": path, "line": i, "column": 1,
                    "message": f"Spaces after list marker: expected {expected_spaces}, found {actual_spaces}",
                    "severity": severity, "check": "markdownlint.MD030",
                    "fix": f"{indent}{marker}{' ' * expected_spaces}{content}",
                })
        elif ol_m:
            expected_spaces = ol_multi if is_multi else ol_single
            prefix = ol_m.group(2) + ol_m.group(3)  # number + delimiter
            after_marker = line[ol_m.end(3):]
            actual_spaces = len(after_marker) - len(after_marker.lstrip(" "))
            if actual_spaces != expected_spaces:
                indent = ol_m.group(1)
                content = after_marker.lstrip(" ").rstrip("\n\r")
                issues.append({
                    "path": path, "line": i, "column": 1,
                    "message": f"Spaces after list marker: expected {expected_spaces}, found {actual_spaces}",
                    "severity": severity, "check": "markdownlint.MD030",
                    "fix": f"{indent}{prefix}{' ' * expected_spaces}{content}",
                })
    return issues


# ---------------------------------------------------------------------------
# Group D — Code block rules (MD014, MD046, MD060)
# ---------------------------------------------------------------------------

def _md014(lines, cfg, suppressed, fence_set, path, severity):
    """MD014: Dollar sign before shell commands without output."""
    issues = []
    # Find fenced code blocks; check if every non-empty line starts with '$'
    inside = False
    fence_char = ""
    fence_len = 0
    block_start = 0
    block_lines: List[Tuple[int, str]] = []

    def _check_block(block_start: int, block_lines: List[Tuple[int, str]]) -> List[Dict]:
        result = []
        non_empty = [(ln, l) for ln, l in block_lines if l.strip()]
        if not non_empty:
            return result
        all_dollar = all(l.lstrip().startswith("$ ") or l.lstrip() == "$" for _, l in non_empty)
        if not all_dollar:
            return result
        for line_no, raw in non_empty:
            if _is_suppressed(suppressed, line_no, "MD014"):
                continue
            stripped = raw.lstrip()
            if stripped.startswith("$ "):
                fixed = raw.replace("$ ", "", 1) if raw.lstrip().startswith("$ ") else raw
                # More careful fix: remove "$ " at the start of content
                indent = raw[: len(raw) - len(raw.lstrip())]
                content = stripped[2:].rstrip("\n\r")
                result.append({
                    "path": path, "line": line_no, "column": 1,
                    "message": "Dollar sign before shell command (no output shown)",
                    "severity": severity, "check": "markdownlint.MD014",
                    "fix": indent + content,
                })
        return result

    for i, line in enumerate(lines, start=1):
        m = _FENCE_START_RE.match(line)
        if not inside:
            if m:
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                inside = True
                block_start = i
                block_lines = []
        else:
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len:
                issues.extend(_check_block(block_start, block_lines))
                inside = False
            else:
                block_lines.append((i, line.rstrip("\n\r")))
    return issues


def _md046(lines, cfg, suppressed, fence_set, path, severity):
    """MD046: Code block style — fenced vs indented."""
    style_cfg = cfg.get("style", "fenced")

    # Detect indented code blocks: 4+ leading spaces, not inside list/blockquote
    # An indented block starts after a blank line and consists of 4+-space lines
    issues = []
    n = len(lines)
    in_fence = fence_set  # already computed

    # Collect fenced and indented block counts for "consistent" mode
    fenced_count = 0
    in_fence_block = False
    for i, line in enumerate(lines, start=1):
        m = _FENCE_START_RE.match(line)
        if not in_fence_block:
            if m:
                in_fence_block = True
                fenced_count += 1
        else:
            if m:
                in_fence_block = False

    # Detect indented blocks
    indented_block_starts: List[int] = []
    in_indented = False
    for i, line in enumerate(lines, start=1):
        if i in in_fence:
            in_indented = False
            continue
        stripped = line.rstrip("\n\r")
        is_blank = stripped.strip() == ""
        is_indented = not is_blank and (stripped.startswith("    ") or stripped.startswith("\t"))
        is_list = bool(_LIST_ITEM_RE.match(line))
        is_bq = stripped.lstrip().startswith(">")

        if is_indented and not is_list and not is_bq:
            if not in_indented:
                # Check previous line was blank or start of file
                prev_blank = i == 1 or lines[i - 2].strip() == ""
                if prev_blank:
                    in_indented = True
                    indented_block_starts.append(i)
        elif not is_blank:
            in_indented = False
        else:
            if in_indented:
                in_indented = False

    if not indented_block_starts:
        return []

    effective_style = style_cfg
    if style_cfg == "consistent":
        if fenced_count == 0 and indented_block_starts:
            effective_style = "indented"
        else:
            effective_style = "fenced"

    if effective_style == "fenced":
        for line_no in indented_block_starts:
            if _is_suppressed(suppressed, line_no, "MD046"):
                continue
            issues.append({
                "path": path, "line": line_no, "column": 1,
                "message": "Code block style: use fenced blocks instead of indented",
                "severity": severity, "check": "markdownlint.MD046",
            })
    # If style==indented, fenced blocks would be flagged — omit for now (rarely configured)
    return issues


def _md060(lines, cfg, suppressed, fence_set, path, severity):
    """MD060: No trailing spaces inside fenced code blocks."""
    issues = []
    for i, line in enumerate(lines, start=1):
        if i not in fence_set:
            continue
        if _is_suppressed(suppressed, i, "MD060"):
            continue
        raw = line.rstrip("\n\r")
        stripped = raw.rstrip(" \t")
        if len(stripped) < len(raw):
            issues.append({
                "path": path, "line": i, "column": len(stripped) + 1,
                "message": "Trailing spaces inside fenced code block",
                "severity": severity, "check": "markdownlint.MD060",
                "fix": stripped,
            })
    return issues


# ---------------------------------------------------------------------------
# Group E — Inline / link rules (MD011, MD034, MD037–MD039, MD042,
#                                 MD049–MD054, MD059)
# ---------------------------------------------------------------------------

def _md011(lines, cfg, suppressed, fence_set, path, severity):
    """MD011: Reversed link syntax (text)[url] → [text](url)."""
    _RE = re.compile(r"\(([^)]+)\)\[([^\]]+)\]")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD011"):
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for m in _RE.finditer(raw):
            if _in_code_span(m.start(), spans):
                continue
            text = m.group(1)
            url = m.group(2)
            fix = raw[:m.start()] + f"[{text}]({url})" + raw[m.end():]
            issues.append({
                "path": path, "line": i, "column": m.start() + 1,
                "message": "Reversed link syntax: use [text](url) not (text)[url]",
                "severity": severity, "check": "markdownlint.MD011",
                "fix": fix,
            })
    return issues


def _md034(lines, cfg, suppressed, fence_set, path, severity):
    """MD034: Bare URL — not inside <>, link, or code span."""
    _URL_RE = re.compile(r"https?://\S+")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD034"):
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for m in _URL_RE.finditer(raw):
            start = m.start()
            if _in_code_span(start, spans):
                continue
            # Inside <url>?
            if start > 0 and raw[start - 1] == "<":
                continue
            # Inside [text](url) or [text][url]?
            # Check if we're inside ( ... ) after a ]
            before = raw[:start]
            if before.endswith("]("):
                continue
            # Inside image alt text or link text
            bracket_depth = 0
            paren_depth = 0
            for ch in before:
                if ch == "[":
                    bracket_depth += 1
                elif ch == "]":
                    bracket_depth = max(0, bracket_depth - 1)
                elif ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth = max(0, paren_depth - 1)
            if paren_depth > 0:
                continue
            url = m.group(0).rstrip(".,;:!?)")
            fix = raw[:start] + f"<{url}>" + raw[start + len(url):]
            issues.append({
                "path": path, "line": i, "column": start + 1,
                "message": f"Bare URL found; use <{url}> or link syntax",
                "severity": severity, "check": "markdownlint.MD034",
                "fix": fix,
            })
    return issues


def _md037(lines, cfg, suppressed, fence_set, path, severity):
    """MD037: Spaces inside emphasis markers."""
    # Exclude {* ... *} MyST include directives via {* lookbehind on star pattern.
    # Exclude cross-span matches on underscore via word-boundary lookbehind/ahead:
    # opening _ must not be preceded by a word char; closing _ must not be followed by one.
    _STAR_RE = re.compile(r"(?<![*{])\*( [^*\n]+ )\*(?!\*)")
    _UNDER_RE = re.compile(r"(?<!\w)_( [^_\n]+ )_(?!\w)")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD037"):
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for pattern in (_STAR_RE, _UNDER_RE):
            for m in pattern.finditer(raw):
                if _in_code_span(m.start(), spans):
                    continue
                marker = raw[m.start()]
                inner = m.group(1).strip()
                fix = raw[:m.start()] + f"{marker}{inner}{marker}" + raw[m.end():]
                issues.append({
                    "path": path, "line": i, "column": m.start() + 1,
                    "message": "Spaces inside emphasis markers",
                    "severity": severity, "check": "markdownlint.MD037",
                    "fix": fix,
                })
    return issues


def _md038(lines, cfg, suppressed, fence_set, path, severity):
    """MD038: Spaces inside code span — check actual span content."""
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD038"):
            continue
        raw = line.rstrip("\n\r")
        # Use _inline_code_spans to find actual span boundaries
        for start, end in _inline_code_spans(raw):
            span_text = raw[start:end]
            # Measure backtick fence length
            tick_len = 0
            while tick_len < len(span_text) and span_text[tick_len] == "`":
                tick_len += 1
            inner = span_text[tick_len:len(span_text) - tick_len]
            if inner and inner[0] == " " and inner[-1] == " ":
                ticks = "`" * tick_len
                content = inner.strip()
                fix = raw[:start] + f"{ticks}{content}{ticks}" + raw[end:]
                issues.append({
                    "path": path, "line": i, "column": start + 1,
                    "message": "Spaces inside code span",
                    "severity": severity, "check": "markdownlint.MD038",
                    "fix": fix,
                })
    return issues


def _md039(lines, cfg, suppressed, fence_set, path, severity):
    """MD039: Spaces inside link brackets."""
    _RE = re.compile(r"\[ ([^\]]+) \]\(")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD039"):
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for m in _RE.finditer(raw):
            if _in_code_span(m.start(), spans):
                continue
            inner = m.group(1).strip()
            fix = raw[:m.start()] + f"[{inner}](" + raw[m.end():]
            issues.append({
                "path": path, "line": i, "column": m.start() + 1,
                "message": "Spaces inside link brackets",
                "severity": severity, "check": "markdownlint.MD039",
                "fix": fix,
            })
    return issues


def _md042(lines, cfg, suppressed, fence_set, path, severity):
    """MD042: Empty link destination or empty link text."""
    _EMPTY_DEST = re.compile(r"\[[^\]]+\]\(\s*\)")
    _EMPTY_TEXT = re.compile(r"\[\s*\]\([^)]+\)")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD042"):
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for pattern in (_EMPTY_DEST, _EMPTY_TEXT):
            for m in pattern.finditer(raw):
                if _in_code_span(m.start(), spans):
                    continue
                issues.append({
                    "path": path, "line": i, "column": m.start() + 1,
                    "message": "Empty link: link text or destination is empty",
                    "severity": severity, "check": "markdownlint.MD042",
                })
    return issues


def _md049(lines, cfg, suppressed, fence_set, path, severity):
    """MD049: Emphasis style consistency (* vs _)."""
    style_cfg = cfg.get("style", "consistent")
    # Two-pass: collect all single emphasis markers, then flag minority
    _STAR_RE = re.compile(r"(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)")
    _UNDER_RE = re.compile(r"(?<!_)_(?!_)([^_\n]+?)(?<!_)_(?!_)")

    star_lines: List[int] = []
    under_lines: List[int] = []

    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for m in _STAR_RE.finditer(raw):
            if not _in_code_span(m.start(), spans):
                star_lines.append(i)
        for m in _UNDER_RE.finditer(raw):
            if not _in_code_span(m.start(), spans):
                under_lines.append(i)

    if not star_lines and not under_lines:
        return []

    if style_cfg == "consistent":
        if not star_lines or not under_lines:
            return []  # already consistent
        # Flag minority
        if len(star_lines) <= len(under_lines):
            minority_lines = star_lines
            msg = "Emphasis style inconsistent; use _ for emphasis"
        else:
            minority_lines = under_lines
            msg = "Emphasis style inconsistent; use * for emphasis"
    elif style_cfg == "asterisk":
        minority_lines = under_lines
        msg = "Emphasis style should use *"
    else:  # underscore
        minority_lines = star_lines
        msg = "Emphasis style should use _"

    issues = []
    for line_no in minority_lines:
        if not _is_suppressed(suppressed, line_no, "MD049"):
            issues.append({
                "path": path, "line": line_no, "column": 1,
                "message": msg,
                "severity": severity, "check": "markdownlint.MD049",
            })
    return issues


def _md050(lines, cfg, suppressed, fence_set, path, severity):
    """MD050: Strong style consistency (** vs __)."""
    style_cfg = cfg.get("style", "consistent")
    _STAR_RE = re.compile(r"\*\*([^*\n]+?)\*\*")
    _UNDER_RE = re.compile(r"__([^_\n]+?)__")

    star_lines: List[int] = []
    under_lines: List[int] = []

    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for m in _STAR_RE.finditer(raw):
            if not _in_code_span(m.start(), spans):
                star_lines.append(i)
        for m in _UNDER_RE.finditer(raw):
            if not _in_code_span(m.start(), spans):
                under_lines.append(i)

    if not star_lines and not under_lines:
        return []

    if style_cfg == "consistent":
        if not star_lines or not under_lines:
            return []
        if len(star_lines) <= len(under_lines):
            minority_lines = star_lines
            msg = "Strong style inconsistent; use __ for strong"
        else:
            minority_lines = under_lines
            msg = "Strong style inconsistent; use ** for strong"
    elif style_cfg == "asterisk":
        minority_lines = under_lines
        msg = "Strong style should use **"
    else:
        minority_lines = star_lines
        msg = "Strong style should use __"

    issues = []
    for line_no in minority_lines:
        if not _is_suppressed(suppressed, line_no, "MD050"):
            issues.append({
                "path": path, "line": line_no, "column": 1,
                "message": msg,
                "severity": severity, "check": "markdownlint.MD050",
            })
    return issues


def _md051(lines, cfg, suppressed, fence_set, path, severity, context=None):
    """MD051: Link fragment does not match any heading (structural rule)."""
    # Use AST headings if available
    headings_ctx = (context or {}).get("headings", [])
    _FRAG_RE = re.compile(r"\]\(#([^)]+)\)")

    if headings_ctx:
        anchors = {_heading_to_anchor(h.get("text", "")) for h in headings_ctx}
    else:
        # Fallback: parse headings from raw lines
        anchors = {_heading_to_anchor(text) for _, _, text, _ in _heading_info(lines)}

    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD051"):
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for m in _FRAG_RE.finditer(raw):
            if _in_code_span(m.start(), spans):
                continue
            frag = m.group(1)
            if frag not in anchors:
                issues.append({
                    "path": path, "line": i, "column": m.start() + 1,
                    "message": f"Link fragment #{frag!r} does not match any heading",
                    "severity": severity, "check": "markdownlint.MD051",
                })
    return issues


def _md052(lines, cfg, suppressed, fence_set, path, severity):
    """MD052: Reference link label not defined."""
    ref_defs = _link_ref_definitions(lines, fence_set)
    # Engine strips link-ref definitions from preprocessed text; skip rule
    # when no definitions are visible to avoid false positives.
    if not ref_defs:
        return []
    # Shortcut form uses (?<!\w) to avoid matching CSS attribute selectors like
    # button[data-md-color-scheme] where [ is immediately preceded by a word char.
    _REF_USE_RE = re.compile(r"\[([^\]]+)\]\[([^\]]*)\]|(?<!\w)\[([^\]]+)\](?!\(|\[)")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD052"):
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for m in _REF_USE_RE.finditer(raw):
            if _in_code_span(m.start(), spans):
                continue
            if m.group(2) is not None:
                # [text][label] form
                label = m.group(2).strip().lower() or m.group(1).strip().lower()
            else:
                # [shortcut] form — label == text
                label = (m.group(3) or "").strip().lower()
            if label and label not in ref_defs:
                issues.append({
                    "path": path, "line": i, "column": m.start() + 1,
                    "message": f"Reference link label [{label!r}] not defined",
                    "severity": severity, "check": "markdownlint.MD052",
                })
    return issues


def _md053(lines, cfg, suppressed, fence_set, path, severity):
    """MD053: Unused link/image reference definitions."""
    ref_defs = _link_ref_definitions(lines, fence_set)
    if not ref_defs:
        return []

    # Collect all used labels from [text][label], [text][], [text] shortcut forms
    used_labels: Set[str] = set()
    _USE_RE = re.compile(r"\[([^\]]+)\]\[([^\]]*)\]|!\[([^\]]*)\]\[([^\]]*)\]")
    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for m in _USE_RE.finditer(raw):
            if _in_code_span(m.start(), spans):
                continue
            label = (m.group(2) or m.group(4) or "").strip().lower()
            text = (m.group(1) or m.group(3) or "").strip().lower()
            used_labels.add(label or text)

    issues = []
    for label, line_no in ref_defs.items():
        if label not in used_labels and not _is_suppressed(suppressed, line_no, "MD053"):
            issues.append({
                "path": path, "line": line_no, "column": 1,
                "message": f"Unused link reference definition: [{label}]",
                "severity": severity, "check": "markdownlint.MD053",
                "fix": "",  # delete the definition line
            })
    return issues


def _md054(lines, cfg, suppressed, fence_set, path, severity):
    """MD054: Link/image style consistency."""
    # Config booleans: autolink, inline, full, collapsed, shortcut
    # Flag link forms not allowed by config (all enabled by default → no findings)
    allow_autolink = cfg.get("autolink", True)
    allow_inline = cfg.get("inline", True)
    allow_full = cfg.get("full", True)
    allow_collapsed = cfg.get("collapsed", True)
    allow_shortcut = cfg.get("shortcut", True)

    if allow_autolink and allow_inline and allow_full and allow_collapsed and allow_shortcut:
        return []  # all allowed — no findings

    issues = []
    _AUTOLINK_RE = re.compile(r"<https?://[^>]+>")
    _INLINE_RE = re.compile(r"!?\[[^\]]*\]\([^)]*\)")
    _FULL_RE = re.compile(r"!?\[[^\]]+\]\[[^\]]+\]")
    _COLLAPSED_RE = re.compile(r"!?\[[^\]]+\]\[\]")
    _SHORTCUT_RE = re.compile(r"(?<!\])\[([^\]]+)\](?!\[|\()")

    checks = [
        (_AUTOLINK_RE, allow_autolink, "autolink"),
        (_FULL_RE, allow_full, "full reference"),
        (_COLLAPSED_RE, allow_collapsed, "collapsed reference"),
        (_INLINE_RE, allow_inline, "inline"),
    ]

    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD054"):
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for pattern, allowed, name in checks:
            if not allowed:
                for m in pattern.finditer(raw):
                    if not _in_code_span(m.start(), spans):
                        issues.append({
                            "path": path, "line": i, "column": m.start() + 1,
                            "message": f"Link/image {name} style not allowed by configuration",
                            "severity": severity, "check": "markdownlint.MD054",
                        })
    return issues


def _md059(lines, cfg, suppressed, fence_set, path, severity):
    """MD059: Non-descriptive link text."""
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD059"):
            continue
        raw = line.rstrip("\n\r")
        spans = _inline_code_spans(raw)
        for m in _NON_DESC_LINK_TEXT_RE.finditer(raw):
            if not _in_code_span(m.start(), spans):
                issues.append({
                    "path": path, "line": i, "column": m.start() + 1,
                    "message": "Non-descriptive link text; use meaningful text instead",
                    "severity": severity, "check": "markdownlint.MD059",
                })
    return issues


# ---------------------------------------------------------------------------
# Group F — Table rules (MD055, MD056, MD058)
# ---------------------------------------------------------------------------

def _md055(lines, cfg, suppressed, fence_set, path, severity):
    """MD055: Table pipe style consistency."""
    style_cfg = cfg.get("style", "consistent")
    # Collect all table rows (not delimiter rows)
    table_rows: List[Tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            continue
        raw = line.rstrip("\n\r")
        if not _TABLE_ROW_RE.match(raw):
            continue
        table_rows.append((i, raw))

    if not table_rows:
        return []

    def _row_style(row: str) -> str:
        has_leading = row.lstrip().startswith("|")
        has_trailing = row.rstrip().endswith("|")
        if has_leading and has_trailing:
            return "leading_and_trailing"
        elif has_leading:
            return "leading_only"
        elif has_trailing:
            return "trailing_only"
        return "no_leading_or_trailing"

    if style_cfg == "consistent":
        first_style = _row_style(table_rows[0][1])
        issues = []
        for line_no, row in table_rows[1:]:
            if _row_style(row) != first_style and not _is_suppressed(suppressed, line_no, "MD055"):
                issues.append({
                    "path": path, "line": line_no, "column": 1,
                    "message": f"Table pipe style inconsistent; expected {first_style!r}",
                    "severity": severity, "check": "markdownlint.MD055",
                })
        return issues

    issues = []
    for line_no, row in table_rows:
        if _row_style(row) != style_cfg and not _is_suppressed(suppressed, line_no, "MD055"):
            issues.append({
                "path": path, "line": line_no, "column": 1,
                "message": f"Table pipe style should be {style_cfg!r}",
                "severity": severity, "check": "markdownlint.MD055",
            })
    return issues


def _md056(lines, cfg, suppressed, fence_set, path, severity):
    """MD056: Table row column count mismatch."""
    issues = []
    # Find table blocks: consecutive rows with a delimiter row
    i = 0
    n = len(lines)
    while i < n:
        line_no = i + 1
        line = lines[i]
        if i + 1 in fence_set or not _TABLE_ROW_RE.match(line):
            i += 1
            continue
        # Start of a table — find delimiter row
        table_start = i
        j = i
        delim_idx = None
        while j < n and _TABLE_ROW_RE.match(lines[j]):
            if _TABLE_DELIM_RE.match(lines[j]):
                delim_idx = j
                break
            j += 1
        if delim_idx is None:
            i += 1
            continue

        # Count columns in delimiter row
        delim_row = lines[delim_idx].rstrip("\n\r")
        cells = [c for c in delim_row.split("|") if c.strip() or (delim_row.startswith("|") and delim_row.endswith("|"))]
        # More robust: strip leading/trailing | and split
        dr = delim_row.strip()
        if dr.startswith("|"):
            dr = dr[1:]
        if dr.endswith("|"):
            dr = dr[:-1]
        expected_cols = len(dr.split("|"))

        # Check all rows in the table
        k = table_start
        while k < n and _TABLE_ROW_RE.match(lines[k]):
            if k + 1 not in fence_set:
                row = lines[k].rstrip("\n\r").strip()
                if row.startswith("|"):
                    row = row[1:]
                if row.endswith("|"):
                    row = row[:-1]
                col_count = len(row.split("|"))
                if col_count != expected_cols and not _TABLE_DELIM_RE.match(lines[k]):
                    if not _is_suppressed(suppressed, k + 1, "MD056"):
                        issues.append({
                            "path": path, "line": k + 1, "column": 1,
                            "message": f"Table row has {col_count} columns; expected {expected_cols}",
                            "severity": severity, "check": "markdownlint.MD056",
                        })
            k += 1
        i = k

    return issues


def _md058(lines, cfg, suppressed, fence_set, path, severity):
    """MD058: Tables should be surrounded by blank lines."""
    issues = []
    n = len(lines)
    in_table = False
    table_start = 0

    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            in_table = False
            continue
        is_table_row = bool(_TABLE_ROW_RE.match(line))

        if is_table_row and not in_table:
            in_table = True
            table_start = i
            # Check blank line above
            if i > 1 and lines[i - 2].strip() != "" and not _is_suppressed(suppressed, i, "MD058"):
                issues.append({
                    "path": path, "line": i, "column": 1,
                    "message": "Table should be preceded by a blank line",
                    "severity": severity, "check": "markdownlint.MD058",
                    "fix": "\n" + line.rstrip("\n"),
                })
        elif not is_table_row and in_table:
            in_table = False
            table_end = i - 1
            # Check blank line after
            if i <= n and line.strip() != "" and not _is_suppressed(suppressed, table_end, "MD058"):
                issues.append({
                    "path": path, "line": table_end, "column": 1,
                    "message": "Table should be followed by a blank line",
                    "severity": severity, "check": "markdownlint.MD058",
                    "fix": lines[table_end - 1].rstrip("\n") + "\n",
                })
    return issues


# ---------------------------------------------------------------------------
# Group G — Document-level rules (MD024, MD033, MD035, MD036,
#                                   MD043, MD044, MD047)
# ---------------------------------------------------------------------------

def _md024(lines, cfg, suppressed, fence_set, path, severity, context=None):
    """MD024: Multiple headings with the same content."""
    allow_different_nesting = cfg.get("allow_different_nesting", False)
    headings = _heading_info(lines)
    issues = []

    if allow_different_nesting:
        # Only flag headings with same text AND same level
        seen: Dict[Tuple[int, str], int] = {}
        for line_no, level, text, style in headings:
            key = (level, text.lower())
            if key in seen and not _is_suppressed(suppressed, line_no, "MD024"):
                issues.append({
                    "path": path, "line": line_no, "column": 1,
                    "message": f"Duplicate heading: {text!r} (level {level})",
                    "severity": severity, "check": "markdownlint.MD024",
                })
            seen[key] = line_no
    else:
        seen_texts: Dict[str, int] = {}
        for line_no, level, text, style in headings:
            key = text.lower()
            if key in seen_texts and not _is_suppressed(suppressed, line_no, "MD024"):
                issues.append({
                    "path": path, "line": line_no, "column": 1,
                    "message": f"Duplicate heading: {text!r}",
                    "severity": severity, "check": "markdownlint.MD024",
                })
            seen_texts[key] = line_no
    return issues


def _md033(lines, cfg, suppressed, fence_set, path, severity):
    """MD033: Inline HTML not allowed."""
    allowed = [e.lower() for e in cfg.get("allowed_elements", [])]
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD033"):
            continue
        raw = line.rstrip("\n\r")
        # Strip HTML comments first
        clean = _HTML_COMMENT_RE.sub("", raw)
        spans = _inline_code_spans(clean)
        for m in _HTML_TAG_RE.finditer(clean):
            if _in_code_span(m.start(), spans):
                continue
            tag_name = m.group(2).lower()
            if tag_name in allowed:
                continue
            issues.append({
                "path": path, "line": i, "column": m.start() + 1,
                "message": f"Inline HTML element <{tag_name}> not allowed",
                "severity": severity, "check": "markdownlint.MD033",
            })
    return issues


def _md035(lines, cfg, suppressed, fence_set, path, severity):
    """MD035: Horizontal rule style consistency."""
    style_cfg = cfg.get("style", "consistent")
    hr_lines: List[Tuple[int, str]] = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            continue
        raw = line.rstrip("\n\r")
        m = _HORIZ_RULE_RE.match(raw)
        if m:
            hr_lines.append((i, raw.strip()))

    if not hr_lines:
        return []

    if style_cfg == "consistent":
        first_style = hr_lines[0][1]
        issues = []
        for line_no, hr in hr_lines[1:]:
            if hr != first_style and not _is_suppressed(suppressed, line_no, "MD035"):
                issues.append({
                    "path": path, "line": line_no, "column": 1,
                    "message": f"Horizontal rule style inconsistent; expected {first_style!r}",
                    "severity": severity, "check": "markdownlint.MD035",
                })
        return issues

    issues = []
    for line_no, hr in hr_lines:
        if hr != style_cfg and not _is_suppressed(suppressed, line_no, "MD035"):
            issues.append({
                "path": path, "line": line_no, "column": 1,
                "message": f"Horizontal rule style should be {style_cfg!r}",
                "severity": severity, "check": "markdownlint.MD035",
            })
    return issues


def _md036(lines, cfg, suppressed, fence_set, path, severity):
    """MD036: Emphasis used as heading (line is entirely emphasis)."""
    _RE = re.compile(r"^\s*(\*\*|__)[^*_\n]+(\*\*|__)\s*$|^\s*(\*|_)[^*_\n]+(\*|_)\s*$")
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set or _is_suppressed(suppressed, i, "MD036"):
            continue
        if _RE.match(line.rstrip("\n\r")):
            issues.append({
                "path": path, "line": i, "column": 1,
                "message": "Emphasis used instead of a heading",
                "severity": severity, "check": "markdownlint.MD036",
            })
    return issues


def _md043(lines, cfg, suppressed, fence_set, path, severity, context=None):
    """MD043: Required heading structure (no-op when headings=[] default)."""
    required = cfg.get("headings", [])
    if not required:
        return []
    match_case = cfg.get("match_case", False)

    headings_ctx = (context or {}).get("headings", [])
    if headings_ctx:
        actual = [h.get("text", "") for h in headings_ctx]
    else:
        actual = [text for _, _, text, _ in _heading_info(lines)]

    if not match_case:
        required = [r.lower() for r in required]
        actual = [a.lower() for a in actual]

    issues = []
    if actual != required:
        issues.append({
            "path": path, "line": 1, "column": 1,
            "message": "Heading structure does not match required structure",
            "severity": severity, "check": "markdownlint.MD043",
        })
    return issues


def _md044(lines, cfg, suppressed, fence_set, path, severity):
    """MD044: Proper names have incorrect capitalization (no-op when names=[])."""
    names = cfg.get("names", [])
    if not names:
        return []
    check_code = cfg.get("code_blocks", True)

    issues = []
    for name in names:
        pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
        for i, line in enumerate(lines, start=1):
            if not check_code and i in fence_set:
                continue
            if _is_suppressed(suppressed, i, "MD044"):
                continue
            raw = line.rstrip("\n\r")
            spans = _inline_code_spans(raw)
            for m in pattern.finditer(raw):
                if _in_code_span(m.start(), spans):
                    continue
                found = m.group(0)
                if found != name:
                    fix = raw[:m.start()] + name + raw[m.end():]
                    issues.append({
                        "path": path, "line": i, "column": m.start() + 1,
                        "message": f"Proper name {found!r} should be {name!r}",
                        "severity": severity, "check": "markdownlint.MD044",
                        "fix": fix,
                    })
    return issues


def _md047(lines, cfg, suppressed, fence_set, path, severity):
    """MD047: File should end with a single newline."""
    if not lines:
        return []
    last = lines[-1]
    if not last.endswith("\n"):
        line_no = len(lines)
        if not _is_suppressed(suppressed, line_no, "MD047"):
            return [{
                "path": path, "line": line_no, "column": len(last) + 1,
                "message": "File should end with a single newline",
                "severity": severity, "check": "markdownlint.MD047",
                "fix": last.rstrip("\n\r") + "\n",
            }]
    return []


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_RULE_SEVERITY_DEFAULT = "warning"

_RULE_FNS = {
    "MD001": _md001,
    "MD003": _md003,
    "MD004": _md004,
    "MD005": _md005,
    "MD007": _md007,
    "MD009": _md009,
    "MD010": _md010,
    "MD011": _md011,
    "MD012": _md012,
    "MD013": _md013,
    "MD014": _md014,
    "MD018": _md018,
    "MD019": _md019,
    "MD020": _md020,
    "MD021": _md021,
    "MD022": _md022,
    "MD023": _md023,
    "MD025": _md025,
    "MD026": _md026,
    "MD027": _md027,
    "MD028": _md028,
    "MD029": _md029,
    "MD030": _md030,
    "MD031": _md031,
    "MD032": _md032,
    "MD033": _md033,
    "MD034": _md034,
    "MD035": _md035,
    "MD036": _md036,
    "MD037": _md037,
    "MD038": _md038,
    "MD039": _md039,
    "MD040": _md040,
    "MD042": _md042,
    "MD044": _md044,
    "MD045": _md045,
    "MD046": _md046,
    "MD047": _md047,
    "MD048": _md048,
    "MD049": _md049,
    "MD050": _md050,
    "MD052": _md052,
    "MD053": _md053,
    "MD054": _md054,
    "MD055": _md055,
    "MD056": _md056,
    "MD058": _md058,
    "MD059": _md059,
    "MD060": _md060,
}

# Structural rules that need context passed in — handled separately in check()
_STRUCTURAL_RULE_FNS = {
    "MD024": _md024,
    "MD043": _md043,
    "MD051": _md051,
}


# ---------------------------------------------------------------------------
# SP20 — Structure extension rules
# ---------------------------------------------------------------------------

def _structure_stacked_headings(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """Structure.StackedHeadings: heading followed immediately by another heading (only blanks between)."""
    if cfg.get("allow_empty_sections", False):
        return []
    issues = []
    headings = _heading_info(lines)
    if len(headings) < 2:
        return []
    for idx in range(len(headings) - 1):
        curr_line = headings[idx][0]
        next_line = headings[idx + 1][0]
        # Check all lines between curr_line and next_line
        between = lines[curr_line:next_line - 1]  # 0-indexed: curr_line..next_line-2
        has_content = any(l.strip() for l in between)
        if not has_content and not _is_suppressed(suppressed, next_line, "Structure.StackedHeadings"):
            issues.append({
                "path": path, "line": next_line, "column": 1,
                "message": "Heading immediately follows another heading with no content between them (empty section)",
                "severity": severity, "check": "Structure.StackedHeadings",
            })
    return issues


def _structure_list_lead_colon(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """Structure.ListLeadColon: list block must be preceded by a sentence ending in a colon."""
    issues = []
    n = len(lines)
    in_list = False

    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            in_list = False
            continue
        is_item = bool(_LIST_ITEM_RE.match(line))
        if is_item and not in_list:
            in_list = True
            # Find the immediately preceding non-blank line
            prev_content_idx = i - 2  # 0-indexed, one line above current
            while prev_content_idx >= 0 and lines[prev_content_idx].strip() == "":
                prev_content_idx -= 1
            if prev_content_idx < 0:
                continue
            prev_line = lines[prev_content_idx].rstrip("\n\r").rstrip()
            # Skip: previous is a heading
            if _HEADING_ATX_RE.match(prev_line):
                continue
            # Skip: previous is a code fence line
            if _FENCE_START_RE.match(prev_line):
                continue
            # Skip: previous is also a list item (nested/continuation)
            if _LIST_ITEM_RE.match(prev_line):
                continue
            if not prev_line.endswith(":"):
                line_no = prev_content_idx + 1  # 1-indexed
                if not _is_suppressed(suppressed, i, "Structure.ListLeadColon"):
                    issues.append({
                        "path": path, "line": i, "column": 1,
                        "message": "List should be preceded by a sentence ending with a colon",
                        "severity": severity, "check": "Structure.ListLeadColon",
                    })
        elif not is_item:
            in_list = False
    return issues


def _structure_image_in_table(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """Structure.ImageInTable: images should not be embedded inside table cells."""
    issues = []
    for i, line in enumerate(lines, start=1):
        if i in fence_set:
            continue
        if not _TABLE_ROW_RE.match(line):
            continue
        if _TABLE_DELIM_RE.match(line):
            continue
        if _is_suppressed(suppressed, i, "Structure.ImageInTable"):
            continue
        if "![" in line:
            issues.append({
                "path": path, "line": i, "column": line.index("![") + 1,
                "message": "Images should not be embedded inside table cells",
                "severity": severity, "check": "Structure.ImageInTable",
            })
    return issues


def _structure_single_header_row(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """Structure.SingleHeaderRow: table must have exactly one GFM delimiter row."""
    issues = []
    # Walk lines, find table regions (consecutive lines with |)
    n = len(lines)
    i = 0
    while i < n:
        line_no = i + 1
        if line_no in fence_set or not _TABLE_ROW_RE.match(lines[i]):
            i += 1
            continue
        # Start of a table region
        table_start = line_no
        delim_lines: List[int] = []
        while i < n and _TABLE_ROW_RE.match(lines[i]) and line_no not in fence_set:
            line_no = i + 1
            if _TABLE_DELIM_RE.match(lines[i]):
                delim_lines.append(line_no)
            i += 1
        if len(delim_lines) > 1:
            for dl in delim_lines[1:]:
                if not _is_suppressed(suppressed, dl, "Structure.SingleHeaderRow"):
                    issues.append({
                        "path": path, "line": dl, "column": 1,
                        "message": "Table has more than one delimiter row; expected exactly one header separator",
                        "severity": severity, "check": "Structure.SingleHeaderRow",
                    })
    return issues


# ---------------------------------------------------------------------------
# SP5 — markdownlint-cli2 Python custom rule extension
# ---------------------------------------------------------------------------

_CLI2_COMMENT_RE = re.compile(r"^\s*//.*$", re.MULTILINE)
_JS_EXTENSIONS = frozenset({".js", ".cjs", ".mjs"})

_log = logging.getLogger(__name__)


def _load_cli2_config(explicit_path: str, search_dir: str) -> Dict[str, Any]:
    """Discover and parse .markdownlint-cli2.jsonc or .markdownlint-cli2.yaml."""
    candidates = [
        ".markdownlint-cli2.jsonc",
        ".markdownlint-cli2.yaml",
        ".markdownlint-cli2.yml",
    ]
    if explicit_path:
        paths_to_try = [Path(explicit_path)]
    else:
        start = Path(search_dir) if search_dir else Path(".")
        paths_to_try = []
        cur = start.resolve()
        for _ in range(12):
            for name in candidates:
                p = cur / name
                if p.exists():
                    paths_to_try.append(p)
                    break
            parent = cur.parent
            if parent == cur:
                break
            cur = parent
    if not paths_to_try:
        return {}

    path = paths_to_try[0]
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    try:
        name = path.name.lower()
        if name.endswith(".jsonc") or name.endswith(".json"):
            stripped = _CLI2_COMMENT_RE.sub("", raw)
            data = json.loads(stripped)
        else:
            data = yaml.safe_load(raw) or {}
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}
    return data


def _load_custom_rule(entry: Any, base_dir: str, rules: List[Dict[str, Any]]) -> None:
    """Load one customRules entry. .py → import as module. JS/npm → log and skip."""
    if not isinstance(entry, str):
        return
    suffix = Path(entry).suffix.lower()
    if suffix in _JS_EXTENSIONS or (not suffix and "/" not in entry and "\\" not in entry):
        _log.warning("JS custom rule %r skipped — only Python (.py) custom rules supported natively", entry)
        return
    if suffix != ".py":
        _log.warning("Custom rule %r skipped — only Python (.py) custom rules supported natively", entry)
        return

    rule_path = Path(entry) if Path(entry).is_absolute() else Path(base_dir) / entry
    if not rule_path.exists():
        _log.warning("Custom rule file not found: %s", rule_path)
        return

    spec = importlib.util.spec_from_file_location(f"_mdcustom_{rule_path.stem}", rule_path)
    if not spec or not spec.loader:
        return
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as exc:
        _log.warning("Failed to load custom rule %s: %s", rule_path, exc)
        return

    names = getattr(module, "NAMES", [rule_path.stem])
    check_fn = getattr(module, "check", None)
    if not callable(check_fn):
        _log.warning("Custom rule %s has no callable check()", rule_path)
        return

    for name in (names if names else [rule_path.stem]):
        rules.append({"name": name, "check": check_fn, "path": str(rule_path)})


def _run_custom_rule(crule: Dict[str, Any], lines: List[str], path: str,
                     issues: List[Dict[str, Any]]) -> None:
    """Execute one loaded Python custom rule via its check(context, on_error) interface."""
    name = crule.get("name", "custom")
    check_key = f"custom.{name}"
    fn: Callable = crule["check"]

    def on_error(line_no: int, detail: str = "", fix: Any = None) -> None:
        issue: Dict[str, Any] = {
            "path": path,
            "line": line_no,
            "column": 1,
            "message": detail or f"{name} violation",
            "severity": "suggestion",
            "check": check_key,
        }
        if fix is not None:
            issue["fix"] = fix
        issues.append(issue)

    ctx = {"lines": lines, "path": path}
    fn(ctx, on_error)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class MarkdownlintRunner(StyleRunner):
    """Native markdownlint rule runner (MD001/003/009/010/012/013/022/025/031/032/040/041)
    + markdownlint-cli2 Python custom rule extension (SP5)."""

    def __init__(self) -> None:
        self._config_path: str = ""
        self._custom_rules: List[Dict[str, Any]] = []  # SP5: loaded Python custom rules
        self._cli2_config: Dict[str, Any] = {}          # SP5: merged cli2 rule config

    def load(self, config_path: str = "", cli2_config_path: str = "",
             search_dir: str = "", **kwargs: Any) -> None:
        self._config_path = config_path or ""
        self._custom_rules = []
        self._cli2_config = {}
        # SP5: discover and load .markdownlint-cli2.* config — explicit path or explicit search_dir only
        search = search_dir or (os.path.dirname(config_path) if config_path else "")
        if not cli2_config_path and not search:
            return  # no auto-discovery without an explicit search root
        cli2_data = _load_cli2_config(cli2_config_path or "", search)
        if cli2_data:
            self._cli2_config = cli2_data.get("config", {})
            for entry in cli2_data.get("customRules", []):
                _load_custom_rule(entry, search, self._custom_rules)

    def check(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        path = context.get("path", "")
        text = context.get("text", "")
        genre = context.get("genre", "general")
        const = context.get("const")

        if not text:
            return []

        lines = text.splitlines(keepends=True)
        config = _load_config(self._config_path, path)
        # SP5: merge cli2 config overrides (cli2 takes precedence)
        if self._cli2_config:
            config = {**config, **self._cli2_config}
        fence_set = _code_fence_lines(lines)
        suppressed = _suppressed_lines(lines)

        def _severity(rule_id: str) -> str:
            rule_cfg_entry = config.get(rule_id)
            if isinstance(rule_cfg_entry, dict):
                return rule_cfg_entry.get("severity", _RULE_SEVERITY_DEFAULT)
            if const:
                return getattr(const, "RULE_SEVERITY_LEVELS", {}).get(
                    f"markdownlint.{rule_id}", _RULE_SEVERITY_DEFAULT
                )
            return _RULE_SEVERITY_DEFAULT

        issues: List[Dict[str, Any]] = []

        for rule_id, fn in _RULE_FNS.items():
            cfg = _rule_cfg(config, rule_id)
            if cfg is None:
                continue
            try:
                issues.extend(fn(lines, cfg, suppressed, fence_set, path, _severity(rule_id)))
            except Exception:
                pass

        # MD041 gets genre context
        cfg41 = _rule_cfg(config, "MD041")
        if cfg41 is not None:
            try:
                issues.extend(_md041(lines, cfg41, suppressed, fence_set, path, _severity("MD041"), genre))
            except Exception:
                pass

        # Structural rules that need the full context (AST headings etc.)
        for rule_id, fn in _STRUCTURAL_RULE_FNS.items():
            cfg = _rule_cfg(config, rule_id)
            if cfg is None:
                continue
            try:
                issues.extend(fn(lines, cfg, suppressed, fence_set, path, _severity(rule_id), context))
            except Exception:
                pass

        # SP20: Structure extension rules
        _structure_rules = [
            ("Structure.StackedHeadings", _structure_stacked_headings),
            ("Structure.ListLeadColon", _structure_list_lead_colon),
            ("Structure.ImageInTable", _structure_image_in_table),
            ("Structure.SingleHeaderRow", _structure_single_header_row),
        ]
        for rule_id, fn in _structure_rules:
            cfg_entry = config.get(rule_id)
            if isinstance(cfg_entry, dict) and cfg_entry.get("disabled"):
                continue
            if cfg_entry is False:
                continue
            sev = _severity(rule_id)
            rule_cfg_dict = cfg_entry if isinstance(cfg_entry, dict) else {}
            try:
                issues.extend(fn(lines, rule_cfg_dict, suppressed, fence_set, path, sev))
            except Exception:
                pass

        # SP5: run Python custom rules
        for crule in self._custom_rules:
            try:
                _run_custom_rule(crule, lines, path, issues)
            except Exception as exc:
                issues.append({
                    "path": path, "line": 1, "column": 1,
                    "message": f"Custom rule '{crule.get('name', '?')}' raised an exception: {exc}",
                    "severity": "suggestion",
                    "check": f"custom.{crule.get('name', 'unknown')}",
                })

        return issues
