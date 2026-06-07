# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Environment (use one)
make virtualenv && source .venv/bin/activate
make pipenv && pipenv shell

# Tests
make test                                # full suite via pytest
make test-cov                            # with coverage report
pipenv run python -m pytest tests/test_adr.py -q   # single test file
pipenv run python -m pytest -k "test_unity" -q     # by name pattern

# Lint / explore
make lint-self                           # run rhetoric-lint on docs/ + README.md
rhetoric-lint rules                      # list all rules with severity
rhetoric-lint --format text --min-severity warning docs/api.md
rhetoric-lint --style-dir style-sets/ --style Rhetoric docs/api.md   # include Vale YAML rules
```

Tests require the package to be importable. Run via `pipenv run python -m pytest` or activate the venv first; bare `python -m pytest` will fail if the env is not active.

## CHANGELOG

**Update `CHANGELOG.md` whenever work is committed.** Add entries under `## [Unreleased]` in the appropriate section (`Added`, `Changed`, `Fixed`, `Removed`). One bullet per logical change — rule additions, runner features, bug fixes, doc promotions. Do not add entries for test-only changes or internal refactors with no user-visible effect. When a version is released, the `[Unreleased]` section becomes the release entry with its date.

spaCy model must be present: `python -m spacy download en_core_web_sm`. If absent, the engine falls back to a blank model (no POS tagging, reduced accuracy).

## Architecture

The linter is a single-process Python package (`rhetoric_lint/`). The main pipeline:

1. **`main.py`** — Typer CLI. Discovers files, loads config (merges `.rhetoric-lint.yaml` keys into `const`), initialises runners, calls `RhetoricEngine`. Flags: `--style-dir`, `--style`, `--no-vale`, `--no-markdownlint`, `--fix`.
2. **`engine.py`** — `RhetoricEngine`. Preprocesses text (strips YAML frontmatter, link-ref definitions, HTML comments/tags; rewrites MyST/MkDocs/pymdownx admonitions and GFM alerts to blockquotes; rewrites content-tab `===` blocks), parses with mistletoe, runs spaCy on each paragraph, classifies the document, dispatches all rule modules, then dispatches runners.
3. **`genre.py` / `topic_type.py` / `template_type.py`** — Three-dimensional classification runs before rules. Genre is document-level; topic type is per-section; doc template is a technical sub-genre. Results are in `context["genre"]`, `section["topic_type"]`, and `context["doc_template"]`. Genres: `howto`, `tutorial`, `concept`, `explanation`, `reference`, `adr`, `postmortem`, `changelog`, `readme`, `general`. Filename-based detection (README, CHANGELOG, CONTRIBUTING) takes priority over structural inference.
4. **`rules/*.py`** — ~28 modules, each exporting `check(context) -> list[dict]`. Exceptions are silently swallowed so one broken rule never blocks the rest.
5. **`runners/`** — External style runners (loaded after Python rules). `base.py`: `StyleRunner` ABC. `vale_style.py`: `ValeStyleRunner` — all 10 Vale rule types, genre gating, vocab suppression. `markdownlint.py`: `MarkdownlintRunner` — 12 MD rules + CLI2 Python custom rule loader. `_readability.py`: shared readability preprocessing + Lexi composite score (textstat, soft dependency).
6. **`fix.py`** — `apply_fixes(path, findings)`: groups fixable findings by file and line, applies `fix` dicts rightmost-column-first. Called by `--fix` flag.
7. **`overlap.py`** — All Jaccard/containment/givenness math lives here. Rules call `channelize_tokens`, `set_overlap_metrics`, `channel_overlap_metrics`, `section_coherence_metrics`. Never reimplement overlap logic in a rule.
8. **`const.py`** — All thresholds and word lists. Config file keys override `const` attributes at runtime. No magic numbers in rule modules.

### `context` dict passed to every rule

| Key | Contents |
|-----|----------|
| `path` | file path |
| `text` | preprocessed Markdown source |
| `doc` | full-document `spacy.Doc` (may be truncated at `NLP_MAX_CHARS`) |
| `nlp` | spaCy model instance |
| `const` | `rhetoric_lint.const` module |
| `sections` | mistletoe AST section hierarchy (see below) |
| `headings` | flat list of all heading nodes |
| `genre` | document genre string |
| `doc_template` | technical sub-genre string or `"general"` |
| `frontmatter` | parsed YAML frontmatter dict (empty if absent or PyYAML unavailable) |
| `section_annotations` | dict keyed by 1-based heading line → annotation dict (from `<!--\n---\nyaml\n---\n-->` blocks) |

Each section has: `level`, `heading`, `start`, `end`, `topic_type`, `paragraphs`, and optionally `annotation` (dict from a preceding annotation block). Each paragraph has: `text`, `pos`, `line`, `doc` (spaCy Doc), `sentences` (list of `{span, start, end, line}`), and `nodes` (list of AST node metadata with `type`, `text`, `language`, `list_type`).

### F5 — DIMENSION_MAP

`const.DIMENSION_MAP` maps the five scoring dimensions to their rule-check prefixes:

| Dimension | Prefixes |
|-----------|----------|
| `Clarity` | `Rhetoric.*`, `Attention.*`, `Cohesion.*`, `Coherence.*` |
| `Structure` | `Heading.*`, `Symmetry.*`, `Structure.*`, `Navigation.*` |
| `Completeness` | `Completeness.*`, `Resilience.*`, `Curriculum.*` |
| `Style` | `Unity.*`, `Lexical.*`, `Terminology.*`, Vale YAML rules |
| `Readability` | `Rhetoric.ReadabilityGrade`, `Clarity.FleschReadingEase` |

Rules not matched by any prefix fall under `const.DIMENSION_DEFAULT` (`"Style"`).

### Hard constraints (from CONTRIBUTING.md)

- **mistletoe is required** — the engine raises `RuntimeError` without it; no fallback parser.
- **overlap.py is the only place for overlap math** — no Jaccard re-implementations in rules.
- **const.py is the only place for thresholds** — no inline numbers in rule files.
- **Stem bridging is Layer B** — apply the 6-char / 5-char stem fallback only at the rule's emission site, never inside `overlap.py`. See CONTRIBUTING.md § "Stem bridge reference" for the exact pattern.
- **`GENRE_GATE_ENABLED = False`** — do not enable or write rules that depend on it; ADR/Postmortem rules self-qualify via heading constellations instead.
- **Rule exceptions are swallowed** — intentional; do not add top-level try/except bypasses.

## Adding a rule

1. Create `rhetoric_lint/rules/mycheck.py` with `check(context) -> list[dict]`.
2. Add module name to the load list in `RhetoricEngine.__init__` (`engine.py`).
3. Add severity entry to `RULE_SEVERITY_LEVELS` in `const.py`.
4. Add description to `RULE_DESCRIPTIONS` in `const.py`.
5. Add the rule to the rules table in `README.md`.
6. Add tests — including at least one "must not fire" fixture against `tests/fixtures/corpus/technical/`.

Issue dict minimum keys: `path`, `line`, `column`, `message`, `severity`, `check`.

## Tests

Test files map roughly to rule categories: `test_adr.py`, `test_postmortem.py`, `test_topic_types.py`, `test_doc_templates.py`, `test_cohesion.py`, `test_unity.py`, `test_symmetry.py`, `test_terminology.py`, `test_rhetoric_new_rules.py`.

`tests/test_rules_examples.py` is an integration test that runs the full engine against fixture files.

`tests/fixtures/corpus/technical/` contains real-world docs seeded as a precision corpus — new rules must produce zero findings against these files before merging.

Rules with **no dedicated test file yet** (good contribution targets): `Heading.NearDuplicate`, `Rhetoric.ComplexitySpike`, `Rhetoric.ThroatClearing`, `Attention.SplitAttention`, `Cohesion.DeicticGhost`, `Resilience.ErrorPathPresence`, `Navigation.FindabilityMap`, `Structure.WallOfText`, `Structure.ActionableHeadings`, `Curriculum.MissingAssessment`.

## Adding a Vale-style YAML rule

1. Create a YAML file in `style-sets/<StyleName>/` following Vale's rule format.
2. Supported `extends:` values: `existence`, `substitution`, `occurrence`, `metric`, `capitalization`, `repetition`, `consistency`, `conditional`, `readability`, `sequence`, `spelling`.
3. Load at runtime: `rhetoric-lint --style-dir style-sets/ --style <StyleName> docs/`.
4. Check name is `"{StyleName}.{yaml_stem}"`.
5. Genre-gate: add `genre: howto, tutorial` to the rule YAML, or `meta.yml` with `genre:` for the whole style.
6. Swap keys in `substitution` rules are treated as **raw regex patterns** (not escaped) — use `fire(?:m[ae]n|wom[ae]n)` syntax as in Vale. Word boundaries are added automatically unless `nonword: true`. Substitution findings carry a `fix` payload — `--fix` applies them in-place.
7. **Spelling rules** (`extends: spelling`) require `spylls` (`pip install 'rhetoric-lint[spell]'`). Bundled dictionaries: `en_US`, `sv_SE`, `ru`. The shipped `Spelling` style uses `en_US` with `vocab/aws.txt` and `vocab/tech.txt`.
   - **To add terms**: append one word per line to `style-sets/Spelling/vocab/tech.txt` (general tech) or `vocab/aws.txt` (AWS). Words are matched case-insensitively.
   - **To use a custom wordlist**: add a `vocab/myterms.txt` file in your style dir and reference it under `ignore:` in the spelling YAML.
   - **`action: {name: suggest}`**: populates `issue["suggestions"]` (up to 3) but does not auto-fix — spelling corrections require human review.

### `extends: readability` and the Lexi metric

The built-in metric name `Lexi` invokes the composite readability score from `rhetoric_lint/runners/_readability.py`. Formula, weights, and normalization match [Rebilly/lexi](https://github.com/Rebilly/lexi) exactly:
- Five textstat metrics weighted: Flesch Reading Ease (16.5%), Gunning Fog (22.3%), ARI (23.3%), Dale-Chall (19.6%), Coleman-Liau (18.3%)
- "Lower is better" metrics use inverted range convention (`min` = worst, `max` = best end)
- Score is 0–100 (100 = most readable)

```yaml
# style-sets/Rhetoric/ReadabilityGrade.yml
extends: readability
metric: Lexi
max: 65        # flag paragraphs scoring below 65
level: warning
scope: paragraph
```

### style-sets/ layout

`style-sets/` is the canonical directory for all Vale-compatible style sets. Only project-owned sets are tracked in git; user/third-party sets installed alongside them are gitignored via `style-sets/*` + `!style-sets/<Name>` negation rules in `.gitignore`. Currently tracked: `Rhetoric/`, `Clarity/`, `Spelling/`.

## Active development

Single source of truth: `.claude/plans/plan-support-for-markdownlint-joyful-teacup.md` (all addendums integrated).

Enterprise platform design (scoring, server, Backstage, JTBD integration): `.claude/plans/plan-enterprise-platform.md`.

Status as of 2026-06-07:

| SP | Status | Description |
|----|--------|-------------|
| SP1 | ✅ done | Runner infrastructure + fix framework + CrossFileContext stub |
| SP2 | ✅ done | Vale existence + substitution |
| SP3 | ✅ done | markdownlint 12 native MD rules |
| SP4 | ✅ done | Vale extended types (8 types) + `_readability.py` |
| SP5 | ✅ done | markdownlint-cli2 Python custom rule extension |
| SP6 | ✅ done | TrivializingLanguage migrated to Vale YAML (`style-sets/Rhetoric/`) |
| SP7 | ✅ done | Rhetoric YAML additions: Terminology, Inclusivity, InclusivityFlag |
| SP8 | ✅ done | 6 NLP rules: SyntacticDepth, Nominalization, MetricDensity, ToneImbalance, PreferredForm, TabVariantBalance |
| SP9 | ✅ done | ProsePartner gaps: PassiveVoiceActorGap, SentenceRhythm, UnsupportedClaim (Python/spaCy) + ReadabilityGrade.yml (Vale YAML, `extends: readability`, `metric: Lexi`) |
| SP_CONTRAST | ✅ done | Rhetoric.UnresolvedContrast (implemented in rhetoric.py, tested) |
| F1 | ✅ done | Section annotation pre-pass: `<!--\n---\nyaml\n---\n-->` blocks before headings → `section_annotations` + `sec["annotation"]`; `topic_type` overrides classifier |
| F2 | ✅ done | Frontmatter parsing into `context["frontmatter"]` before blanking; alias normalisation via `const.FRONTMATTER_ALIASES` |
| F5 | ✅ done | `const.DIMENSION_MAP` — 5 scoring dimensions mapped to rule-check prefixes |
| SP_SPELL | ✅ done | `extends: spelling` via spylls; optional dep `[spell]`; `style-sets/Spelling/` with en_US + AWS/tech vocab |
| SP10/SP11 | backlog | DependencyReveal + ConceptReintroductionPenalty (blocked on CrossFileContext) |

**False positive standard**: every new rule requires a "must not fire" fixture. All new rules must produce zero findings against `tests/fixtures/corpus/technical/` before merging.
