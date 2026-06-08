# CI Integration

rhetoric-lint can run in two CI modes: as a pre-commit hook (runs locally before every commit) and as a GitHub Actions workflow (runs on pull requests).

## Pre-commit hook

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/yourusername/rhetor-linter
    rev: v0.1.0          # pin to a release tag
    hooks:
      - id: rhetoric-lint
```

By default this fails on `warning`-severity findings and above. To fail only on errors (missing H1, missing result verification), use the stricter hook ID:

```yaml
      - id: rhetoric-lint-error
```

Install hooks into your repo once:

```bash
pip install pre-commit
pre-commit install
```

## GitHub Actions

Copy `.github/workflows/rhetoric-lint.yml` from this repo, or add the steps below to an existing workflow:

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"

- name: Install rhetoric-lint
  run: pip install rhetoric-lint

- name: Download spaCy model
  run: python -m spacy download en_core_web_sm

- name: Run rhetoric-lint
  run: rhetoric-lint lint --format text --min-severity warning docs/ README.md
```

The spaCy download step is required. Without it the engine falls back to a blank model with no POS tagging, which reduces rule accuracy.

## Severity knob

| Flag | Fails on |
|------|----------|
| `--min-severity suggestion` | any finding |
| `--min-severity warning` | warnings and errors (default) |
| `--min-severity error` | errors only |

Error-severity rules today: `Completeness.ResultVerification`, `Heading.MissingH1`.

## Scoping which files are checked

Pass one or more paths as arguments:

```bash
rhetoric-lint lint --min-severity warning docs/ README.md CONTRIBUTING.md
```

Glob patterns are not expanded by the CLI — pass directory paths and let the engine recurse, or use shell expansion: `rhetoric-lint lint $(find docs -name '*.md')`.

## Scoring (informational, no exit code)

```bash
rhetoric-lint score docs/
```

Outputs JSON with per-file dimension scores (Clarity, Structure, Completeness, Style, Readability) and per-1000-word densities. Always exits 0. Useful for dashboards and trend tracking without blocking CI.
