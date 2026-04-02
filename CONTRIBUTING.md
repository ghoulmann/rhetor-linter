# Contributing to rhetoric-lint

## Development setup

```bash
# Standard virtualenv
make virtualenv          # creates .venv, installs deps, downloads spaCy model
source .venv/bin/activate

# Or with Pipenv
make pipenv
pipenv shell
```

## Running tests

```bash
make test          # run pytest
make test-cov      # run pytest with coverage report
make lint-self     # run rhetoric-lint on its own docs
make clean         # remove __pycache__, .pytest_cache, .coverage
```

## Architecture constraints

These are non-obvious design decisions. Read before contributing.

### mistletoe is a hard requirement

The engine raises `RuntimeError` if mistletoe is absent or returns no sections. There is no fallback parser. Do not add one.

### overlap.py is the only place for overlap math

Rules call `channelize_tokens`, `set_overlap_metrics`, etc. from `overlap.py`. No rule should re-implement Jaccard or containment.

### const.py is the only place for thresholds

No magic numbers in rule modules. Config files override `const` attributes at runtime before linting.

### Stem bridging belongs in each rule (Layer B), not in overlap.py (Layer A)

A post-channelization stem fallback applied globally in `overlap.py` would degrade precision for well-calibrated rules. Apply it only inside the specific rule's emission site, and only when direct lemma overlap is already zero.

### Genre classification is gated

`GENRE_GATE_ENABLED = False` until per-genre F1 >= 0.78 on the validation corpus. Do not enable it or write rules that depend on it.

Recognised genres: `technical`, `scientific`, `academic`, `curriculum`, `legal`, `adr`, `postmortem`, `general`. ADR and Postmortem rules self-qualify using heading constellations and regex rather than relying on the gate.

To contribute labeled documents or run the accuracy evaluation, see the
[Genre Labeling Guide](tests/fixtures/corpus/LABELING_GUIDE.md).

### Rule exceptions are swallowed

A crashing rule emits nothing; other rules continue. This is intentional — one broken rule should never block the rest of the linter.

## Adding a rule

1. Create `rhetoric_lint/rules/mycheck.py` with a `check(context) -> list[Issue]` function.
2. Add the module name to the load list in `RhetoricEngine.__init__` (`rhetoric_lint/engine.py`).
3. Add a severity entry to `RULE_SEVERITY_LEVELS` in `rhetoric_lint/const.py`.
4. Add a description to `RULE_DESCRIPTIONS` in `rhetoric_lint/const.py`.
5. Add the rule to the rules table in `README.md`.
6. Add tests.

Issue dicts need at minimum: `path`, `line`, `column`, `message`, `severity`, `check`.

The `context` dict passed to each rule contains:

| Key | Type | Description |
|-----|------|-------------|
| `path` | `str` | File path being linted |
| `text` | `str` | Raw Markdown source |
| `doc` | `spacy.tokens.Doc` | Full-document spaCy Doc (may be truncated for large files; see `NLP_MAX_CHARS`) |
| `nlp` | `spacy.Language` | Loaded spaCy model |
| `const` | `module` | The `rhetoric_lint.const` module (for threshold access) |
| `sections` | `list[dict]` | AST-parsed section hierarchy from mistletoe |
| `headings` | `list[dict]` | Flat list of all heading nodes extracted from the AST |
| `genre` | `str` | Detected (or overridden) document genre: `technical`, `adr`, `postmortem`, etc. |
| `doc_template` | `str` | Detected document template (technical sub-genre): `quick_start`, `architecture`, etc.; `general` if none matched |

Each section dict in `sections` includes a `topic_type` field populated by `topic_type.py` before rules run. Values: `concept`, `howto`, `reference`, `faq`, `tutorial`, `explanation`, `troubleshooting`, `general`.

## Stem bridge reference (Layer B)

spaCy lemmatization divergence for morphologically related words is handled by a two-level stem fallback applied at each rule's emission site (Layer B only — not in `overlap.py`):

| Layer | Slice | Handles |
|-------|-------|---------|
| 6-char | `l[:6]` for `len(l) >= 5` | `requirement`/`require` -> `requir`; `instal`/`install` -> `instal` |
| 5-char | `l[:5]` for `len(l) >= 5` | `mkdocs`/`mkdoc` OOV inconsistency -> `mkdoc` |

Applied in: `headings.py` (NearDuplicate/InformationScent), `unity.py` (HeadingTopicCoherence), `cohesion.py` (Break — 6-char then 5-char secondary).

Both bridges apply only when direct lemma overlap is already zero.

Regression tests:

- `tests/test_unity.py::test_unity_no_false_positive_stem_bridge`
- `tests/test_cohesion.py::test_no_cohesion_break_stem_bridge`
- `tests/test_cohesion.py::test_no_cohesion_break_5char_stem_bridge`

## Test coverage gaps

The following rules lack dedicated unit tests and are good targets for contribution:

- `Heading.NearDuplicate`
- `Rhetoric.ComplexitySpike`
- `Rhetoric.ThroatClearing`
- `Attention.SplitAttention`
- `Cohesion.DeicticGhost`
- `Resilience.ErrorPathPresence`
- `Navigation.FindabilityMap`
- `Structure.WallOfText`
- `Structure.ActionableHeadings`
- `Curriculum.MissingAssessment`

Some of these are exercised indirectly by integration tests in `tests/test_rules_examples.py`, but dedicated tests with edge cases would strengthen the suite.

Rules with dedicated test files: ADR (`tests/test_adr.py`), Postmortem (`tests/test_postmortem.py`), topic types (`tests/test_topic_types.py`), doc templates (`tests/test_doc_templates.py`).

## Code style

- Type hints on all public functions. Use `from __future__ import annotations` for modern syntax.
- No `TODO`/`FIXME` comments — file an issue instead.
- Keep rule modules focused: one `check()` function with helpers as needed.
