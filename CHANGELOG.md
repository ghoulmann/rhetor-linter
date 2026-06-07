# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `extends: spelling` Vale rule type via `spylls` optional dependency (`pip install 'rhetoric-lint[spell]'`)
- `style-sets/Spelling/` — US English spell-checking with pre-built `vocab/aws.txt` (~80 AWS service/tool names) and `vocab/tech.txt` (~200 general tech terms)
- `const.DIMENSION_MAP` — maps five scoring dimensions (Clarity, Structure, Completeness, Style, Readability) to rule-check prefixes; `DIMENSION_DEFAULT = "Style"` fallback
- `const.FRONTMATTER_ALIASES` — canonical key → alias list for frontmatter normalisation
- `context["frontmatter"]` — parsed YAML frontmatter available to all rules (F2)
- `context["section_annotations"]` — per-section metadata from `<!--\n---\nyaml\n---\n-->` annotation blocks (F1); `sec["annotation"]` and `sec["topic_type"]` override classifier result
- `Rhetoric.PassiveVoiceActorGap` — spaCy rule: passive construction without explicit by-agent (SP9)
- `Attention.SentenceRhythm` — spaCy rule: monotonous or wildly uneven sentence-length pacing (SP9)
- `Completeness.UnsupportedClaim` — spaCy rule: assertion signal not followed by evidence within 2 sentences (SP9)
- `Rhetoric.ReadabilityGrade` — Vale YAML rule (`extends: readability`, `metric: Lexi`): flags paragraphs with composite readability score below 65
- `Rhetoric.UnresolvedContrast` — contrast signal (however, but, etc.) without a following resolution sentence
- 6 NLP rules (SP8): `Attention.SyntacticDepth`, `Rhetoric.Nominalization`, `Attention.MetricDensity`, `Rhetoric.ToneImbalance`, `Terminology.PreferredForm`, `Symmetry.TabVariantBalance`
- Vale `Rhetoric` style set: `Terminology.yml` (inclusive terminology substitutions with regex swap keys), `Inclusivity.yml`, `InclusivityFlag.yml`
- Vale `Clarity` style set: `FleschReadingEase.yml`, `Nominalizations.yml`, `PrepositionalDensity.yml`
- Vale `Rhetoric.TrivializingLanguage` and `TrivializingLanguage-just` migrated from Python to Vale YAML (SP6)
- Vale runner extended types (SP4): `occurrence`, `metric`, `capitalization`, `repetition`, `consistency`, `conditional`, `readability`, `sequence`
- Lexi composite readability score in `runners/_readability.py` (matches Rebilly/lexi formula and weights exactly)
- markdownlint-cli2 Python custom rule extension (SP5)
- 12 native markdownlint MD rules (SP3)
- `StyleRunner` ABC, `ValeStyleRunner`, `MarkdownlintRunner`, fix framework, `CrossFileContext` stub (SP1/SP2)
- `--fix` flag: applies deterministic fixes in-place (substitution rules, selected markdownlint rules)
- `--style-dir` / `--style` / `--no-vale` / `--no-markdownlint` CLI flags

### Changed
- README.md promoted from README2.md draft; README2.md removed
- `style-sets/` is now the canonical location for all Vale-compatible style sets; `styles/` removed
- Substitution swap keys treated as raw regex patterns (not escaped), enabling Vale-style patterns like `fire(?:m[ae]n|wom[ae]n)`

### Changed
- Genre set updated to Diataxis-aligned 10-genre taxonomy: `howto`, `tutorial`, `concept`, `explanation`, `reference`, `adr`, `postmortem`, `changelog`, `readme`, `general`; removed `technical`, `scientific`, `curriculum` as classifier-inferred outputs
- `classify_genre()` now accepts `path` parameter; filename-based detection takes highest priority (README→`readme`, CHANGELOG/HISTORY→`changelog`, CONTRIBUTING/SECURITY→`howto`)
- Genre accuracy thresholds now only enforced when `GENRE_GATE_ENABLED=True`; test always runs and reports diagnostics
- Corpus labels updated from `technical` to Diataxis genres across 45 documents

### Fixed
- Lexi NaN guard: `coleman_liau_index` NaN now clamps to 0.0 matching Rebilly/lexi reference behaviour
- Exception matching in existence/substitution rules now searches full line text (not just matched token), fixing multi-word exceptions like `lame duck`
- `_blank_html_comments` no longer strips section annotation blocks (F1 pre-pass runs first)
