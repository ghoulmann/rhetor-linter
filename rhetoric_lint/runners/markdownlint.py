"""SP3: Native markdownlint rules — MD001/003/009/010/012/013/022/025/031/032/040/041."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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
    """Return per-rule config dict, or None if disabled."""
    entry = config.get(rule_id)
    if entry is None:
        return _DEFAULTS.get(rule_id, {})
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
}


class MarkdownlintRunner(StyleRunner):
    """Native markdownlint rule runner (MD001/003/009/010/012/013/022/025/031/032/040/041)."""

    def __init__(self) -> None:
        self._config_path: str = ""

    def load(self, config_path: str = "", **kwargs: Any) -> None:
        self._config_path = config_path or ""

    def check(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        path = context.get("path", "")
        text = context.get("text", "")
        genre = context.get("genre", "general")
        const = context.get("const")

        if not text:
            return []

        lines = text.splitlines(keepends=True)
        config = _load_config(self._config_path, path)
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

        return issues
