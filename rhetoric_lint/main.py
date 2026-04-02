import fnmatch
import glob
import json
import os
from pathlib import Path
from typing import List, Optional

import typer

from rhetoric_lint.engine import RhetoricEngine
import rhetoric_lint.const as _const

app = typer.Typer(add_completion=False)


def _discover_files(inputs: List[str], ignore_patterns: List[str]) -> List[str]:
    files = set()
    if not inputs:
        inputs = ["."]

    for p in inputs:
        # glob pattern
        if any(ch in p for ch in "*?["):
            for f in glob.glob(p, recursive=True):
                if os.path.isfile(f) and f.lower().endswith(".md"):
                    files.add(os.path.normpath(f))
            continue

        path = Path(p)
        if path.is_dir():
            for f in path.rglob("*.md"):
                files.add(str(f))
        elif path.is_file():
            if path.suffix.lower() == ".md":
                files.add(str(path))
        else:
            # treat as possible glob
            for f in glob.glob(p, recursive=True):
                if os.path.isfile(f) and f.lower().endswith(".md"):
                    files.add(os.path.normpath(f))

    # apply ignore patterns
    if ignore_patterns:
        out = []
        for f in files:
            rel = os.path.relpath(f)
            if any(
                fnmatch.fnmatch(rel, pat)
                or fnmatch.fnmatch(f, pat)
                or fnmatch.fnmatch(Path(f).name, pat)
                for pat in ignore_patterns
            ):
                continue
            out.append(f)
        files = set(out)

    return sorted(files)


def _load_config(path: Optional[str]):
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        typer.echo(f"Config file not found: {path}", err=True)
        raise typer.Exit(2)

    if p.suffix.lower() in (".yml", ".yaml"):
        try:
            import yaml

            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except ImportError:
            typer.echo(
                "PyYAML is required to read YAML config files. Install with `pip install pyyaml`.",
                err=True,
            )
            raise typer.Exit(2)
    else:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            typer.echo(f"Failed to parse config file: {e}", err=True)
            raise typer.Exit(2)


SEVERITY_LEVEL = {"suggestion": 0, "warning": 1, "error": 2}


@app.command()
def lint(
    paths: List[Path] = typer.Argument(None),
    config: Optional[str] = typer.Option(
        None, "-c", "--config", help="Path to YAML/JSON config file"
    ),
    format: str = typer.Option("json", help="Output format: json|yaml|text|line"),
    rules: Optional[str] = typer.Option(
        None, help="Comma-separated list of rules to enable (run only these)"
    ),
    ignore_rules: Optional[str] = typer.Option(
        None, "--ignore-rules", help="Comma-separated list of rules to suppress"
    ),
    min_severity: str = typer.Option(
        "suggestion", help="Minimum severity to include: suggestion|warning|error"
    ),
    ignore: Optional[str] = typer.Option(
        None, help="Comma-separated ignore glob patterns for file paths"
    ),
    genre: Optional[str] = typer.Option(
        None,
        help="Override detected genre for all files: technical|scientific|academic|curriculum|legal|general",
    ),
):
    """Lint Markdown files for rhetorical quality.

    Exits 0 (clean), 1 (warnings/suggestions), or 2 (errors or CLI failure).

    Examples:
      rhetoric-lint docs/
      rhetoric-lint --format text --min-severity warning docs/api.md
      rhetoric-lint --rules Cohesion.Break,Heading.Generic docs/
      rhetoric-lint --ignore-rules Rhetoric.ThroatClearing docs/
      rhetoric-lint --genre curriculum docs/syllabus.md
    """

    ignore_patterns = [p.strip() for p in (ignore or "").split(",") if p.strip()]
    selected_rules = [r.strip() for r in (rules or "").split(",") if r.strip()]
    ignored_rules = [r.strip() for r in (ignore_rules or "").split(",") if r.strip()]

    cfg = _load_config(config)

    # apply config overrides to const module if keys match
    if cfg:
        try:
            import rhetoric_lint.const as const

            for k, v in cfg.items():
                if hasattr(const, k):
                    setattr(const, k, v)
        except Exception:
            pass

    files = _discover_files([str(p) for p in paths] if paths else [], ignore_patterns)

    engine = RhetoricEngine()
    raw_issues = engine.lint_files(files, genre_override=genre or None)

    # normalize issues
    matches = []
    for it in raw_issues:
        sev = str(it.get("severity", "suggestion")).lower()
        try:
            level = SEVERITY_LEVEL.get(sev, 0)
        except Exception:
            level = 0

        match = {
            "file": it.get("path") or it.get("file") or "",
            "line": int(it.get("line", 1) or 1),
            "column": int(it.get("column", 1) or 1),
            "rule": it.get("check") or it.get("rule") or "",
            "message": it.get("message", ""),
            "severity": sev,
            "_level": level,
        }
        matches.append(match)

    # filter by rules (allowlist)
    if selected_rules:
        matches = [
            m for m in matches
            if any(m["rule"] == r or m["rule"].startswith(r) for r in selected_rules)
        ]

    # filter by ignore-rules (denylist)
    if ignored_rules:
        matches = [
            m for m in matches
            if not any(m["rule"] == r or m["rule"].startswith(r) for r in ignored_rules)
        ]

    # filter by severity
    min_level = SEVERITY_LEVEL.get(min_severity.lower(), 0)
    matches = [m for m in matches if m["_level"] >= min_level]

    # prepare final output (remove internal keys)
    for m in matches:
        m.pop("_level", None)

    # determine exit code
    exit_code = 0
    if not matches:
        exit_code = 0
    else:
        max_level = max(
            SEVERITY_LEVEL.get(m.get("severity", "suggestion"), 0) for m in matches
        )
        if max_level >= 2:
            exit_code = 2
        else:
            exit_code = 1

    # output
    fmt = (format or "json").lower()
    if fmt == "json":
        # Vale-compatible JSON: aggregate violations under a top-level "Matches" array.
        vale_matches = []
        for m in matches:
            vale_matches.append(
                {
                    "Path": m.get("file", ""),
                    "Line": m.get("line", 1),
                    "Check": m.get("rule", ""),
                    "Message": m.get("message", ""),
                    "Severity": m.get("severity", "suggestion"),
                }
            )
        out: dict = {"Genre": engine.last_genres, "Matches": vale_matches}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif fmt == "yaml":
        try:
            import yaml

            print(yaml.safe_dump({"matches": matches}, sort_keys=False))
        except ImportError:
            typer.echo(
                "PyYAML is required for YAML output. Install with `pip install pyyaml`.",
                err=True,
            )
            raise typer.Exit(2)
    elif fmt == "text":
        for m in matches:
            print(
                f"{m['file']}:{m['line']}:{m['column']}: [{m['severity'].upper()}] {m['rule']} — {m['message']}"
            )
    elif fmt == "line":
        for m in matches:
            print(json.dumps(m, ensure_ascii=False))
    else:
        typer.echo(f"Unknown format: {format}", err=True)
        raise typer.Exit(2)

    raise typer.Exit(code=exit_code)


@app.command(name="rules")
def list_rules(
    severity: Optional[str] = typer.Option(
        None, help="Filter by severity: suggestion|warning|error"
    ),
    format: str = typer.Option("text", help="Output format: text|json"),
):
    """List all available rules with their severity and description."""
    severity_order = {"suggestion": 0, "warning": 1, "error": 2}
    rows = []
    for check, sev in sorted(_const.RULE_SEVERITY_LEVELS.items()):
        if severity and sev != severity.lower():
            continue
        description = _const.RULE_DESCRIPTIONS.get(check, "")
        rows.append({"check": check, "severity": sev, "description": description})

    rows.sort(key=lambda r: (-severity_order.get(r["severity"], 0), r["check"]))

    fmt = (format or "text").lower()
    if fmt == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        col = max((len(r["check"]) for r in rows), default=0)
        sev_col = len("suggestion")
        for r in rows:
            print(f"{r['check']:<{col}}  {r['severity']:<{sev_col}}  {r['description']}")


if __name__ == "__main__":
    app()
