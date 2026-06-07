# Master Plan: Vale + markdownlint + NLP Expansion

## Global constraints

1. **Rigorous unit tests in every subplan** — each rule must have tests for: true positives, false positive suppression (edge cases the rule must NOT fire on), empty input, malformed input, multi-match, and scope boundary. No subplan ships without its tests passing.
2. **No shell-outs** — all execution is native Python. markdownlint-cli2 JS custom rules are not executed; the cli2 config format is supported as a manifest for Python custom rules only.
3. **Fix/correction support** — every finding that has a deterministic fix includes a `fix` dict. The finding shape gains an optional `fix` key. A `--fix` CLI flag applies all fixable findings in-place.
4. **Context-aware AST scoping** — the Vale runner uses the mistletoe AST already built by the engine. Text extraction per scope is node-type-aware: `paragraph` scope excludes `CodeFence`, `InlineCode`, `Link` href, and `Image` src nodes by default. Rules never fire on content inside code blocks unless explicitly scoped to `code` or `raw`. This is a fundamental precision advantage over standard Vale.
5. **Genre-gated styles** — both Vale rules and markdownlint rules may declare a `genre:` constraint (a rhetor-linter extension to the respective YAML/config formats). The runner skips rules whose genre list does not include the document's classified genre. This allows strict imperative checks in howto/tutorial genres, readability thresholds tuned per genre, and discursive prose rules enabled only in concept/explanation genres.
6. **Finding shape** (extended):
   ```python
   {
     "path": str, "line": int, "column": int,
     "check": str, "message": str, "severity": str,
     "fix": {                          # optional — present only when fix is deterministic
       "type": "replace" | "remove" | "insert",
       "edit_column": int,             # 1-based column to start edit
       "delete_count": int,            # chars to delete (0 = pure insert)
       "insert_text": str,             # text to insert after deletion
     }
   }
   ```
7. **Code-block immunity** — no rule fires on content inside a fenced code block or inline code span. The engine's `nodes` list carries `type == "CodeFence"` and `type == "Code"` metadata. Any rule that accesses paragraph text must filter these out before matching.
8. **Minimum-content guard** — rules that compute ratios, CV, or grade levels must define a minimum content threshold (sentences, words, or tokens) below which they are silent. Noisy findings on 2-sentence sections are worse than misses.
9. **Test fixture pairing** — every new rule requires a "must not fire" fixture alongside its "must fire" fixture. Rules failing against any file in `tests/fixtures/corpus/technical/` are blocked from merging.
10. **Full RST analysis is out of scope** — requires a neural discourse parser (heavy dep, low precision on technical docs). `SP_CONTRAST` covers the Contrast discourse relation only; remaining RST relations have insufficient signal-to-noise for this use case.

---

## Dependency graph

```
SP1: Runner Infrastructure + Fix Framework + CrossFileContext stub
 ├── SP2: Vale Core (existence + substitution)
 │    ├── SP4: Vale Extended Types (+ _readability.py)
 │    │    └── SP9: ProsePartner Gaps (also needs SP8)
 │    ├── SP6: Rhetoric YAML Migration (TrivializingLanguage)
 │    ├── SP7: Rhetoric YAML Additions (Terminology, Inclusivity)
 │    └── SP_SPELL: Vale spelling rule type
 ├── SP3: markdownlint Native Rules
 │    └── SP5: markdownlint-cli2 Python Custom Rule Extension
 ├── SP8: NLP Rule Expansion (5 rules + TabVariantBalance)
 │    └── SP9: ProsePartner Gaps (also needs SP4)
 └── CrossFileContext (from SP1)
      ├── SP10: DependencyReveal
      └── SP11: ConceptReintroductionPenalty

Independent (after SP1 CLI stable):
 └── SP_CI: Pre-commit + GitHub Actions

Independent (any time):
 └── SP_CONTRAST: Rhetoric.UnresolvedContrast
```

| # | Subplan | Depends on |
|---|---|---|
| SP1 | Runner infrastructure + fix framework + CrossFileContext stub | — | ✅ done |
| SP2 | Vale core types (existence + substitution) | SP1 | ✅ done |
| SP3 | markdownlint native MD rules | SP1 | ✅ done |
| SP4 | Vale extended types (occurrence … sequence/NLP) | SP2 | ✅ done |
| SP5 | markdownlint-cli2 Python custom rule extension | SP3 | ✅ done |
| SP6 | Migrate TrivializingLanguage to Vale YAML | SP2 | ✅ done |
| SP7 | Rhetoric YAML additions (Terminology, Inclusivity) | SP2 | ✅ done |
| SP8 | NLP rule expansion (6 spaCy rules + TabVariantBalance) | SP1 | ✅ done |
| SP9 | ProsePartner gaps (3 Python rules + ReadabilityGrade.yml) | SP8, SP4 | ✅ done |
| SP_SPELL | Vale spelling rule type (spylls optional dep) | SP2 | ✅ done |
| SP_CONTRAST | Rhetoric.UnresolvedContrast | — | ✅ done |
| SP_GENRE | Genre refactor: 10-genre Diataxis set, filename detection, corpus relabeling | — | ✅ done |
| F1 | Section annotation pre-pass | engine.py | ✅ done |
| F2 | Frontmatter parsing + FRONTMATTER_ALIASES | engine.py | ✅ done |
| F4 | SCORE_MIN_WORDS = 150 + score.py skeleton | const.py, score.py | ✅ done |
| F5 | DIMENSION_MAP (5 scoring dimensions) | const.py | ✅ done |
| F9 | metadata.py: normalise_topic_type, normalise_owner, normalise_frontmatter | metadata.py | ✅ done |
| SP_CI | Pre-commit + GitHub Actions integration | SP1 | open |
| SP10 | DependencyReveal (multi-file) | CrossFileContext (SP1) | backlog |
| SP11 | ConceptReintroductionPenalty (multi-file) | CrossFileContext (SP1) | backlog |

SP2 + SP3 + SP8 + SP_CI + SP_CONTRAST start together after SP1. SP9 waits for both SP8 and SP4. SP_SPELL waits for SP2. SP10/SP11 wait for CrossFileContext (delivered in SP1).

---

## Implementation sequence

```
Tier 0 — Infrastructure (unblocks everything)
  SP1: StyleRunner ABC + fix.py + engine wiring + --fix flag + CrossFileContext stub

Tier 1 — Core runners (parallel after SP1)
  SP2:         Vale existence + substitution + AST scoping + genre gating
  SP3:         markdownlint native rules (12 rules) + inline suppression
  SP8:         NLP rules — SyntacticDepth, Nominalizations, MetricDensity,
               ToneImbalance, Terminology, TabVariantBalance
  SP_CI:       .pre-commit-hooks.yaml + GH Actions workflow + docs/ci-integration.md
  SP_CONTRAST: Rhetoric.UnresolvedContrast in rhetoric.py

Tier 2 — Extensions (parallel after Tier 1)
  SP4:      Vale extended types + _readability.py shared module
  SP5:      markdownlint-cli2 Python custom rule extension
  SP6:      Migrate TrivializingLanguage to Vale YAML
  SP_SPELL: Vale spelling rule type (spylls optional dep)

Tier 3 — Depends on Tier 2
  SP9:      ProsePartner gaps — PassiveVoiceActorGap, SentenceRhythm,
            UnsupportedClaim (Python/spaCy, needs SP4 + SP8) +
            ReadabilityGrade.yml (Vale YAML, extends: readability, metric: Lexi)
  SP7:      Rhetoric YAML additions — Terminology.yml, Inclusivity.yml  ✅ done
  SP_GENRE: 10-genre Diataxis classifier — filename detection, changelog/readme/howto
            signals, dominant topic_type inference; corpus relabeled; accuracy gate
            conditional on GENRE_GATE_ENABLED  ✅ done

TODO
  TabVariantBalance: rule is structural (AST OL-item counting), not NLP — no spaCy dep.
    After SP8 ships, move it out of the NLP grouping and note in symmetry.py that it
    requires no language model. The max-min arithmetic stays; only the SP8 label is wrong.

  Docs generation: two-tool hybrid.
    - pdoc (dev dep) for Python rule modules → docs/api/
    - `rhetoric-lint docs` CLI subcommand for YAML style rules (styles/*/*.yml)
      Outputs Markdown in same style as pdoc; grouped by style dir; reads
      message/level/extends/link from each YAML file.
    - meta.json required in each styles/* subdir for section headers.
    - Makefile `docs` target runs both in sequence.
    - ~14 rule modules need minimal check() docstrings before pdoc is useful:
      adr, concept, doc_templates, explanation, faq, headings, howto,
      metric_density, nominalizations, postmortem, preferred_form, reference,
      syntactic_depth, tone, troubleshooting, tutorial.

  Enterprise platform design — adversarial review findings (2026-06-07)
  Must resolve before any server/scoring implementation begins:

  ✅ [FATAL F1] FIXED (2026-06-07). `_extract_section_annotations()` runs on raw text
    before `_blank_html_comments()`; results stored in `context["section_annotations"]`
    keyed by 1-based heading line number; `sec["annotation"]` and `sec["topic_type"]`
    override set per-section. Tests in `tests/test_f1_f2_f5.py`.

  ✅ [FATAL F2] FIXED (2026-06-07). `_parse_frontmatter()` runs on raw text before
    blanking; stored in `context["frontmatter"]`; aliases normalised via
    `const.FRONTMATTER_ALIASES`. Frontmatter `topic_type` overrides sections[0].
    Tests in `tests/test_f1_f2_f5.py`.

  [FATAL F3] SP12 emits N×M spam (jobs × files) when coverage is missing.
    jtbd-tool marks job coverage=="missing" corpus-wide → SP12 re-runs Jaccard per-file
    and fires on every file by definition. 5 jobs × 50 files = 250 identical findings.
    Fix: emit one corpus-level finding per missing job via CrossFileContext (SP1 done),
    not one per file. Alternatively: require manifest to include primary_doc_path hint.

  [MAJOR F4] Density rate model needs minimum word floor.
    50-word stub with 3 findings = 60/1kw; 5000-word doc with 3 findings = 0.6/1kw.
    Fix: suppress badge / mark "insufficient sample" below 150 words (suggested threshold).

  ✅ [MAJOR F5] FIXED (2026-06-07). `const.DIMENSION_MAP` added: 5 dimensions (Clarity,
    Structure, Completeness, Style, Readability) → rule-check prefix lists. All previously
    unassigned prefixes now mapped. `const.DIMENSION_DEFAULT = "Style"` fallback.
    Tests in `tests/test_f1_f2_f5.py`.

  [MAJOR F6] SP12 tokenizer parity has no contract test.
    Plan says "reimplement _tokenize identically." Any drift in jtbd-tool stopwords
    silently diverges Jaccard scores. Fix: shared contract fixture — fixed text + job
    statement → expected Jaccard score — run against both tools in CI.

  [MAJOR F7] jtbd-reporter integration scope — RESOLVED.
    jtbd-reporter was early ideation/prototype. jtbd-tool is the planned implementation
    and sole manifest source. No integration work needed on jtbd-reporter; archive it.

  [MINOR F8] Polling staleness unquantified. For active TechDocs monorepos, daily poll
    = up to 23-hour stale scores in Backstage plugin. State limitation explicitly in
    server docs; note webhook-based refresh as planned v2 feature.

  [MINOR F9] Owner field normalization vs Backstage entity references.
    frontmatter `owner: platform-team` won't match Backstage `group:platform-team`.
    F2 is now fixed — normalization contract (prefix inference, fallback) still TBD
    but unblocked. Implement when Backstage plugin design begins.

  [MINOR F10] Server sub-package import constraint unstated.
    Rule modules must never import server-layer packages (FastAPI, SQLAlchemy) at module
    level or [server] extra becomes a hard transitive dep for all users. Add to
    CONTRIBUTING.md when server sub-package is created.

Backlog — Blocked on CrossFileContext (from SP1)
  SP10: DependencyReveal
  SP11: ConceptReintroductionPenalty

Roadmap (design notes only — see end of document)
  Cognitive Jump Distance, Intent-Artifact Closure, Narrative Compression Ratio,
  Taxonomy Alignment, Code-Prose Alignment, Interface Surface Coverage,
  Procedural State Machine, Retrieval Anchor Density
```

---

## SP1 — Runner Infrastructure + Fix Framework

**Goal:** Wire the `StyleRunner` ABC, hook it into the engine, add fix support to the finding pipeline, and add `--fix` CLI flag. No rule logic yet.

### Finding shape change

Add `apply_fixes(path: str, findings: list[dict]) -> int` utility in `rhetoric_lint/fix.py`:
- Groups fixable findings by file and line
- Applies `fix` dicts top-to-bottom per line (rightmost column first to preserve offsets)
- Returns count of applied fixes

### Files

**Create:**
- `rhetoric_lint/runners/__init__.py`
- `rhetoric_lint/runners/base.py` — `StyleRunner` ABC with `load(**kwargs)` and `check(context) → list[dict]`
- `rhetoric_lint/fix.py` — `apply_fixes(path, findings)` and `_apply_line_fix(line_text, fix) → str`

**Modify:**
- `rhetoric_lint/engine.py` — `self._runners: list[StyleRunner]`, `_init_runners(config)`, runner dispatch after Python rules; add `CrossFileContext` class (`term_first_seen: dict[str, tuple[str,str]]`, `concept_definitions: dict[str,list[str]]`, `scan(paths, nlp) -> None`); `lint_files()` instantiates and populates it before the per-file loop and passes it as `context["cross_file"]`
- `rhetoric_lint/main.py`:
  - `--style-dir PATH` (repeatable)
  - `--style NAME` (comma-separated; empty = all)
  - `--no-vale` / `--no-markdownlint`
  - `--fix` (apply all deterministic fixes in-place)
- `rhetoric_lint/const.py`:
  - `STYLE_DIRS: list[str] = []`
  - `ENABLED_STYLES: list[str] = []`
  - `MARKDOWNLINT_ENABLED: bool = True`
  - `MARKDOWNLINT_CONFIG: str = ""`
  - `TERMINOLOGY_FILE: str = ""`

### Tests

`tests/test_fix_framework.py`:
- Fix applied correctly to a line with single replacement
- Fix applied correctly when multiple fixes on same line (rightmost first)
- Fix with `delete_count=0` (pure insert)
- Fix with `insert_text=""` (pure delete)
- `--fix` flag: file is modified in place; findings with no fix are not changed
- `--fix` on read-only file: error message, no crash
- Empty findings list: no-op
- Finding without `fix` key: skipped silently
- `context["cross_file"]` is present and not None in every per-file context dict
- `CrossFileContext.scan()` on empty path list: no crash, empty dicts
- `CrossFileContext.scan()` with two fixture files: `term_first_seen` populated with at least one entry
- Rules that don't read `context["cross_file"]`: no breakage

### Verification
```bash
rhetoric-lint tests/fixtures/test_generic.md   # no crash, no new findings
rhetoric-lint --fix tests/fixtures/test_generic.md  # no crash on clean file
python -m pytest tests/test_fix_framework.py -v
python -m pytest tests/ -v
```

---

## SP2 — Vale Core Types: existence + substitution

**Goal:** Implement `existence` (81 rules) and `substitution` (45 rules) — ~70% of style-sets/. Includes fix support for substitution rules.

### Vale YAML fields consumed

```yaml
extends: existence | substitution
message: "Consider removing '%s'"
level: error | warning | suggestion
scope: text | paragraph | sentence | heading | heading.h1–h6 |
       table.header | table.cell | list | blockquote | raw | summary
ignorecase: true
nonword: false         # wrap tokens with \b word boundaries
exceptions: [word]     # literal strings; if match overlaps any exception, skip
vocab: true            # merge vocabularies/{StyleName}/accept.txt + reject.txt
tokens: [regex, ...]   # existence: patterns to find
raw: [prefix_regex]    # prefix combined with each token (e.g. passive voice)
swap: {find_pattern: suggest_text}  # substitution
capitalize: true       # capitalize suggestion if match was capitalized
```

### Scope extraction — AST-aware

Text extraction uses the mistletoe AST already built by the engine (`context["sections"]`). Every scope is node-type-filtered — never a raw text split. This is the key precision advantage over standard Vale: rules cannot accidentally fire on content inside code blocks, link URLs, or image alt text.

| Vale scope | AST source | Auto-excluded node types |
|---|---|---|
| `raw` | `context["text"]` verbatim | nothing (raw Markdown including syntax) |
| `prose` *(rhetor extension)* | `Paragraph` leaf text only | `CodeFence`, `InlineCode`, `Link` href, `Image`, `BlockQuote` |
| `paragraph` / `text` | `Paragraph` rendered text | `CodeFence`, `InlineCode` spans |
| `sentence` | `paragraph["sentences"]` | `InlineCode` spans within sentence |
| `heading` / `heading.h1–h6` | `section["heading"]` + level filter | `InlineCode` within heading text |
| `list` | `ListItem` leaf text | `InlineCode` within list items |
| `blockquote` | `BlockQuote` text | nested `CodeFence` |
| `table.header` / `table.cell` | `Table` node text | `InlineCode` in cells |
| `code` *(rhetor extension)* | `CodeFence` + `InlineCode` content | (inverted — prose excluded) |
| `summary` | full doc prose | `CodeFence` blocks stripped |

Each scope unit carries its absolute start line. Match offsets within scope text map back to absolute line numbers via the stored offset. Multi-line scope units use `text[:match.start()].count('\n')` added to the unit's start line.

### Genre gating — rhetor-linter extension to Vale YAML

An optional `genre:` field in any Vale rule restricts it to documents of matching genre. The runner reads `context["genre"]` (already classified by the engine) and skips non-matching rules entirely — zero regex overhead.

```yaml
# style-sets/HowToChecks/ImperativeStep.yml
extends: existence
message: "Step heading should start with an imperative verb: '%s'"
level: warning
scope: heading
genre: howto, tutorial          # ← rhetor-linter extension; absent = all genres
tokens: ['\b(the|a|an|this)\b']
```

Style-level genre gating via optional `meta.yml` in a style directory:
```yaml
# style-sets/HowToChecks/meta.yml
genre: howto, tutorial          # all rules in this dir only run on these genres
```

Individual rule `genre:` takes precedence over directory-level meta. Genre values match the engine's output: `howto`, `tutorial`, `concept`, `explanation`, `reference`, `adr`, `postmortem`, `changelog`, `readme`, `general`. Absent `genre:` field = applies to all genres.

### Fix support

- `existence`: `fix = {"type": "remove", "edit_column": match.start()+1, "delete_count": len(match.group()), "insert_text": ""}` — suggests removing the matched token.
- `substitution`: `fix = {"type": "replace", ..., "insert_text": swap_value}`.
- Both included only when the match is a single contiguous token (no sentence-boundary matches).

### Check naming

`"{style_dir_name}.{yaml_stem}"` — e.g., `style-sets/write-good/Passive.yml` → `"write-good.Passive"`.

### Message formatting

Vale uses Go printf `%s` / `%[1]s`. Map to Python `%s` by substituting `%[N]s` → positional args.

### Files

**Create:**
- `rhetoric_lint/runners/vale_style.py` — `ValeStyleRunner(StyleRunner)`, internal `Rule` dataclass
- `tests/test_vale_style_runner.py`

### Tests

`test_vale_style_runner.py` must cover:
- Existence: token found → finding emitted with correct line/column
- Existence: token NOT in text → no finding
- Existence `nonword: true`: `"just"` in `"justified"` → no match; `" just "` → match
- Existence `ignorecase: true/false`: case sensitivity respected
- Existence `exceptions`: match overlapping exception phrase → suppressed
- Existence `raw:` prefix: combined pattern works (passive voice test)
- Existence `scope: heading`: fires only in headings, not in paragraphs
- Existence `scope: raw`: fires on raw Markdown text including syntax characters
- Existence `scope: paragraph`: does NOT fire on identical token inside a fenced code block
- Existence `scope: paragraph`: does NOT fire on token inside an inline code span (`` `just` ``)
- Existence `scope: prose`: does NOT fire on token that is the href of a link
- `genre: howto`: fires on howto document, suppressed on general document
- `genre: tutorial, howto`: fires on both, suppressed on adr
- Rule without `genre:` field: fires on all genres
- Style with `meta.yml genre: howto`: entire style skipped on non-howto document
- Substitution: `swap` key matched → finding with suggestion in message
- Substitution `capitalize: true`: capitalized match → capitalized suggestion
- Substitution: fix dict present with correct insert_text
- Multi-match in one paragraph: all findings emitted
- Rule with empty tokens list: no crash, no findings
- YAML missing required field (`tokens` for existence): graceful skip with warning
- `vocab: true` with accept.txt containing matched word → suppressed
- Style not in `enabled_styles` → not loaded

### Verification
```bash
rhetoric-lint --style-dir style-sets/ --style write-good tests/fixtures/test_generic.md
rhetoric-lint --style-dir style-sets/ --style vale --format json tests/fixtures/test_generic.md \
  | python -c "import json,sys; [print(m['Check']) for f in json.load(sys.stdin) for m in f['Matches']]"
python -m pytest tests/test_vale_style_runner.py -v
python -m pytest tests/ -v
```

---

## SP3 — markdownlint Native Rules

**Goal:** Native Python implementation of the most-used MD structural rules using raw line array and existing mistletoe AST. Includes fix support for mechanical rules.

### Rule subset + fix support

| Rule | Check | Fix? | Notes |
|---|---|---|---|
| MD001 | Heading levels increment by one | No | Walk section levels in order |
| MD003 | Heading style consistent | Yes | Normalize to atx (`# Heading`) |
| MD009 | Trailing spaces | Yes | Delete trailing spaces |
| MD010 | Hard tabs | Yes | Replace `\t` with configured spaces |
| MD012 | Multiple consecutive blank lines | Yes | Delete extra blank lines |
| MD013 | Line length | No | Too context-dependent for safe auto-fix |
| MD022 | Blank lines around headings | Yes | Insert blank line before/after |
| MD025 | Single H1 | No | Safe fix unclear |
| MD031 | Blank lines around fenced code | Yes | Insert blank lines |
| MD032 | Blank lines around lists | Yes | Insert blank lines |
| MD040 | Fenced code has language | No | Language unknown without context |
| MD041 | First line is top-level heading | No | Requires intent |

### Config cascade

Discover `.markdownlint.json` → `.markdownlint.yaml` → `.markdownlint.yml` walking from file's directory toward project root. Stop at first found.

Inline suppression: pre-scan lines for `<!-- markdownlint-disable MD013 -->` / `<!-- markdownlint-enable MD013 -->` / `<!-- markdownlint-disable-line MD013 -->` / `<!-- markdownlint-disable-next-line MD013 -->`. Build suppression set `{(rule_id, line_number)}` before running checks.

### Genre gating for markdownlint rules

Config supports `rhetoric-genre` extension key per rule:
```json
{
  "MD041": { "rhetoric-genre": ["howto", "tutorial"] },
  "MD043": { "headings": ["# Overview", "## Steps"], "rhetoric-genre": ["howto"] }
}
```
Rules without `rhetoric-genre` run on all genres. This allows strict structural rules (MD041, MD043) to be applied only to specific doc types.

### AST-aware code block detection

Rules that operate on raw lines (MD009, MD010, MD013) pre-build a `_code_fence_lines: set[int]` by scanning for ```` ``` ```` / `~~~` fences in the line array before checking. Lines inside code fences are skipped, preventing false positives on intentional code formatting. MD040 (no language tag) is the one rule that operates *on* fence lines.

### Files

**Create:**
- `rhetoric_lint/runners/markdownlint.py` — `MarkdownlintRunner(StyleRunner)`; each rule as `_md001(lines, cfg, suppressed) → list[dict]`
- `tests/test_markdownlint_runner.py`

### Tests

`test_markdownlint_runner.py` must cover per rule:

**MD001:**
- H1 → H2 → H3: no finding
- H1 → H3 (skip level): finding on H3
- H2 → H1 (decrease): no finding
- Front matter only: no finding

**MD009:**
- Line ending in two spaces: finding + fix deletes them
- Line ending in `\n` only: no finding
- Code fence content with trailing spaces: no finding (skip code blocks)
- `br_spaces: 2` config: two trailing spaces allowed → no finding

**MD010:**
- Tab in paragraph: finding + fix replaces with 4 spaces
- Tab in fenced code block: no finding (configurable skip)
- Tab in leading indentation of list: finding

**MD012:**
- Two blank lines in sequence: finding + fix
- Three blank lines: one finding, fix removes to one blank
- Single blank line: no finding

**MD013:**
- Line of 81 chars with `line_length: 80`: finding
- Line of 80 chars: no finding
- Code block line > 80 with `code_blocks: false`: no finding
- Heading line > 80 with `headings: false`: no finding
- Table row > 80: default skip

**MD022:**
- Heading with blank line before + after: no finding
- Heading missing blank line before: finding + fix inserts blank line
- First heading in file: blank line before not required

**MD031/MD032:**
- Fenced code / list immediately after paragraph with no blank: finding + fix inserts blank line
- Fenced code at start of file: no blank line required before

**Inline suppression:**
- `<!-- markdownlint-disable MD013 -->` on line N: MD013 findings on lines > N suppressed until enable
- `<!-- markdownlint-disable-line MD013 -->`: only that line suppressed
- `<!-- markdownlint-disable-next-line MD013 -->`: only next line suppressed

### Verification
```bash
rhetoric-lint --format line tests/fixtures/test_generic.md | grep markdownlint
rhetoric-lint --fix tests/fixtures/trailing_spaces.md  # trailing spaces removed
python -m pytest tests/test_markdownlint_runner.py -v
python -m pytest tests/ -v
```

---

## SP4 — Vale Extended Types

**Goal:** Add the remaining 8 Vale rule types to `vale_style.py`, including `sequence` (NLP via spaCy).

### Types to add

| Type | Key fields | Fix? |
|---|---|---|
| `occurrence` | `token`, `max`, `min`, `ignorecase` | No |
| `metric` | `formula`, `condition`; `summary` scope | No |
| `capitalization` | `match`, `style`, `exceptions`, `indicators`, `threshold` | Yes — fix = apply correct case |
| `repetition` | `tokens`, `max`, `alpha` | Yes — fix = remove repeated token |
| `consistency` | `either` | No |
| `conditional` | `first`, `second` | No |
| `readability` | `metrics`, `grade` | No |
| **`sequence`** | `tokens[].{pattern, tag, skip, negate}` | No |

### `readability` type — Vale-compatible implementation

**Non-negotiable constraint:** For the same document, the `readability` rule type must produce the same grade level as Vale's native `readability` rule.

Vale's implementation (confirmed by reading Go source):
- Scope `summary` includes: paragraph text, list item text (`<li>`), blockquote text
- Scope `summary` excludes: headings (`<h1>`–`<h6>`), table cells/captions, code blocks (`<pre>`)
- Inline code spans: characters replaced with `*` (preserving token length, preventing vocabulary lookup)
- Formulas: standard academic algorithms from `jdkato/twine` — same as `textstat` implementations when given identical input

**Shared preprocessing function** — extracted to `rhetoric_lint/runners/_readability.py`, used by both the Vale `readability` rule type and the SP9 `readability.py` rule:

```python
def preprocess_for_readability(sections: list, raw_text: str) -> str:
    """
    Produce plain text for readability scoring, matching Vale's summary scope:
    
    Include:  Paragraph, ListItem, BlockQuote text
    Exclude:  headings, CodeFence, Table/TableRow/TableCell, HTMLBlock
    InlineCode: replace each character with '*' (matching Vale's twine preprocessing)
    
    Then apply lexi-style cleanup for sentence detection accuracy:
    - Convert colons to periods
    - Add period to list items not ending in punctuation
    - Remove list items < 4 words (prevents short enumerations skewing FK grade)
    - Collapse multiple spaces/newlines
    """
```

This function is the single source of truth. Vale `readability` rule and SP9 `readability.py` BOTH call it.

**`textstat` functions used per metric:**
```python
import textstat
VALE_METRIC_FN = {
    "Flesch-Kincaid":             textstat.flesch_kincaid_grade,
    "SMOG":                       textstat.smog_index,
    "Gunning Fog":                textstat.gunning_fog,
    "Coleman-Liau":               textstat.coleman_liau_index,
    "Automated Readability":      textstat.automated_readability_index,
    "Flesch Reading Ease":        textstat.flesch_reading_ease,   # for lexi composite
}
```

**Vale YAML `readability` rule → grade check:**
```yaml
extends: readability
metrics: [Flesch-Kincaid]
grade: 8                   # flag if FK grade > 8
```

Implementation: call `preprocess_for_readability()`, pass result to `textstat.flesch_kincaid_grade()`, compare against `grade:`.

### `sequence` + spaCy

spaCy `.tag_` returns Penn Treebank tags — same set Vale uses. Runner receives `context["nlp"]` (spaCy `Doc`), iterates sentence spans, matches token descriptors against `(token.text_lower, token.tag_)`. `skip: N` is a bounded gap: advance up to N tokens and retry match. If `context["nlp"]` is `None`, skip all `sequence` rules and log once per style.

### `metric` formula evaluation

Use `ast.literal_eval`-like safe evaluator (NOT `eval()`). Supported variables: `words`, `sentences`, `syllables`, `characters`, `long_words`, `paragraphs`. Supported operators: `+`, `-`, `*`, `/`, `**`. Condition: `"> N"`, `"< N"`, `">= N"`, `"<= N"`.

### Tests (additions to `test_vale_style_runner.py`)

- Occurrence: token appears 4 times, `max: 3` → finding; appears 3 times → no finding
- Occurrence: `min: 1`, token absent → finding
- Metric: FK formula evaluates correctly against known text
- Metric: malformed formula → graceful skip, warning logged
- **Readability preprocessing:** paragraph text included; heading text excluded; list item text included; table cell text excluded; inline code replaced with `*`; colon converted to period; list item < 4 words removed; list item gets period appended
- **Readability grade match:** fixture document produces FK grade within ±0.5 of textstat computed directly on equivalent manually-cleaned text (documents the expected small delta from Vale's `twine` syllable counter)
- Capitalization `$sentence`: sentence-initial word not capitalized → finding + fix
- Capitalization `exceptions`: excepted word in non-cap position → no finding
- Repetition: "the the" → finding + fix removes second "the"
- Repetition `alpha: true`: "1 1" → no finding (non-alpha)
- Consistency: both `colour` and `color` appear → finding; only one → no finding
- Conditional: `first` matches, `second` absent → finding; `first` absent → no finding
- Sequence: POS pattern `NN VBZ` matches "dog runs" (NN=dog, VBZ=runs) → finding
- Sequence: pattern with `skip: 2` matches token after 1 gap token → finding
- Sequence: `negate: true` on a tag — inverted match works
- Sequence: spaCy model `None` → no findings, no crash

### Files (SP4)

**Create:**
- `rhetoric_lint/runners/_readability.py`:
  - `preprocess_for_readability(sections: list, raw_text: str) -> str` — shared preprocessing for Vale-compatible scores
  - `VALE_METRIC_FN: dict[str, Callable]` — maps Vale metric names to `textstat` functions
  - `composite_score(text: str) -> float` — lexi-formula 0–100 composite; used by `rules/readability.py`

**Modify:**
- `rhetoric_lint/runners/vale_style.py` — extend `_apply_rule()` for all 8 new types; `readability` type calls `_readability.preprocess_for_readability()` then the appropriate `VALE_METRIC_FN`
- `tests/test_vale_style_runner.py` — test cases per type (see above)

### Verification
```bash
rhetoric-lint --style-dir style-sets/ --style Readability --format json tests/fixtures/test_generic.md
rhetoric-lint --style-dir style-sets/ --style write-good --format line tests/fixtures/test_generic.md
python -m pytest tests/test_vale_style_runner.py -v
```

---

## SP5 — markdownlint-cli2 Python Custom Rule Extension

**Goal:** Support loading Python custom rules via the markdownlint-cli2 config format. No shell-out. JS custom rules are not executed; `.py` paths in `customRules` are loaded as Python modules.

### Design

Parse `.markdownlint-cli2.jsonc` / `.markdownlint-cli2.yaml` / `.markdownlint-cli2.cjs` (JSON/YAML only — `.cjs`/`.mjs` are skipped with a warning since they require Node). 

From the config:
- `config:` → rule enable/disable, same as `.markdownlint.json`
- `customRules:` entries ending in `.py` → import as Python module, call `check(context) → list[dict]`
- `customRules:` entries ending in `.js`/`.cjs`/`.mjs` or npm package names → log once: `"JS custom rule '{name}' skipped — only Python (.py) custom rules are supported natively"`

**Python custom rule API** (analogous to markdownlint's JS API):
```python
# custom_rule.py
NAMES = ["my-rule"]
DESCRIPTION = "Flags something"
TAGS = ["custom"]

def check(context: dict, on_error) -> None:
    # context has same keys as rhetor-linter rule context
    # call on_error(line_number, detail=None, fix=None)
    for line_no, line in enumerate(context["lines"], 1):
        if "TODO" in line:
            on_error(line_no, detail="TODO comment found")
```

The runner calls `check(context, on_error)` where `on_error` accumulates findings into the standard finding shape.

### Files

**Modify:**
- `rhetoric_lint/runners/markdownlint.py` — add `_load_cli2_config()` and Python custom rule loader

### Tests (`tests/test_markdownlint_runner.py`, new section)

- `.markdownlint-cli2.yaml` with `customRules: [./my_rule.py]`: rule loaded, check() called, findings returned
- Custom rule calls `on_error(5)` → finding at line 5 with `check: "custom.my-rule"`
- Custom rule calls `on_error(3, fix={...})` → finding includes fix dict
- Custom rule raises exception: skip rule, emit `suggestion`-level meta-finding, no crash
- `.cjs` entry in customRules: warning logged, no crash, no JS executed
- npm package name in customRules: warning logged, no crash
- No cli2 config found: no-op, no crash
- `config: {MD013: false}` in cli2 config: MD013 disabled correctly

### Verification
```bash
# Create a Python custom rule, reference it from cli2 config
python -m pytest tests/test_markdownlint_runner.py -v -k cli2
python -m pytest tests/ -v
```

---

## SP6 — Migrate TrivializingLanguage to Vale YAML

**Goal:** The only existing Python rule that is a pure word-list existence check. Migrate to `style-sets/Rhetoric/`. Proves the migration path for future word-list rules.

### Why only this one

All other Python rules have spaCy, structural, or multi-section dependencies (confirmed by reading `rhetoric.py`, `cohesion.py`, `headings.py`, `completeness.py`). `TrivializingLanguage` is the sole exception.

### Files

**Create:**
- `style-sets/Rhetoric/TrivializingLanguage.yml`:
  ```yaml
  extends: existence
  message: "Trivializing language: '%s' implies this is easy. Consider removing."
  ignorecase: true
  level: suggestion
  scope: paragraph
  tokens: [simply, easily, obviously, 'of course', straightforward]
  ```
- `style-sets/Rhetoric/TrivializingLanguage-just.yml`:
  ```yaml
  extends: existence
  message: "Trivializing language: 'just' implies this is easy. Consider removing."
  ignorecase: true
  level: suggestion
  scope: sentence
  tokens: ['\bjust\b']
  exceptions:
    - just released
    - just updated
    - just published
    - just now
    - have just
    - has just
    - was just
  ```

**Modify:**
- `rhetoric_lint/rules/rhetoric.py` — remove `_trivializing_check()` and its call at the bottom of `check()`
- `rhetoric_lint/const.py` — remove `TRIVIALIZING_WORDS` if no longer referenced

### Tests

- YAML rule fires on `"This is simply done"` → finding with `check: "Rhetoric.TrivializingLanguage"`
- YAML rule does NOT fire on `"was just released"` (exception phrase)
- Old Python path no longer fires (no duplicate findings)
- All existing tests pass (regression)

### Verification
```bash
rhetoric-lint --style-dir style-sets/ --style Rhetoric tests/fixtures/test_generic.md | grep Trivializ
python -m pytest tests/ -v
```

---

## SP7 — Rhetoric YAML Additions

**Goal:** New word-list checks as Vale YAML, following the architecture principle from SP6.

### Files

**Create:**
- `style-sets/Rhetoric/Terminology.yml` (`substitution` — forbidden→preferred)
- `style-sets/Rhetoric/Inclusivity.yml` (`substitution` — with suggestions)
- `style-sets/Rhetoric/InclusivityFlag.yml` (`existence` — terms without clean replacements)

Content is standard (whitelist→allowlist, blacklist→denylist, ableist terms, etc.) — see prior plan iterations. No Python module.

### Tests

- `Terminology.yml`: `"whitelist"` → finding with suggestion `"allowlist"`
- `Inclusivity.yml`: `"guys"` in paragraph → finding with suggestion
- `InclusivityFlag.yml`: `"lame"` → finding; `"lame duck"` as a legitimate phrase → consider exception
- No double-firing with `Canonical/400-Enforce-inclusive-terms.yml` (distinct terms)

### Verification
```bash
rhetoric-lint --style-dir style-sets/ --style Rhetoric --format line tests/fixtures/test_generic.md
python -m pytest tests/ -v
```

---

## SP8 — NLP Rule Expansion

**Goal:** Five new Python rule modules closing Acrolinx-class gaps. All use `context["nlp"]`. Independent of SP2–SP7.

**Scoping note:** All SP8/SP9 rules operate on `context["sections"]` (AST-derived), so they inherit the AST's code-block exclusion automatically — paragraph text has already had `CodeFence` and `InlineCode` nodes stripped by the engine's preprocessing. No extra suppression logic needed unless a rule explicitly wants to include code.

### 1. `rules/syntactic_depth.py` → `Attention.SyntacticDepth`

- Walk spaCy dependency tree per sentence; compute max depth + count `ccomp`/`advcl`/`relcl` dependents.
- Flag if max depth > `SYNTACTIC_DEPTH_MAX` (default 6) OR nested clause count > `NESTED_CLAUSE_MAX` (default 2).
- **const.py:** `SYNTACTIC_DEPTH_MAX = 6`, `NESTED_CLAUSE_MAX = 2`

**Edge case tests:** Single-word sentence; sentence with coordination but no subordination (should not fire); sentence exactly at threshold (no finding); sentence one above threshold (finding).

### 2. `rules/nominalizations.py` → `Rhetoric.Nominalization`

- Find `token.pos_ == "NOUN"` with lemma ending in `-tion`, `-ment`, `-ance`, `-ity`, `-ness`.
- Prioritize `prep` + `pobj` pattern: `"the implementation of"` is highest signal.
- Root lookup: strip suffix, check if resulting form exists as a verb lemma in spaCy vocab. If vocab unavailable, use suffix heuristic only.
- Suppress: proper nouns, domain-specific terms in `exceptions` list (configurable), nouns in code spans.

**Edge case tests:** `"implementation"` in `"the implementation of the API"` → finding; `"implementation"` as standalone subject (`"Implementation is key"`) → lower confidence, suppress if no `prep` dep; `"nation"` (not a nominalization) → no finding (no known verb root); proper noun `"Washington"` → no finding.

### 3. `rules/metric_density.py` → `Attention.MetricDensity`

- Per sentence, count `token.like_num` OR `token.is_digit` OR regex `\d+(\.\d+)?(%|ms|MB|GB|px|rpm|x)`.
- Flag if numeric proportion > `METRIC_DENSITY_RATIO` (0.30) in sentences of ≥ 8 tokens.
- Sliding window (10 tokens): flag if > `METRIC_DENSITY_WINDOW_MAX` (3) are numeric.
- Suppress: sentences inside code fences; table rows.
- **const.py:** `METRIC_DENSITY_RATIO = 0.30`, `METRIC_DENSITY_WINDOW = 10`, `METRIC_DENSITY_WINDOW_MAX = 3`

**Edge case tests:** Sentence with 1 number in 10 tokens → no finding; sentence with 4 numbers in 8 tokens → finding; "3.14 is π" (short) → below minimum length, no finding; table row → no finding; code fence → no finding.

### 4. `rules/tone.py` → `Rhetoric.ToneImbalance`

- Classify tokens into `AUTHORITATIVE_MODALS`, `EMPATHETIC_SOFTENERS`, `NEGATIVE_FRAMING` (defined in `const.py`).
- Document-level: compute ratio of each bucket.
- Flag (line 1) if authoritative ratio > `TONE_AUTHORITATIVE_MAX` (0.15) AND genre ∈ {howto, tutorial}; OR negative framing > `TONE_NEGATIVE_MAX` (0.20) in any genre.
- One finding per document — do not spam per-sentence.
- **const.py:** lexicons + thresholds.

**Edge case tests:** All-authoritative howto → finding; authoritative tutorial below threshold → no finding; negative framing in adr → finding; empty doc → no finding; genre `None` → no finding.

### 5. `rules/terminology.py` → `Terminology.PreferredForm`

Python layer only — case enforcement for proper nouns that Vale substitution can't handle (preserves `swap:` from YAML for fuzzy matching, Python for exact case).

- Load `terminology.yml` `required_form:` section.
- Use spaCy `PhraseMatcher` with `LOWER` to find case-insensitive matches.
- Compare span text to required form; flag mismatches.
- Suppress: terms inside code spans/fences; terms in URLs.
- **Config:** `TERMINOLOGY_FILE` from const (or `--terminology-file` flag from SP1).

**Edge case tests:** `"github"` when required form is `"GitHub"` → finding; `"GitHub"` correct case → no finding; `"github.com"` (URL) → no finding; term in code span `` `github` `` → no finding; empty `required_form:` list → no findings.

### 6. `rules/symmetry.py` → `Symmetry.TabVariantBalance`

Content tabs (`=== "Tab"` blocks) rewritten to blockquotes by the engine preprocessor should have symmetric ordered list item counts across variants.

- Detect tab boundaries by scanning preprocessed text for the pymdownx rewrite pattern (blockquote with bold tab title, produced by the `///` rewriter in commit 8e5de0c).
- Count ordered list items (`nodes` with `list_type == "ol"`) per tab variant.
- If `max(step_count) - min(step_count) > TAB_VARIANT_STEP_TOLERANCE` across ≥ 2 variants → `warning`.
- Skip sections where all tab variants contain only code blocks (reference-style tabs).
- `GENRES = frozenset({"howto", "tutorial", "concept", "explanation", "reference", "general"})`

**False positive controls:**

| Scenario | Expected | Suppression |
|---|---|---|
| Single tab | No finding | `len(tab_variants) < 2` guard |
| Two tabs, code-only | No finding | Skip if max OL item count == 0 |
| Two tabs, 3 vs 4 steps | No finding | `max - min <= TAB_VARIANT_STEP_TOLERANCE` |
| Tabs in reference section | No finding | `topic_type == "reference"` skip |
| Tabs rewritten but no step content | No finding | Zero step count → skip |

**Tests (in `tests/test_nlp_rules_expansion.py`):**
- Two tabs, same step count → no finding
- Two tabs, 4 steps vs 2 steps → finding
- Two tabs, 3 steps vs 4 steps → no finding (within tolerance)
- Single tab → no finding
- Two tabs, code-only → no finding

### Files

**Create:**
- `rhetoric_lint/rules/syntactic_depth.py`
- `rhetoric_lint/rules/nominalizations.py`
- `rhetoric_lint/rules/metric_density.py`
- `rhetoric_lint/rules/tone.py`
- `rhetoric_lint/rules/terminology.py`
- `tests/test_nlp_rules_expansion.py`

**Modify:**
- `rhetoric_lint/rules/symmetry.py` — add `_tab_variant_balance_check(context)`, called from `check()`
- `rhetoric_lint/const.py` — all new thresholds and lexicons listed above, plus `TAB_VARIANT_STEP_TOLERANCE = 1`

### Verification
```bash
python -m pytest tests/test_nlp_rules_expansion.py -v
python -m pytest tests/ -v
```

---

## SP9 — ProsePartner Gaps

**Goal:** Three new Python rules + one Vale YAML rule closing gaps identified in ProsePartner comparison analysis. All depend on SP8's infrastructure patterns. Independent of SP2–SP7.

**ReadabilityGrade is implemented as Vale YAML** (`style-sets/Rhetoric/ReadabilityGrade.yml`, `extends: readability`, `metric: Lexi`) rather than a Python rule. The Lexi composite score is already implemented in `_readability.py` and the `readability` rule type is already supported by SP4. The YAML approach is preferable: threshold is user-configurable, genre gating is via the YAML `genre:` field, and no Python module is needed.

### 1. `rules/passive_voice.py` → `Rhetoric.PassiveVoiceActorGap`

Not duplicate of write-good's `Passive.yml` (which flags all passive). This flags **passive constructions without a by-agent** — degrading step clarity in instruction-heavy docs.

- Detect passive: `token.dep_ in ("nsubjpass", "auxpass")` OR `token.dep_ == "aux"` AND POS tag `VBN`/`VBD` following `be`-form.
- Flag only when no `by`-agent (`prep` with `pobj` where prep lemma == "by") exists in the same clause.
- Genre gate: higher severity in howto/tutorial genres (`"error"`); `"suggestion"` elsewhere.
- Suppress: passive constructions where the actor is genuinely unknown/irrelevant (e.g., "it was observed that" in concept/explanation genres).

**Edge case tests:**
- `"The file is created."` → finding (no actor)
- `"The file is created by the installer."` → no finding (actor present)
- `"Errors were logged."` in postmortem → finding
- `"It was shown that..."` in concept/explanation genre → suggestion (not error)
- Active sentence `"The installer creates the file."` → no finding
- Sentence with no verb → no finding

**const.py:** `PASSIVE_ACTOR_GAP_SEVERITY_INSTRUCTIONAL = "warning"`, `PASSIVE_ACTOR_GAP_SEVERITY_DEFAULT = "suggestion"`

### 2. `rules/sentence_rhythm.py` → `Attention.SentenceRhythm`

LongSentence and WallOfText exist but don't track pacing. CV of sentence lengths within a section is a first-class Tier 1 signal.

- Per section, compute sentence token counts (spaCy sentences already available).
- Compute coefficient of variation: `cv = std / mean` of token counts.
- Flag the section if `cv > SENTENCE_RHYTHM_CV_MAX` (default 0.8) AND section has ≥ 4 sentences.
- Also flag: max_tokens / min_tokens > `SENTENCE_RHYTHM_SPIKE_RATIO` (default 4.0) within a section.
- One finding per section (at section heading line or first paragraph line if no heading).
- Include min/max/mean/CV in message for actionability.

**Edge case tests:**
- All sentences same length: CV = 0 → no finding
- Monotone section (all 8–10 tokens): CV low → no finding
- 45-token opener + three 3-token fragments: spike ratio fires
- Section with exactly 3 sentences: below minimum, no finding
- Section with spaCy `None`: no crash, no finding

**const.py:** `SENTENCE_RHYTHM_CV_MAX = 0.8`, `SENTENCE_RHYTHM_SPIKE_RATIO = 4.0`, `SENTENCE_RHYTHM_MIN_SENTENCES = 4`

### 3. `style-sets/Rhetoric/ReadabilityGrade.yml` → `Rhetoric.ReadabilityGrade`

**Supersedes the Python rule approach.** Implemented as a Vale YAML rule using the `extends: readability` type (SP4) with `metric: Lexi`. The Lexi composite score is already in `_readability.py`; no new Python module needed. Threshold is user-configurable via YAML override in `.rhetoric-lint.yaml`.

```yaml
extends: readability
message: "Readability score is low (%s) — consider simplifying sentences or vocabulary."
level: warning
scope: paragraph
metric: Lexi
max: 65
```

Score 0–100 (100 = most readable). Paragraphs scoring below `max` fire. Genre gating via the `genre:` field if needed.

**Tests** (in `test_rhetoric_yaml.py`):
- Low-readability paragraph → `Rhetoric.ReadabilityGrade` fires
- High-readability paragraph → no finding
- `textstat` absent → no crash (runner skips metric silently)

### 4. `rules/unsupported_claim.py` → `Completeness.UnsupportedClaim`

Detect assertion phrases not followed within 2 sentences by evidence. Most useful in concept/explanation sections.

**Assertion signals** (regex, sentence-initial or clause-initial):
```
this means, therefore, thus, this demonstrates, this shows,
which shows, which means, which demonstrates, this confirms,
this proves, this indicates, this suggests, this implies,
as a result, consequently, it follows that
```

**Evidence signals** (within the next 2 sentences):
- Code fence (```` ``` ```` or `    ` indent) within the section
- Evidence phrases: `for example`, `for instance`, `see`, `as shown in`, `as illustrated`, `figure`, `table`, `listing`
- Numbered list following the paragraph
- Citation-like: `[N]`, `(source)`, `(see`, `\d{4})`

**Logic:**
- Per paragraph in concept/explanation sections, scan sentences for assertion signals.
- If found, look ahead 2 sentences in the same paragraph + the immediately following block.
- If no evidence signal found → finding at the assertion sentence.
- Genre gate: only fires in `concept`, `explanation` genres.

**Edge case tests:**
- `"Therefore, X. For example, Y."` → no finding (evidence present)
- `"Therefore, X. Y. Z."` (no evidence in 2 sentences) → finding
- `"This means that X."` followed immediately by a fenced code block → no finding
- Assertion in ADR decision section → no finding (genre gate)
- Assertion in howto step → no finding (genre gate)
- Multiple assertion phrases in one paragraph: one finding per unaccompanied assertion (cap at 2 per paragraph to avoid noise)
- Short paragraph (1 sentence only): no finding (insufficient context to verify claim)

**const.py:** `UNSUPPORTED_CLAIM_LOOKHEAD_SENTENCES = 2`, `UNSUPPORTED_CLAIM_MAX_PER_PARA = 2`

### Files

**Create:**
- `rhetoric_lint/rules/passive_voice.py`
- `rhetoric_lint/rules/sentence_rhythm.py`
- `rhetoric_lint/rules/unsupported_claim.py`
- `style-sets/Rhetoric/ReadabilityGrade.yml` — `extends: readability`, `metric: Lexi`, `max: 65`, `level: warning`, `scope: paragraph`
- `tests/test_prose_partner_gaps.py`

**Modify:**
- `rhetoric_lint/const.py` — all new thresholds listed above
- `pyproject.toml` / `Pipfile` — add `textstat` dependency (pure Python, no ML, no GPU)

**Note:** `_readability.py` is created in SP4 and consumed here. SP9 depends on SP4 being complete.

### Verification
```bash
python -m pytest tests/test_prose_partner_gaps.py -v
python -m pytest tests/ -v
rhetoric-lint --format json tests/fixtures/test_generic.md \
  | python -c "import json,sys; [print(m['Check']) for f in json.load(sys.stdin) for m in f['Matches'] if any(k in m['Check'] for k in ('Passive','Rhythm','Readability','Claim'))]"
```

---

## SP_SPELL — Vale `spelling` Rule Type

**Goal:** Implement `extends: spelling` in `vale_style.py` (created by SP2) using `spylls` as an optional pure-Python Hunspell backend. Completes Vale rule type coverage. Depends on SP2.

### Dependency addition

**`pyproject.toml`**: `[project.optional-dependencies]` → `spell = ["spylls"]`
**`Pipfile`**: add `spylls` as optional in `[packages]`

Install: `pip install rhetoric-lint[spell]`

### Vale `spelling` YAML fields to support

| Field | Meaning |
|---|---|
| `extends: spelling` | rule type selector |
| `dicpath` | dir containing `.aff`/`.dic` files, relative to the style dir |
| `dictionaries` | list of dict names without extension (e.g., `en_US`) |
| `custom: true` | use only named dicts, no bundled base dict |
| `append: false` | don't merge project `vocabularies/` accept.txt |
| `ignore` | path(s) to plain-text word lists (one word per line) |
| `action: {name: suggest}` | populate `suggestions` list in finding |
| `message` | format string with `%s` for the flagged word |
| `level` | error/warning/suggestion |

### Implementation in `rhetoric_lint/runners/vale_style.py`

```python
try:
    from spylls.hunspell import Dictionary as HunspellDict
    _SPYLLS_AVAILABLE = True
except ImportError:
    _SPYLLS_AVAILABLE = False

_spell_cache: dict[tuple[str, str], "HunspellDict"] = {}
```

Add `_check_spelling(self, rule, scope_texts, context)` method; dispatch `"spelling"` case in `_apply_rule()`.

Key logic:
1. Graceful degradation: if `_SPYLLS_AVAILABLE` is False, emit one `suggestion`-level meta-finding per file instructing the user to install `rhetoric-lint[spell]`.
2. Resolve `.aff`/`.dic` paths: `dicpath` relative to rule YAML dir; fallback = rule YAML dir.
3. Load/cache: `_spell_cache[(resolved_dicpath, dict_name)] = HunspellDict(aff_path)`.
4. Build ignore set: `rule["ignore"]` word-list files + `accept.txt` if `append != False`.
5. Build filter patterns: `[re.compile(p) for p in rule.get("filters", [])]`.
6. Per `(text, line_offset)` in scope_texts (AST-scoped, already code-free): tokenize with `re.findall(r"[a-zA-Z''\-]+", text)`; for each word skip if in ignore set, matches filter, or any dict lookup passes; emit finding; if `action == suggest`, populate `suggestions = dict.suggest(word)[:3]`.

AST-aware scoping (inherited from SP2) automatically excludes code fences, inline code, URLs, link hrefs.

### Files

**Modify:**
- `rhetoric_lint/runners/vale_style.py` — add `_SPYLLS_AVAILABLE` guard, `_spell_cache`, `_check_spelling()`, dispatch case
- `pyproject.toml` — add `spell` optional dep group
- `Pipfile` — add optional `spylls`

### Tests (add to `tests/test_vale_style_runner.py`)

- Correctly spelled word → no finding
- Misspelled word → finding with correct check name, line, column
- Word in `ignore` list → no finding
- Word matched by `filters` regex → no finding
- `action: {name: suggest}` → finding includes `suggestions` key, ≤ 3 entries
- `en-GB` dict: `"colour"` → no finding; `"color"` → finding
- `custom: true` + unknown word → finding (no fallback)
- `vocab: true` accept.txt word → suppressed (shared SP2 vocab logic)
- `spylls` absent (mock `_SPYLLS_AVAILABLE = False`) → one meta-finding per file, no crash
- `.aff`/`.dic` not found → warning logged, rule skipped, no crash
- Word in inline code span in prose → not checked (AST scope exclusion)

### Verification
```bash
pip install spylls
rhetoric-lint --style-dir style-sets/ --style Spelling --format line tests/fixtures/test_generic.md
python -m pytest tests/test_vale_style_runner.py -v -k spelling
python -m pytest tests/ -v
```

---

## SP_CI — Pre-commit + GitHub Actions

**Goal:** Wire the stable CLI into pre-commit and GitHub Actions. No Python source changes. Depends on SP1 (CLI stable).

### Files to create

**`.pre-commit-hooks.yaml`** (repo root):
```yaml
- id: rhetoric-lint
  name: rhetoric-lint
  language: python
  entry: rhetoric-lint
  types: [markdown]
  pass_filenames: true
  additional_dependencies:
    - "spacy[en_core_web_sm]"
```

**`.github/workflows/rhetoric-lint.yml`**:
```yaml
name: rhetoric-lint
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Cache spaCy model
        uses: actions/cache@v4
        with:
          path: ~/.local/lib/python3.12/site-packages/en_core_web_sm
          key: spacy-en-core-web-sm-${{ runner.os }}
      - run: pip install rhetoric-lint
      - run: python -m spacy download en_core_web_sm
      - run: rhetoric-lint --min-severity warning docs/
```

**`docs/ci-integration.md`** — guide covering pre-commit setup, GitHub Actions, exit codes (0/1/2), and `--ignore` pattern usage. Keep under 100 lines.

### Verification
```bash
python -c "import yaml; yaml.safe_load(open('.pre-commit-hooks.yaml'))"
rhetoric-lint --min-severity error tests/fixtures/corpus/technical/
```

---

## SP_CONTRAST — `Rhetoric.UnresolvedContrast`

**Goal:** Detect paragraphs using contrast signal words without a following resolution signal. Independent of all other SPs.

**Constraint:** Full RST analysis is out of scope (see global constraint 10). This rule covers the Contrast discourse relation only.

### Implementation in `rhetoric_lint/rules/rhetoric.py`

Add `_unresolved_contrast_check(context)` alongside existing helpers; call from `check()`.

**Contrast signals** (sentence-initial or clause-initial; position < 30% of sentence length):
```python
CONTRAST_SIGNALS = [
    "however", "but", "although", "nevertheless", "on the other hand",
    "on the contrary", "in contrast", "by contrast", "even so", "yet",
    "despite", "nonetheless", "that said", "while", "whereas",
    "notwithstanding",
]
```

Note: overlaps with `const.SIGNPOSTS["adversative"]` but has different membership. Use a separate `CONTRAST_SIGNALS` const, not SIGNPOSTS.

**Resolution signals** (within rest of contrast sentence + next sentence):
```python
CONTRAST_RESOLUTION_SIGNALS = [
    "therefore", "thus", "so", "as a result", "consequently", "this means",
    "which means", "instead", "rather", "still", "ultimately", "in practice",
    "in fact", "the key point", "the solution", "to address this",
]
```

**Logic:**
1. Per paragraph using `paragraph["sentences"]`.
2. Skip if `len(sentences) < CONTRAST_MIN_SENTENCES` (default 3).
3. For each sentence with contrast signal at position < 30% of sentence length: check rest of sentence + next sentence for resolution signal; no resolution → emit finding at contrast sentence's line.
4. Cap at `CONTRAST_UNRESOLVED_MAX_PER_PARA` (default 2) per paragraph.
5. Genre gate: fires only in `concept`, `explanation`, `general`. Skip `howto`, `tutorial`, `adr`, `reference`, `postmortem`.

### `const.py` additions
```python
CONTRAST_SIGNALS = [...]
CONTRAST_RESOLUTION_SIGNALS = [...]
CONTRAST_UNRESOLVED_MAX_PER_PARA = 2
CONTRAST_MIN_SENTENCES = 3
```

### Rule registration
- `RULE_SEVERITY_LEVELS["Rhetoric.UnresolvedContrast"] = "suggestion"`
- `RULE_DESCRIPTIONS["Rhetoric.UnresolvedContrast"] = "Contrast signal without resolution"`
- Add row to `README.md` rules table.

### Files

**Modify:**
- `rhetoric_lint/rules/rhetoric.py` — add `_unresolved_contrast_check()`, call from `check()`
- `rhetoric_lint/const.py` — add constants above
- `README.md` — add rules table row

### Tests (add to `tests/test_rhetoric_new_rules.py`)

- "However, X. Therefore, Y. Z." (≥3 sentences, resolved) → no finding
- "However, X. Y. Z." (≥3 sentences, unresolved) → finding
- "But X." (< 3 sentences) → no finding (min-sentence guard)
- Contrast signal mid-sentence (position > 30%) → no finding
- Genre `howto` → no finding (genre gate)
- Genre `concept` → finding
- **Precision corpus**: zero findings on `tests/fixtures/corpus/technical/`

### Verification
```bash
python -m pytest tests/test_rhetoric_new_rules.py -v -k contrast
python -m pytest tests/ -v
rhetoric-lint --rules Rhetoric.UnresolvedContrast --format text tests/fixtures/test_generic.md
```

---

## SP10 — DependencyReveal *(blocked on CrossFileContext)*

**Goal:** Flag tool/concept references in a file that are used before they are defined anywhere in the scanned file set.

**Blocked on:** `CrossFileContext` (delivered in SP1). Do not implement until SP1 is complete and `context["cross_file"]` is populated.

**Design:**
- `CrossFileContext.term_first_seen` maps each term to the file and section heading where it first appears.
- Rule reads `context["cross_file"].term_first_seen`; for each proper noun or key noun phrase in the current file, flags if the current file appears earlier in the scan order than the file where the term is first defined.
- Genre gate: fires in all genres except `reference`.

**False positive controls:**

| Scenario | Expected | Suppression |
|---|---|---|
| Term defined in glossary file, used everywhere | No finding | Glossary-origin terms exempt |
| Term first seen in 1-sentence mention (not a definition) | No finding | Definition requires ≥ 2 sentences containing the term |
| ADR + tutorial both explain "JWT" | No finding | Genre-pair exemption for `adr` + `tutorial` |

---

## SP11 — ConceptReintroductionPenalty *(blocked on CrossFileContext)*

**Goal:** Flag sections in different files that re-explain the same concept (Jaccard ≥ 0.60 on content lemma sets).

**Blocked on:** `CrossFileContext` (delivered in SP1).

**Design:**
- Uses `set_overlap_metrics()` from `rhetoric_lint/overlap.py` (already exported) with a 0.60 Jaccard threshold on section lemma sets — same algorithmic approach as the composable duplicate detection in `overlap.py`.
- Two sections in different files with Jaccard ≥ 0.60 on content lemma sets qualify as redundant reintroductions.
- `CrossFileContext.concept_definitions` maps term → list of files.

**False positive controls:**

| Scenario | Expected | Suppression |
|---|---|---|
| Same concept at different abstraction levels | No finding | Require Jaccard ≥ 0.60 on **content** lemma sets, not just term co-occurrence |
| ADR + tutorial both explain the same term | No finding | Genre-pair exemption: `adr` + `tutorial` pairings don't trigger |

---

## Roadmap design notes *(implementation TBD)*

Design decisions captured here for when these features are scheduled.

### `CODE_LANGUAGE_ALIASES` (for Code-Prose Alignment + Interface Surface Coverage)

Add to `const.py`:
```python
CODE_LANGUAGE_ALIASES = {
    "ts": "typescript", "py": "python", "golang": "go",
    "js": "javascript", "c++": "cpp", "rb": "ruby",
}
```
Normalize fenced code block language tags before extracting tool/flag names for prose matching.

### Procedural State Machine

Detect nested ordered lists (ordered list item whose `nodes` contain a child ordered list) as sub-procedures. Validate inner lists independently for imperative form using the same `HowTo.NonImperativeStep` logic. The `nodes` list in each paragraph already carries `list_type` metadata — no new parsing needed.

### Remaining roadmap features (prioritized)

- Cognitive Jump Distance (paragraph-level TF-IDF centroid drop)
- Intent-Artifact Closure
- Narrative Compression Ratio
- Taxonomy Alignment (H2/H3 vs controlled vocabulary)
- Code-Prose Alignment (uses `CODE_LANGUAGE_ALIASES`)
- Interface Surface Coverage (CLI flags in code blocks → prose explanation)
- Procedural State Machine (nested ordered list sub-procedure validation)
- Retrieval Anchor Density

---

## SP12: JTBD Coverage Integration

**Status**: Planned — blocked on jtbd-tool Tier 3 (stable API at `localhost:8080`)  
**Depends on**: SP1 (`CrossFileContext`); jtbd-tool producing a `jtbd-manifest.json`

### New rule: `Coverage.MissingJobCoverage`

File: `rhetoric_lint/rules/jtbd_coverage.py`

Rule fires a `warning` finding for each job in the manifest where `coverage == "missing"` (i.e., no doc paragraph meets the Jaccard threshold). This connects jtbd-tool's scan output to rhetor-linter's per-file audit loop.

#### Engine integration

- New `const.py` additions:
  ```python
  JTBD_MANIFEST_PATH: str = ""          # path to jtbd-manifest.json; empty = rule disabled
  JTBD_COVERAGE_JACCARD_MIN: float = 0.30
  ```
- New CLI flag: `--jtbd-manifest <path>` → sets `const.JTBD_MANIFEST_PATH`
- Engine `main.py`: if `JTBD_MANIFEST_PATH` is set, load manifest JSON into `context["jtbd_manifest"]`

#### Rule logic

```python
def check(context: dict) -> list[dict]:
    manifest_path = context["const"].JTBD_MANIFEST_PATH
    if not manifest_path:
        return []
    manifest = context.get("jtbd_manifest")
    if not manifest:
        return []

    findings = []
    for job in manifest.get("jobs", []):
        if job.get("coverage") != "missing":
            continue

        # Compute Jaccard against all paragraphs in this file
        job_tokens = _tokenize(job["statement_text"])
        best = 0.0
        for section in context["sections"]:
            for para in section.get("paragraphs", []):
                score = set_overlap_metrics(job_tokens, _tokenize(para["text"]))["jaccard"]
                best = max(best, score)

        threshold = context["const"].JTBD_COVERAGE_JACCARD_MIN
        if best < threshold:
            findings.append({
                "path":    context["path"],
                "line":    1,
                "column":  0,
                "check":   "Coverage.MissingJobCoverage",
                "severity": "warning",
                "message": (
                    f"Job '{job['statement_text']}' ({job['job_map_step']}) "
                    f"has no documentation coverage (best Jaccard: {best:.3f} < {threshold}). "
                    f"SWEBOK ref: {job['swebok_ref']}"
                ),
            })
    return findings
```

`_tokenize` mirrors `auditor.py` in jtbd-tool: lowercase, `\b[a-z]{2,}\b`, minus stopwords. Do **not** copy — import from a shared util module or reimplement identically (the two tools must not import each other).

Use `overlap.py::set_overlap_metrics()` for the Jaccard call — never reimplement Jaccard in rule files (hard constraint from CONTRIBUTING.md).

#### `const.py` severity/description entries

```python
RULE_SEVERITY_LEVELS["Coverage.MissingJobCoverage"] = "warning"
RULE_DESCRIPTIONS["Coverage.MissingJobCoverage"] = (
    "A JTBD job detected by jtbd-tool has no documentation coverage in this file."
)
```

#### Tests: `tests/test_jtbd_coverage.py`

- **Must-fire**: synthetic manifest with one `coverage=missing` job; doc fixture with no matching text → assert finding emitted.
- **Must-not-fire (coverage present)**: same manifest; doc fixture whose paragraph contains matching tokens (Jaccard ≥ 0.30) → assert no finding.
- **Must-not-fire (no manifest)**: `JTBD_MANIFEST_PATH = ""` → assert no finding.
- **Must-not-fire (corpus)**: full engine against `tests/fixtures/corpus/technical/` with real manifest produced by `jtbd-tool scan .` → zero findings (real docs are presumed to cover their own jobs).

#### Manifest loading

Load once per engine run, not per file. In `engine.py`:

```python
if const.JTBD_MANIFEST_PATH:
    import json
    with open(const.JTBD_MANIFEST_PATH) as f:
        context["jtbd_manifest"] = json.load(f)
```

#### Exchange format contract (jtbd-tool ↔ rhetor-linter)

The only manifest fields rhetor-linter reads:
- `jobs[].id`
- `jobs[].statement_text`
- `jobs[].job_map_step`
- `jobs[].swebok_ref`
- `jobs[].coverage`  (`"missing"` | `"partial"` | `"covered"` | `"unknown"`)

Schema version is in `manifest.version`. If the file is missing or invalid JSON, the rule returns `[]` silently — never raises.

---

## Infrastructure Gates

Gates are triggered by conditions, not dates. No new git repos are created until Gate 2 fires.

### Gate 1 — Scaffold (trigger: Phase 0 complete)

Triggered when a component's Phase 0 is complete enough to start writing code in its target location. For each component the plan defines: what directories to create, what CLAUDE.md to write, what goes in pyproject.toml / package.json skeleton.

This is just `mkdir` + stub files inside the existing repo — no new git repos yet.

**Deliverables (✅ complete 2026-06-07):**
- `rhetoric_lint/server/` — stub `__init__.py` + `CLAUDE.md` (import constraint documented)
- `rhetoric_lint/score.py` — `ScoreResult` dataclass + `score_file()` boundary function (server calls this only)
- `rhetoric_lint/metadata.py` — `normalise_topic_type()`, `normalise_owner()`, `normalise_frontmatter()` skeletons
- `const.SCORE_MIN_WORDS = 150` — F4 scoring floor

**Remaining Phase 0 items (open):**
- F3: SP12 emission rework (corpus-level via CrossFileContext) — blocked on jtbd-tool Tier 3
- F6: SP12 tokenizer contract test — blocked on jtbd-tool Tier 3
- F8: Document polling staleness as known limitation (CONTRIBUTING.md note)
- F9: `normalise_owner()` wired into engine F2 path (metadata.py exists; engine call not yet added)
- F10: Server import constraint noted in CONTRIBUTING.md

### Gate 2 — Repo creation (trigger: graduation condition)

Graduation condition — any one of:
- Server needs a different deploy cadence or version than the linter
- A second analysis backend is added
- A dedicated contributor works server-only

Until the condition fires, `rhetoric_lint/server/` stays inside the linter repo. When it fires, the plan specifies a `git subtree split` or extract sequence.

**Other Gate 2 repo creations:**
- `jtbd-tool` repo: create when `jtbd-tool scan` returns valid manifest JSON (near-term trigger)
- `backstage-shela-plugin` repo: create at Phase 4 start — TypeScript, separate cadence from day one

### Gate 3 — Org creation (trigger: ≥2 repos ready for public release)

Triggered by: two or more repos ready for public release under a shared brand. This is the last step, not the first.

**Chosen org name: Chancery Labs (`chancery-labs`)**

Component names under the org:

| Component | Name | Role |
|---|---|---|
| Org | `chancery-labs` | Document authentication and transmission — medieval chancery metaphor |
| Linter | `shela` | she'ela — the question/inquiry put to the text |
| Server | `syla` | Transmits the findings |
| Auditor | `laxa` | From halaxa — the normative path |

Action at Gate 3: create GitHub org, transfer repos, update CI config and install paths in docs.
