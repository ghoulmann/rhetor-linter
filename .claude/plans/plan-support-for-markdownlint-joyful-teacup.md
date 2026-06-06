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
| SP1 | Runner infrastructure + fix framework + CrossFileContext stub | — |
| SP2 | Vale core types (existence + substitution) | SP1 |
| SP3 | markdownlint native MD rules | SP1 |
| SP4 | Vale extended types (occurrence … sequence/NLP) | SP2 |
| SP5 | markdownlint-cli2 Python custom rule extension | SP3 |
| SP6 | Migrate TrivializingLanguage to Vale YAML | SP2 |
| SP7 | Rhetoric YAML additions (Terminology, Inclusivity) | SP2 |
| SP8 | NLP rule expansion (5 spaCy rules + TabVariantBalance) | SP1 |
| SP9 | ProsePartner gaps (4 rules) | SP8, SP4 |
| SP_SPELL | Vale spelling rule type (spylls optional dep) | SP2 |
| SP_CI | Pre-commit + GitHub Actions integration | SP1 |
| SP_CONTRAST | Rhetoric.UnresolvedContrast | — |
| SP10 | DependencyReveal (multi-file) | CrossFileContext (SP1) |
| SP11 | ConceptReintroductionPenalty (multi-file) | CrossFileContext (SP1) |

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
  SP9: ProsePartner gaps — PassiveVoiceActorGap, SentenceRhythm,
       ReadabilityGrade, UnsupportedClaim (needs SP4 + SP8)
  SP7: Rhetoric YAML additions — Terminology.yml, Inclusivity.yml

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

Individual rule `genre:` takes precedence over directory-level meta. Genre values match the engine's output: `howto`, `tutorial`, `concept`, `explanation`, `reference`, `faq`, `adr`, `postmortem`, `technical`, `general`. Absent `genre:` field = applies to all genres.

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
- `genre: howto`: fires on howto document, suppressed on technical document
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

### Files

**Create:**
- `rhetoric_lint/rules/syntactic_depth.py`
- `rhetoric_lint/rules/nominalizations.py`
- `rhetoric_lint/rules/metric_density.py`
- `rhetoric_lint/rules/tone.py`
- `rhetoric_lint/rules/terminology.py`
- `tests/test_nlp_rules_expansion.py`

**Modify:**
- `rhetoric_lint/const.py` — all new thresholds and lexicons listed above

### Verification
```bash
python -m pytest tests/test_nlp_rules_expansion.py -v
python -m pytest tests/ -v
```

---

## SP9 — ProsePartner Gaps

**Goal:** Four new Python rules closing gaps identified in ProsePartner comparison analysis. All depend on SP8's infrastructure patterns. Independent of SP2–SP7.

### 1. `rules/passive_voice.py` → `Rhetoric.PassiveVoiceActorGap`

Not duplicate of write-good's `Passive.yml` (which flags all passive). This flags **passive constructions without a by-agent** — degrading step clarity in instruction-heavy docs.

- Detect passive: `token.dep_ in ("nsubjpass", "auxpass")` OR `token.dep_ == "aux"` AND POS tag `VBN`/`VBD` following `be`-form.
- Flag only when no `by`-agent (`prep` with `pobj` where prep lemma == "by") exists in the same clause.
- Genre gate: higher severity in howto/tutorial genres (`"error"`); `"suggestion"` elsewhere.
- Suppress: passive constructions where the actor is genuinely unknown/irrelevant (e.g., "it was observed that" in scientific/technical genres).

**Edge case tests:**
- `"The file is created."` → finding (no actor)
- `"The file is created by the installer."` → no finding (actor present)
- `"Errors were logged."` in postmortem → finding
- `"It was shown that..."` in technical genre → suggestion (not error)
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

### 3. `rules/readability.py` → `Attention.ReadabilityGrade`

Section-level readability with genre awareness, using the **lexi composite formula** (Rebilly) for the 0–100 score and Vale-compatible individual grade metrics for thresholds.

**Uses `rhetoric_lint/runners/_readability.py::preprocess_for_readability()`** — the same preprocessing shared with the Vale `readability` rule type. This guarantees consistent scores across both rule systems for the same text.

#### Composite formula (from lexi)

```python
METRIC_RANGES = {
    "flesch_reading_ease":          {"min": 0,    "max": 100},   # higher = easier
    "gunning_fog":                  {"min": 19,   "max": 6},     # lower = easier (inverted)
    "automated_readability_index":  {"min": 22,   "max": 6},     # lower = easier (inverted)
    "dale_chall_readability_score": {"min": 11,   "max": 4.9},   # lower = easier (inverted)
    "coleman_liau_index":           {"min": 19,   "max": 6},     # lower = easier (inverted)
}

WEIGHTS = {
    "flesch_reading_ease":          0.1653977378,
    "gunning_fog":                  0.2228367277,
    "automated_readability_index":  0.2325290236,
    "dale_chall_readability_score": 0.1960641698,
    "coleman_liau_index":           0.1831723411,
}

def _composite(text: str) -> float:
    raw = {
        "flesch_reading_ease":          textstat.flesch_reading_ease(text),
        "gunning_fog":                  textstat.gunning_fog(text),
        "automated_readability_index":  textstat.automated_readability_index(text),
        "dale_chall_readability_score": textstat.dale_chall_readability_score(text),
        "coleman_liau_index":           textstat.coleman_liau_index(text) or 0,
    }
    # Cap each score to its range
    capped = {k: _cap(v, METRIC_RANGES[k]["min"], METRIC_RANGES[k]["max"]) for k, v in raw.items()}
    # Normalize 0→1 (ranges may be inverted — capBetween handles sign)
    normed = {k: (capped[k] - mn) / (mx - mn)
              for k, (mn, mx) in {k: (min(r["min"],r["max"]), max(r["min"],r["max"]))
                                   for k,r in METRIC_RANGES.items()}.items()}
    return 100 * sum(normed[k] * WEIGHTS[k] for k in WEIGHTS)
```

Composite 0–100: higher = more readable (same direction as Flesch Reading Ease).

#### Genre-aware thresholds (FK Grade for threshold; composite reported in message)

| Genre | FK Grade threshold | Severity |
|---|---|---|
| `howto`, `tutorial` | > `READABILITY_TUTORIAL_FK_MAX` (12) | warning |
| `technical`, `general` | > `READABILITY_TECHNICAL_FK_MAX` (16) | suggestion |
| `concept`, `explanation` | > `READABILITY_TECHNICAL_FK_MAX` (16) | suggestion |
| `adr`, `postmortem` | exempt | — |
| `reference` | exempt | — |

One finding per section; message includes: FK grade, composite score (0–100), and top-contributing metric.

**Edge case tests:**
- Tutorial section FK=8, composite=72 → no finding
- Tutorial section FK=14, composite=45 → finding with composite in message
- ADR section FK=20 → no finding (genre exempt)
- Section with < `READABILITY_MIN_SENTENCES` (3) → no finding
- Empty text → no finding
- `textstat` import fails → rule disabled with one-time warning
- **Consistency:** same section text passed to Vale `readability` rule and to this rule → FK grades match within ±0.5 (documents expected delta from `twine` syllable counter)

**const.py:** `READABILITY_TUTORIAL_FK_MAX = 12`, `READABILITY_TECHNICAL_FK_MAX = 16`, `READABILITY_MIN_SENTENCES = 3`

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
- Genre gate: only fires in `concept`, `explanation`, `technical` genres.

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
- `rhetoric_lint/rules/readability.py` — imports `rhetoric_lint.runners._readability.composite_score` and `preprocess_for_readability`
- `rhetoric_lint/rules/unsupported_claim.py`
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
