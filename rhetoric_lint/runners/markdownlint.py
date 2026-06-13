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
    "MD010": {"code_blocks": True, "spaces_per_tab": 4},
    "MD012": {"maximum": 1},
    "MD013": {"line_length": 80, "code_blocks": True, "tables": True},
    "MD022": {"lines_above": 1, "lines_below": 1},
    "MD031": {"list_items": False},
    "MD032": {},
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
    """Return per-rule config dict, or None if disabled (entry=False or disabled:true)."""
    entry = config.get(rule_id)
    if entry is None:
        return _DEFAULTS.get(rule_id, {})
    if entry is False:
        return None
    if isinstance(entry, dict) and entry.get("disabled"):
        return None
    merged = dict(_DEFAULTS.get(rule_id, {}))
    if isinstance(entry, dict):
        merged.update(entry)
    return merged


# ---------------------------------------------------------------------------
# Pre-scan helpers
# ---------------------------------------------------------------------------

def _code_fence_lines(lines: List[str]) -> Set[int]:
    """1-indexed set of line numbers inside fenced code blocks (including fence lines)."""
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


def _md046(
    lines: List[str],
    cfg: Dict[str, Any],
    suppressed: Dict[int, Set[str]],
    fence_set: Set[int],
    path: str,
    severity: str,
) -> List[Dict[str, Any]]:
    """MD046: Code block style — backtick vs tilde consistency."""
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
            if _is_suppressed(suppressed, line_no, "MD046"):
                continue
            raw = lines[line_no - 1].rstrip("\n\r")
            fence_match = _FENCE_START_RE.match(raw)
            if fence_match:
                fix = majority_char * len(fence_match.group(1)) + raw[fence_match.end():]
            else:
                fix = None
            issue: Dict[str, Any] = {
                "path": path, "line": line_no, "column": 1,
                "message": "Code block style should be consistent; use the majority style",
                "severity": severity, "check": "markdownlint.MD046",
            }
            if fix is not None:
                issue["fix"] = fix
            issues.append(issue)
    elif style_cfg == "fenced":
        for line_no in tilde_lines:
            if _is_suppressed(suppressed, line_no, "MD046"):
                continue
            raw = lines[line_no - 1].rstrip("\n\r")
            fence_match = _FENCE_START_RE.match(raw)
            fix = "`" * len(fence_match.group(1)) + raw[fence_match.end():] if fence_match else None
            issue = {
                "path": path, "line": line_no, "column": 1,
                "message": "Code block style should use backticks (fenced)",
                "severity": severity, "check": "markdownlint.MD046",
            }
            if fix is not None:
                issue["fix"] = fix
            issues.append(issue)
    elif style_cfg == "tilde":
        for line_no in backtick_lines:
            if _is_suppressed(suppressed, line_no, "MD046"):
                continue
            raw = lines[line_no - 1].rstrip("\n\r")
            fence_match = _FENCE_START_RE.match(raw)
            fix = "~" * len(fence_match.group(1)) + raw[fence_match.end():] if fence_match else None
            issue = {
                "path": path, "line": line_no, "column": 1,
                "message": "Code block style should use tildes",
                "severity": severity, "check": "markdownlint.MD046",
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
# Runner
# ---------------------------------------------------------------------------

_RULE_SEVERITY_DEFAULT = "warning"

_RULE_FNS = {
    "MD001": _md001,
    "MD003": _md003,
    "MD009": _md009,
    "MD010": _md010,
    "MD012": _md012,
    "MD013": _md013,
    "MD022": _md022,
    "MD025": _md025,
    "MD031": _md031,
    "MD032": _md032,
    "MD040": _md040,
    "MD045": _md045,
    "MD046": _md046,
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
