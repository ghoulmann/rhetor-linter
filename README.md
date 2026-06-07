# rhetoric-lint

A Markdown linter for rhetorical and structural quality. Drop-in Vale alternative for CI/CD pipelines. Checks cohesion, unity, completeness, symmetry, attention, headings, and rhetoric using spaCy NLP and a mistletoe AST parser.

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
{ "Genre": {"file.md": "technical"}, "Matches": [{ "Path": "...", "Line": 1, "Check": "...", "Message": "...", "Severity": "warning" }] }
```

**Text**: `file.md:LINE:COL: [SEVERITY] RULE — message`

**Line**: one JSON object per line (for log pipelines).

**YAML**: requires `pyyaml`.

## Style runners

rhetoric-lint has two optional style runners that run alongside the built-in Python rules.

### Vale-compatible rules (`--style-dir`)

Any directory of Vale-format `.yml` rule files can be loaded. Supported rule types: `existence`, `substitution`, `occurrence`, `metric`, `capitalization`, `repetition`, `consistency`, `conditional`, `readability`, `sequence`.

```bash
# Run built-in Rhetoric style set (TrivializingLanguage, Terminology, Inclusivity)
rhetoric-lint --style-dir style-sets/ --style Rhetoric docs/

# Run multiple style sets
rhetoric-lint --style-dir style-sets/ --style Rhetoric,write-good docs/
```

The `Rhetoric` style set ships in `style-sets/Rhetoric/`:

| Style rule | Type | Description |
|-----------|------|-------------|
| `Rhetoric.TrivializingLanguage` | existence | Flags `simply`, `easily`, `obviously`, `of course`, `straightforward` |
| `Rhetoric.TrivializingLanguage-just` | existence | Flags `just` with temporal-use exceptions |
| `Rhetoric.Terminology` | substitution | Suggests inclusive terminology replacements (`whitelist` → `allowlist`, etc.) |
| `Rhetoric.Inclusivity` | substitution | Flags language with more inclusive alternatives |
| `Rhetoric.InclusivityFlag` | existence | Flags terms without clean drop-in replacements |

Genre gating: add a `genre:` field to any rule YAML to restrict it to matching document genres. Add `meta.yml` with `genre:` to gate an entire style set.

### markdownlint structural rules

12 structural MD rules run automatically (unless `--no-markdownlint`). Configure via `.markdownlint.json/.yaml/.yml` discovered from the file's directory. Inline suppression via HTML comments:

```html
<!-- markdownlint-disable MD013 -->
Long line here is OK.
<!-- markdownlint-enable MD013 -->
```

Rules with auto-fix support (applied by `--fix`): MD003, MD009, MD010, MD012, MD022, MD031, MD032.

Python custom rules via `.markdownlint-cli2.yaml`:

```yaml
customRules:
  - my_custom_rule.py
```

```python
# my_custom_rule.py
NAMES = ["my-rule"]
def check(context, on_error):
    for i, line in enumerate(context["lines"], 1):
        if "FIXME" in line:
            on_error(i, detail="FIXME found", fix="TODO")
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | No violations |
| `1` | Warnings or suggestions only |
| `2` | At least one `error`, or CLI/config failure |

## Classification

The linter classifies every document along three dimensions before running rules:

| Dimension | Granularity | Classifier | Example values |
|-----------|-------------|------------|----------------|
| Genre | Document | `genre.py` | `technical`, `adr`, `postmortem`, `curriculum` |
| Topic type | Section | `topic_type.py` | `concept`, `howto`, `reference`, `faq` |
| Doc template | Document (technical sub-genre) | `template_type.py` | `quick_start`, `architecture`, `platform_onboarding` |

**Genre** shapes structural expectations at the document level (e.g. ADR requires a `Status:` field; Postmortem requires action items with owners).

**Topic type** is assigned per-section based on heading keywords, list structure, and spaCy POS tags. It shapes rules that fire inside individual sections (e.g. How-To steps must begin with imperative verbs; Concept sections must not contain procedural ordered lists).

**Doc template** is a finer classification within the `technical` genre. It enforces section-presence completeness (e.g. a Quick Start must have Prerequisites, a core task, a Verify step, and Next Steps).

Genre classification is currently ungated (`GENRE_GATE_ENABLED = False`); all rules self-qualify internally using structural signals.

## Rules

Several rules — particularly the heading-topic coherence, cohesion, and task
orientation checks — work best when each section opens with a plain introductory
sentence before any table, code block, or list. The linter treats the first
substantial sentence as the section's topic sentence and measures its overlap
with the heading and body. When a section jumps straight into structured content,
that overlap is zero and the rule fires. Adding a short lead-in sentence
(e.g., "The CLI accepts the following flags:") resolves most of these and is
generally good practice for both human readers and automated retrieval systems.

### Core structural rules

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
| `Engine.OversizedDocument` | suggestion | File exceeds NLP_MAX_CHARS; full-document NLP was truncated (section-level checks still run on the complete file) |

### NLP rules (spaCy-based)

| Check | Severity | Description |
|-------|----------|-------------|
| `Attention.SyntacticDepth` | suggestion | Sentence has deeply nested clause structure (dep-tree depth + subordinate clause count); gated to concept/explanation sections |
| `Rhetoric.Nominalization` | suggestion | Nominalized verb form in "the X of" prepositional pattern (concept/explanation sections only) |
| `Attention.MetricDensity` | suggestion | Sentence has high proportion of numeric tokens (>30% in ≥12-token sentences) |
| `Rhetoric.ToneImbalance` | suggestion | Document tone is unbalanced: excessive authoritative modals (in how-to/tutorial) or negative framing |
| `Terminology.PreferredForm` | suggestion | Term does not match required form in `TERMINOLOGY_FILE` |
| `Symmetry.TabVariantBalance` | suggestion | Content-tab variants have unequal step counts (exceeds `TAB_VARIANT_STEP_TOLERANCE`) |

### Architecture Decision Records (ADR)

Self-qualify on: `Status:` field + ≥2 ADR-section headings, or ≥3 ADR-section headings alone.

| Check | Severity | Description |
|-------|----------|-------------|
| `ADR.MissingDecision` | error | ADR is missing a Decision section |
| `ADR.MissingStatus` | warning | ADR is missing a `Status:` field |
| `ADR.UndecidedStatus` | warning | ADR `Status` is Proposed/Draft but Decision section has no body |
| `ADR.MissingConsequences` | warning | ADR is missing a Consequences, Trade-offs, or Impact section |

### Postmortem / Incident Reports

Self-qualify on: ≥3 postmortem-signal headings (Timeline, Impact, Root Cause, Action Items, etc.).

| Check | Severity | Description |
|-------|----------|-------------|
| `Postmortem.MissingRootCause` | error | Postmortem has no Root Cause or Contributing Factors section |
| `Postmortem.MissingActionItems` | error | Postmortem has no Action Items or Corrective Actions section |
| `Postmortem.OpenActionItem` | warning | Action item has no assigned owner (`@mention`) and no due date |
| `Postmortem.MissingTimeline` | warning | Postmortem has no Timeline section |

### Topic-type checks

Assigned per-section by `topic_type.py` based on heading keywords, list structure, and spaCy POS tags.

**Concept** — high-level orientation; must not drift into procedures.

| Check | Severity | Description |
|-------|----------|-------------|
| `Concept.ProcedureLeak` | warning | Concept section contains ≥3 ordered imperative steps — move to a How-To |

**Troubleshooting** — reactive resolution guidance; remediation must be sequenced.

| Check | Severity | Description |
|-------|----------|-------------|
| `Troubleshooting.MissingRemediation` | warning | Troubleshooting section has no ordered remediation steps |
| `Troubleshooting.UnorderedRemediation` | warning | Troubleshooting remediation steps are in an unordered list; order matters |

**How-To** — goal-oriented directions; steps must be imperative and ordered.

| Check | Severity | Description |
|-------|----------|-------------|
| `HowTo.UnorderedSteps` | warning | How-To section uses an unordered list where a numbered sequence is required |
| `HowTo.NonImperativeStep` | suggestion | How-To step does not begin with an imperative verb |

**FAQ** — self-contained Q&A pairs; each entry must be a question with a substantive answer.

| Check | Severity | Description |
|-------|----------|-------------|
| `FAQ.EmptyAnswer` | warning | FAQ entry has no substantive answer |
| `FAQ.NonQuestionEntry` | suggestion | FAQ heading is not phrased as a question |

**Tutorial** — learning-oriented; single path, observation cues required.

| Check | Severity | Description |
|-------|----------|-------------|
| `Tutorial.AlternativesDiversion` | warning | Tutorial offers alternative paths — tutorials must follow a single route |
| `Tutorial.NoObservationCues` | suggestion | Tutorial section has no feedback mechanism ("you should see", "notice that", etc.) |

**Reference** — technical machinery description; must not contain procedural steps.

| Check | Severity | Description |
|-------|----------|-------------|
| `Reference.ContainsInstructions` | warning | Reference section contains procedural steps — move to a How-To |

**Explanation** — discursive treatment; must connect to related concepts.

| Check | Severity | Description |
|-------|----------|-------------|
| `Explanation.ContainsInstructions` | warning | Explanation section contains procedural steps — move to a How-To |
| `Explanation.NoConnections` | suggestion | Explanation section has no links to related concepts |

### Document template checks

Classified per-document by `template_type.py`. All checks enforce section-presence completeness or structural anti-patterns within a specific template.

**Product Overview** — capabilities and use cases; no procedures.

| Check | Severity | Description |
|-------|----------|-------------|
| `ProductOverview.MissingOverview` | warning | Missing an Overview or Introduction section |
| `ProductOverview.MissingCapabilities` | warning | Missing a Capabilities or Features section |
| `ProductOverview.ProcedureLeak` | warning | Contains procedural steps — link to a How-To instead |
| `ProductOverview.MissingUseCases` | suggestion | Missing a Use Cases section |

**Architecture** — all sections should be Concept type.

| Check | Severity | Description |
|-------|----------|-------------|
| `Architecture.MissingOverview` | warning | Missing an Overview section |
| `Architecture.MissingTechnicalDesign` | warning | Missing a Components or Technical Design section |
| `Architecture.ProcedureLeak` | warning | Contains procedural steps — Architecture docs should be Concept throughout |

**Use Cases** — one use case per section.

| Check | Severity | Description |
|-------|----------|-------------|
| `UseCases.MissingOverview` | warning | Missing an Overview section |
| `UseCases.MultipleUseCasesInSection` | suggestion | A section contains multiple sub-use-cases — each should be its own top-level section |

**Onboarding** — overview + requirements + steps.

| Check | Severity | Description |
|-------|----------|-------------|
| `Onboarding.MissingSteps` | error | Missing a How-To steps section |
| `Onboarding.MissingOverview` | warning | Missing an Overview section |
| `Onboarding.MissingRequirements` | warning | Missing a Requirements or Prerequisites section |

**Quick Start** — minimal path to first success.

| Check | Severity | Description |
|-------|----------|-------------|
| `QuickStart.MissingCoreTask` | error | Missing a core task How-To section |
| `QuickStart.MissingOverview` | warning | Missing an Overview section |
| `QuickStart.MissingPrerequisites` | warning | Missing a Prerequisites section |
| `QuickStart.MissingVerification` | warning | Missing a Verify step — readers need confirmation that setup succeeded |
| `QuickStart.MissingNextSteps` | suggestion | Missing a Next Steps section |

**Platform Onboarding** — comprehensive setup: env + auth + workflow + key concepts + troubleshooting.

| Check | Severity | Description |
|-------|----------|-------------|
| `PlatformOnboarding.MissingOverview` | warning | Missing an Overview section |
| `PlatformOnboarding.MissingPrerequisites` | warning | Missing a Prerequisites section |
| `PlatformOnboarding.MissingEnvSetup` | warning | Missing an Environment Setup section |
| `PlatformOnboarding.MissingAuth` | warning | Missing an Authentication section |
| `PlatformOnboarding.MissingWorkflow` | warning | Missing a Workflow or core task section |
| `PlatformOnboarding.MissingVerification` | warning | Missing a Verify step |
| `PlatformOnboarding.MissingTroubleshooting` | warning | Missing a Troubleshooting section |
| `PlatformOnboarding.MissingKeyConcepts` | suggestion | Missing a Key Concepts section |
| `PlatformOnboarding.MissingNextSteps` | suggestion | Missing a Next Steps section |

## Configuration

Any key in `const.py` can be overridden via config file:

```yaml
# .rhetoric-lint.yaml
MAX_SENTENCE_TOKENS: 35
REQUIRE_H1: false
UNITY_MIN_HEADING_TOPIC_CONTENT_OVERLAP: 0.15
COMPLETENESS_STRUCT_LEAD_MIN_LIST_ITEMS: 3  # lists shorter than this don't require a lead sentence
NLP_MAX_CHARS: 500000                       # truncate full-doc NLP for large files
```

```bash
rhetoric-lint --config .rhetoric-lint.yaml docs/
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture constraints, the rule
authoring guide, and the
[Genre Labeling Guide](tests/fixtures/corpus/LABELING_GUIDE.md) for corpus
annotation work.

## Development

```bash
make test          # run pytest
make test-cov      # run pytest with coverage report
make lint-self     # run rhetoric-lint on docs/ and README.md
make rules         # list all rules
make clean         # remove __pycache__, .pytest_cache, .coverage
```
