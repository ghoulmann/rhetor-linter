# rhetoric-lint

A Markdown linter for rhetorical and structural quality. Checks cohesion, unity, completeness, symmetry, attention, headings, and rhetoric using spaCy NLP and a mistletoe AST parser. Includes Vale-compatible and markdownlint-compatible style runners.

## Installation

```bash
# Standard virtualenv
make virtualenv          # creates .venv, installs deps, downloads spaCy model
source .venv/bin/activate

# Or with Pipenv
make pipenv              # creates pipenv environment from Pipfile
pipenv shell
```

Manual install:

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
pip install pyyaml       # optional: needed for YAML config/output
```

## Usage

```bash
rhetoric-lint docs/
rhetoric-lint --format text --min-severity warning docs/api.md
rhetoric-lint --rules Cohesion.Break,Heading.Generic docs/
rhetoric-lint --ignore-rules Rhetoric.ThroatClearing docs/
rhetoric-lint --genre curriculum docs/syllabus.md
rhetoric-lint --config .rhetoric-lint.yaml docs/
rhetoric-lint --style-dir style-sets/ --style Rhetoric docs/
```

List all available rules:

```bash
rhetoric-lint rules
rhetoric-lint rules --severity warning
rhetoric-lint rules --format json
```

## CLI reference

| Flag | Default | Description |
|------|---------|-------------|
| `--format` | `json` | Output format: `json`, `yaml`, `text`, `line` |
| `--min-severity` | `suggestion` | Minimum severity to emit: `suggestion`, `warning`, `error` |
| `--rules` | — | Comma-separated allowlist of rules to run |
| `--ignore-rules` | — | Comma-separated denylist of rules to suppress |
| `--ignore` | — | Comma-separated glob patterns to exclude files |
| `--config`, `-c` | — | YAML or JSON config file; keys matching `const.py` override defaults |
| `--genre` | — | Override genre detection: `technical`, `scientific`, `academic`, `curriculum`, `legal`, `adr`, `postmortem`, `general` |
| `--style-dir` | — | Parent directory of Vale-compatible style sets (repeatable) |
| `--style` | — | Comma-separated style names to enable (empty = all in `--style-dir`) |
| `--no-vale` | false | Disable Vale-compatible style runners |
| `--no-markdownlint` | false | Disable markdownlint runner |
| `--fix` | false | Apply all deterministic fixes in-place |

Both `--rules` and `--ignore-rules` support prefix matching: `--rules Cohesion` matches all `Cohesion.*` checks.

## Output formats

**JSON** (default) — Vale-compatible:

```json
{
  "Genre": { "file.md": "technical" },
  "Matches": [
    { "Path": "...", "Line": 1, "Check": "...", "Message": "...", "Severity": "warning" }
  ]
}
```

**Text**: `file.md:LINE:COL: [SEVERITY] RULE — message`

**Line**: one JSON object per line (for log pipelines).

**YAML**: requires `pyyaml`.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | No violations |
| `1` | Warnings or suggestions only |
| `2` | At least one `error`, or CLI/config failure |

## Style runners

### Vale-compatible rules (`--style-dir`)

Any directory of Vale-format `.yml` rule files can be loaded. Supported rule types: `existence`, `substitution`, `occurrence`, `metric`, `capitalization`, `repetition`, `consistency`, `conditional`, `readability`, `sequence`.

Two style sets ship in `style-sets/`:

**`Rhetoric`** — rhetorical quality checks:

| Style rule | Type | Description |
|-----------|------|-------------|
| `Rhetoric.TrivializingLanguage` | existence | Flags trivializing adverbs (`simply`, `easily`, `basically`, `merely`, etc.) |
| `Rhetoric.TrivializingLanguage-just` | existence | Flags `just` with temporal-use exceptions |
| `Rhetoric.Terminology` | substitution | Inclusive terminology replacements (`whitelist`→`allowlist`, gendered roles, etc.) |
| `Rhetoric.Inclusivity` | existence | Flags terms with more inclusive alternatives |
| `Rhetoric.InclusivityFlag` | existence | Flags terms without clean drop-in replacements |

**`Clarity`** — readability structure checks:

| Style rule | Type | Description |
|-----------|------|-------------|
| `Clarity.FleschReadingEase` | readability | Flags paragraphs below the Flesch Reading Ease threshold |
| `Clarity.Nominalizations` | occurrence | Flags excessive nominalizations per sentence |
| `Clarity.PrepositionalDensity` | occurrence | Flags excessive prepositional phrases per sentence |

### markdownlint structural rules

12 structural MD rules run automatically (unless `--no-markdownlint`). Configure via `.markdownlint.json/.yaml/.yml`. Inline suppression via `<!-- markdownlint-disable MD013 -->` / `<!-- markdownlint-enable MD013 -->`.

Python custom rules via `.markdownlint-cli2.yaml`:

```yaml
customRules:
  - my_custom_rule.py
```

## Rules

| Check | Severity | Description |
|-------|----------|-------------|
| `Heading.H1` | error | Missing top-level H1 |
| `Completeness.ResultVerification` | error | Imperative section has no verification step |
| `Heading.Generic` | warning | Heading uses a generic name (overview, introduction, etc.) |
| `Heading.InformationScent` | warning | Heading gives no signal about section content |
| `Unity.HeadingTopicCoherence` | warning | Heading and topic sentence share too few content words |
| `Cohesion.GivennessBreak` | warning | High pronoun density without noun anchors |
| `Cohesion.Break` | warning | No discourse bridge between consecutive sentences |
| `Cohesion.DeicticGhost` | warning | Demonstrative pronoun with no antecedent in prior context |
| `Symmetry.Parallelism` | warning | List items lack parallel grammatical structure |
| `Symmetry.OrderedListImperatives` | warning | Steps in a task list do not start with imperatives |
| `Structure.TaskOrientation` | warning | Task-oriented section lacks imperative structure |
| `Rhetoric.ComplexitySpike` | warning | Propositional density spikes sharply within a section |
| `Structure.WallOfText` | warning | Long prose block with no structural breaks |
| `Navigation.FindabilityMap` | warning | Document lacks navigational structure for its length |
| `Resilience.ErrorPathPresence` | warning | Procedural section has no failure guidance or error scenario |
| `Heading.VividScent` | suggestion | Heading language is weak or vague |
| `Heading.NearDuplicate` | suggestion | Two headings are nearly identical (Jaccard ≥ 0.70) |
| `Unity.TopicSectionDrift` | suggestion | Topic sentence drifts from body content |
| `Rhetoric.ThroatClearing` | suggestion | Section opens with high-stopword sentence |
| `Attention.SplitAttention` | suggestion | Sentence exceeds maximum token count (default 45) |
| `Completeness.SchemaMapping` | suggestion | Section missing expected structural elements |
| `Completeness.StructureLead` | suggestion | Section opens directly with a list or code block without a lead sentence |
| `Structure.ActionableHeadings` | suggestion | Noun-only headings in a task-oriented document |
| `Curriculum.MissingAssessment` | suggestion | Curriculum section has no assessment element (genre-gated) |

### NLP rules (spaCy-based)

| Check | Severity | Description |
|-------|----------|-------------|
| `Attention.SyntacticDepth` | suggestion | Sentence has deeply nested clause structure |
| `Rhetoric.Nominalization` | suggestion | Nominalized verb form in "the X of" prepositional pattern |
| `Attention.MetricDensity` | suggestion | Sentence has high proportion of numeric tokens |
| `Rhetoric.ToneImbalance` | suggestion | Excessive authoritative modals or negative framing |
| `Terminology.PreferredForm` | suggestion | Term does not match required form in `TERMINOLOGY_FILE` |
| `Symmetry.TabVariantBalance` | suggestion | Content-tab variants have unequal step counts |
| `Rhetoric.PassiveVoiceActorGap` | suggestion | Passive construction without an explicit by-agent |
| `Attention.SentenceRhythm` | suggestion | Monotonous or wildly uneven sentence-length pacing |
| `Completeness.UnsupportedClaim` | suggestion | Assertion signal not followed by evidence within 2 sentences |

## Configuration

Any key in `const.py` can be overridden via config file:

```yaml
# .rhetoric-lint.yaml
MAX_SENTENCE_TOKENS: 35
REQUIRE_H1: false
UNITY_MIN_HEADING_TOPIC_CONTENT_OVERLAP: 0.15
COMPLETENESS_STRUCT_LEAD_MIN_LIST_ITEMS: 3
NLP_MAX_CHARS: 500000
```

```bash
rhetoric-lint --config .rhetoric-lint.yaml docs/
```

## Development

```bash
make test          # run pytest
make test-cov      # run pytest with coverage report
make lint-self     # run rhetoric-lint on docs/ and README.md
make rules         # list all rules
make clean         # remove __pycache__, .pytest_cache, .coverage
```
