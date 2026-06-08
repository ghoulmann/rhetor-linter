"""Apply deterministic in-place fixes to Markdown files.

fix dict keys (all optional except edit_column for non-delete operations):
  type:         "replace" | "remove" | "insert"
  edit_column:  1-based column of the match start
  delete_count: number of characters to delete (0 for pure insert)
  insert_text:  text to insert at edit_column after deletion (""  for pure delete)
"""
from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path


def apply_fixes(path: str, findings: list[dict]) -> int:
    """Apply all fixable findings in *findings* to *path* in-place.

    Returns the number of fixes applied.  Findings without a 'fix' key are
    silently skipped.  Fixes on the same line are applied rightmost-column-first
    so earlier column offsets remain valid.
    """
    fixable = [f for f in findings if "fix" in f and f["fix"]]
    if not fixable:
        return 0

    p = Path(path)
    try:
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as e:
        raise OSError(f"Cannot read {path}: {e}") from e

    # Check write permission before doing any work
    if not os.access(path, os.W_OK):
        raise PermissionError(f"No write permission: {path}")

    # Group by line number (1-based)
    by_line: dict[int, list[dict]] = defaultdict(list)
    for f in fixable:
        line_no = int(f.get("line", 1) or 1)
        by_line[line_no].append(f["fix"])

    applied = 0
    for line_no, fixes in by_line.items():
        if line_no < 1 or line_no > len(lines):
            continue
        idx = line_no - 1
        line_text = lines[idx]
        # Apply fixes rightmost-column-first to preserve offsets
        sorted_fixes = sorted(fixes, key=lambda fx: fx.get("edit_column", 1), reverse=True)
        for fix in sorted_fixes:
            new_line, ok = _apply_line_fix(line_text, fix)
            if ok:
                line_text = new_line
                applied += 1
        lines[idx] = line_text

    try:
        p.write_text("".join(lines), encoding="utf-8")
    except OSError as e:
        raise OSError(f"Cannot write {path}: {e}") from e

    return applied


def _apply_line_fix(line_text: str, fix: dict) -> tuple[str, bool]:
    """Apply a single fix dict to *line_text*.

    Returns (new_line_text, success).  On malformed input returns (line_text, False).
    """
    col = fix.get("edit_column")
    delete_count = fix.get("delete_count", 0)
    insert_text = fix.get("insert_text", "")

    if col is None:
        return line_text, False

    col = int(col)
    delete_count = int(delete_count)

    # col is 1-based; convert to 0-based index
    idx = col - 1
    if idx < 0 or idx > len(line_text):
        return line_text, False

    new_text = line_text[:idx] + (insert_text or "") + line_text[idx + delete_count:]
    return new_text, True
