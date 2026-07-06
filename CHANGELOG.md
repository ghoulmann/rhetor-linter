# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- SP_MDLINT_FULL: markdownlint native rule coverage expanded from 12 to ~50 rules (`markdownlint.MD004`–`markdownlint.MD060`) in `rhetoric_lint/runners/markdownlint.py`; adds 5 shared helpers (`_blockquote_regions`, `_link_ref_definitions`, `_heading_to_anchor`, `_inline_code_spans`, `_in_code_span`); all fixable rules carry `fix` payloads
- `Clarity.MergeConflictMarkers` Vale YAML rule (`scope: raw`, `level: error`) — flags `<<<<<<<`, `=======`, `>>>>>>>` conflict markers anywhere in document text; Vale runner `scope: raw` now correctly scans full document line-by-line (was incorrectly limited to code-fence nodes)
- SP23: Frontmatter metadata enforcement (opt-in, `FRONTMATTER_ENFORCEMENT_ENABLED = False`) — `Metadata.MissingOwner`, `Metadata.MissingAudience`, `Metadata.InvalidAudience`, `Metadata.Stale`, `Metadata.MissingDate`; `METADATA_STALE_DAYS = 183`; `VALID_AUDIENCE_VALUES` configurable
- SP21: `Heading.SiblingParallelism` — flags H2 headings that break grammatical pattern of siblings (verb-led vs. noun-led) when minority < 33% of group; requires spaCy; `const.HEADING_PARALLELISM_MIN_GROUP = 3`
- SP22: 5 Reference genre completeness checks — `Reference.MissingAuth`, `Reference.MissingRateLimit`, `Reference.MissingVersioning`, `Reference.MissingRequestExample`, `Reference.MissingParameterTable`; two-tier detection (heading variant OR marker vocabulary); gated to `reference` genre or API-indicator headings; 150-word floor
- SP20: 6 new markdownlint extension checks — `markdownlint.MD045` (image alt text), `markdownlint.MD046` (fenced code style consistency), `Structure.StackedHeadings`, `Structure.ListLeadColon`, `Structure.ImageInTable`, `Structure.SingleHeaderRow`
- SP19: 9 new Vale YAML rules in `style-sets/Clarity/` — `NoPlease`, `PositiveLanguage`, `NoGerundHeadings` (genre-gated, excludes `howto`), `HardCodedVersions`, `HeadingSentenceCase`, `HeadingLength`, `NoQuestionHeadings` (genre-gated, excludes `faq`), `ParagraphSentenceCount`, `TableHeaderCase`
- Vale runner: comma-separated genre list support in `genre:` field (e.g. `genre: howto, concept, reference`) — inclusion-based multi-genre gate
- Vale runner: `nonword: true` now uses tokens as raw regex patterns (no `re.escape`), matching Vale's actual semantics; `nonword: false` (default) continues treating tokens as literals with word boundaries
- `Coverage.MissingJobCoverage` rule (SP12): fires a warning for each JTBD job in a `jtbd-manifest.json` where `coverage == "missing"` and no paragraph in the file meets the Jaccard threshold; disabled when `--jtbd-manifest` is not set
- `--jtbd-manifest <path>` CLI flag: loads a jtbd-tool manifest and enables `Coverage.MissingJobCoverage`
- `const.JTBD_MANIFEST_PATH` and `const.JTBD_COVERAGE_JACCARD_MIN` (default 0.30)
- `.pre-commit-hooks.yaml`: `rhetoric-lint` (warn+) and `rhetoric-lint-error` (error-only) hook definitions for pre-commit
- `.github/workflows/rhetoric-lint.yml`: GitHub Actions workflow — checks out, installs, downloads `en_core_web_sm`, runs `rhetoric-lint lint` on `docs/` and `README.md`
- `docs/ci-integration.md`: setup guide covering pre-commit, GitHub Actions, severity knob, file scoping, and score subcommand
- `rhetoric-lint score` CLI subcommand: runs a full lint pass and outputs dimension scores (Clarity, Structure, Completeness, Style, Readability) as JSON with per-1000-word densities; always exits 0
- `RhetoricEngine.last_doc_templates` and `last_word_counts` — per-file metadata persisted after each `lint_files()` call, used by `score_file()`
- `score_file()` accepts optional `word_count` kwarg for callers that have pre-computed token counts
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

### Removed
- MyST/Sphinx precision-corpus fixtures dropped as least concern for validated corpus coverage: `black-usage.md`, `click-commands.md`, `court-scraper-site-discovery.md`, `myst-typography.md` (+ `.label` files); `engine.py` MyST preprocessing is unaffected — see `history/2026-07-02-myst-corpus-scope-decision.md`
- `fastapi-first-steps.md` corpus fixture restored after being incidentally deleted alongside the MyST fixtures; it is MkDocs Material, not MyST, and was not part of the scope decision

### Fixed
- `score.py`: `{**dimension_map, dimension_default}` syntax error (was never imported by tests; caught on first CLI run)
- `Symmetry.Parallelism`: items containing Markdown links received out-of-bounds positions from the engine's fallback (`pos = pointer` when `_node_text()` strips link syntax and pattern search fails); these overflowed items were grouped into a spurious mega-list and all findings reported at line `len(text)+1`; fix filters items with `start >= len(text)` before grouping
- Lexi NaN guard: `coleman_liau_index` NaN now clamps to 0.0 matching Rebilly/lexi reference behaviour
- Exception matching in existence/substitution rules now searches full line text (not just matched token), fixing multi-word exceptions like `lame duck`
- `_blank_html_comments` no longer strips section annotation blocks (F1 pre-pass runs first)
