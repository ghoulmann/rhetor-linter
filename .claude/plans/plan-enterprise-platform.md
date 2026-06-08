# Plan: Rhetor Enterprise Platform

**Created:** 2026-06-07  
**Updated:** 2026-06-07 (boundary decision, jtbd-reporter retired)  
**Status:** Design — blocked on F1/F2/F3 prerequisites (see § Prerequisite checklist)  
**Related:** `plan-support-for-markdownlint-joyful-teacup.md` § TODO (enterprise findings)

---

## What this is

An observability and governance platform for Markdown documentation sets, inspired by
Acrolinx but built on rhetor-linter's NLP + Diataxis-aware engine. Key differentiator:
scores documentation quality *per topic type* (concept / how-to / reference / tutorial)
within each file — no other tool does this.

Three surfaces:
1. **Badge endpoint** — Shields.io-compatible JSON per repo (zero-friction adoption)
2. **Dashboard** — per-repo and per-doc health scores, trends, drill-down
3. **Backstage TechDocs plugin** — owner insights + reader badge inside Backstage

---

## Architecture

### Linter / server boundary

The linter is a **pure function**: text in → findings out. No state, no HTTP, no persistence.
The server is a **stateful application** that orchestrates the linter and stores results.

The boundary artifact is `rhetoric_lint/score.py`:

```python
# rhetoric_lint/score.py  ← THE BOUNDARY
def score_file(path: str, engine: RhetoricEngine) -> ScoreResult: ...
def score_repo(paths: list[str], engine: RhetoricEngine) -> RepoScore: ...
```

`ScoreResult` is the JSON shape the server stores and the dashboard reads (see § Score JSON).
`rhetoric-lint score` CLI command calls `score_file()` and writes JSON to stdout or a file.

**The linter never:**
- Knows about repos, polling, or schedules
- Stores anything beyond `--fix` in-place edits
- Serves HTTP or has auth
- Knows about users

**The server never:**
- Reimplements analysis logic — calls `score_file()` only
- Knows about spaCy, Vale rule parsing, or AST internals
- Modifies findings — stores and serves them unchanged

**Graduation condition** (server → own repo): when any of these is true:
- Server needs to deploy at a different version than the linter
- Server integrates a second analysis backend
- A contributor works exclusively on server and never touches rules

### Repo structure

```
rhetoric_lint/              pip install rhetoric-lint
  rules/                    NLP rule modules (pure, stateless)
  runners/                  Vale, markdownlint runners
  score.py                  ← boundary: score_file() → ScoreResult
  fix.py
  metadata.py               frontmatter parsing + owner normalisation (F2, F9)

rhetoric_lint/server/       pip install rhetoric-lint[server]
  app.py                    FastAPI application factory
  auth.py                   GitHub OAuth (authlib)
  scheduler.py              APScheduler polling jobs
  store.py                  SQLAlchemy models (SQLite → Postgres)
  poller.py                 git clone --depth=1 + calls score_file()
  badge.py                  Shields.io JSON endpoint
  dashboard.py              Jinja2 HTML routes
  settings.py               Config YAML load + web UI API
  api.py                    /check, /score, /rules REST endpoints

backstage-rhetor-plugin/    Separate repo — TypeScript, reads server API only
```

Entry point: `rhetoric-lint serve`

Constraint (add to CONTRIBUTING.md when server is created): rule modules in
`rhetoric_lint/rules/` must never import server-layer packages at module level.

Deploy target: Fly.io / Render (free tier for MVP, ~$5/mo for persistent storage).

### Data flow

```
Config YAML / Web UI settings
  → APScheduler (poll on schedule)
  → git clone --depth=1 target repo
  → score_file() [rhetoric_lint.score] per .md file
  → ScoreResult JSON per file
  → SQLite store (per run, per file)
  → Dashboard reads store
  → Badge endpoint reads store
  → Backstage plugin reads badge/score API
```

---

## Repo targeting

**MVP:** YAML config file in the rhetor-server deployment listing repos, paths, labels.  
**Later:** Web UI at `/settings` — add org / repo / path glob / label via form. Stored in SQLite.

```yaml
# rhetor-sources.yaml
sources:
  - repo: org/repo
    paths: ["docs/**/*.md", "README.md"]
    label: "Platform Docs"
    owner: platform-team        # overrides frontmatter owner if absent
  - repo: org/other-repo
    paths: ["docs/"]
```

**Repo visibility:** Public repos first (no auth required for git clone). Private opt-in
later via GitHub token in server secrets.

**GitLab:** Same git clone approach; GitLab public repos require no token.

**Read the Docs:** Fetch source repo from RTD API, apply same git clone path.

**Polling staleness:** Default interval TBD (suggest: 6 hours). For active TechDocs
monorepos, this means up to 6-hour stale scores in Backstage. Known limitation — webhook-
based refresh is planned v2 (requires repo-side hook setup, out of MVP scope).

---

## Score model

### Unit and normalization

**Base unit:** findings / 1000 words (density rate). No composite 0–100 score.

**Minimum word floor:** Files with fewer than 150 words produce no density score and no
badge — marked "insufficient sample." This prevents 30-word stubs dominating cross-repo
comparisons.

**Aggregation:**
- File level: density per dimension across all findings in the file
- Topic level: density per dimension scoped to sections with that topic_type
- Repo level: mean density per dimension across all files in the scan

### Five curated dimensions

Industry ceiling is ~7 dimensions (Acrolinx: 7, Grammarly: 5). Five chosen here.
Source of truth is `const.DIMENSION_MAP` (const.py) — update there first, not here.
`const.DIMENSION_DEFAULT = "Style"` for any check prefix not matched.

**Redesigned 2026-06-08** — `Completeness` retired (category error); `Readability` absorbed into Clarity. Full spec in `plan-the-implementation-moonlit-shell.md` (SP_CONFIG). Implementation pending.

| Dimension | Prefixes | What it measures |
|---|---|---|
| **Clarity** | `Rhetoric`, `Attention`, `Cohesion`, `Coherence`, `Rhetoric.ReadabilityGrade`, `Clarity.FleschReadingEase`, `Clarity.Nominalizations`, `Clarity.PrepositionalDensity` | Prose quality + readability |
| **Structure** | `Heading`, `Symmetry`, `Structure`, `Navigation` | Document shape and navigation |
| **Style** | `Unity`, `Lexical`, `Terminology`, `Rhetoric.TrivializingLanguage`, `Rhetoric.Terminology`, `Rhetoric.Inclusivity`, `Rhetoric.InclusivityFlag` | Word-level choices and terminology |
| **Form** | `HowTo`, `ADR`, `Tutorial` | Template adherence for topic type |
| **Coverage** | `Coverage`, `Resilience`, `Substance`, `JTBD`, `Curriculum` | Depth, relevance, user needs served |

Vale YAML rules from `style-sets/*/` inherit dimension via a `dimension:` key in `meta.json`
(field to be added to meta.json spec; fall back to `DIMENSION_DEFAULT` if absent).

### Diataxis per-topic breakdown

Within each dimension, density is shown separately per `topic_type` when sections are
classified. This is the core differentiator — no other tool does topic-type-aware scoring.

Example: a file with mixed concept + how-to sections:
```
docs/deploy.md  (1240 words)
  Clarity    1.8/1kw overall
    [concept]  1.2/1kw
    [how-to]   3.4/1kw  ← hotspot
  Structure  0.6/1kw
  Style      0.4/1kw
  Form       0.9/1kw
  Coverage   2.1/1kw
    [how-to]   4.8/1kw  ← hotspot
```

Files with no classifiable topic structure show file-level density only (no empty rows).

### Badge

Badge shows worst-dimension density rate with colour thresholds (configurable):
- Green: worst dimension < 1.0/1kw
- Yellow: 1.0–3.0/1kw
- Red: > 3.0/1kw
- Grey: insufficient sample (< 150 words)

Shields.io endpoint: `GET /badge/{owner}/{repo}.json`
```json
{"schemaVersion": 1, "label": "doc health", "message": "2.3/1kw", "color": "yellow"}
```

---

## Score JSON shape (per file, per run)

```json
{
  "repo": "org/repo",
  "path": "docs/deploy.md",
  "title": "Deploy to Kubernetes",
  "word_count": 1240,
  "scanned_at": "2026-06-07T14:00:00Z",
  "metadata": {
    "topic_type": ["how-to"],
    "sdlc_phase": ["deployment", "operations"],
    "audience": ["developer", "devops"],
    "tags": ["kubernetes", "helm"],
    "owner": ["platform-team"],
    "author": ["jane.smith"]
  },
  "dimensions": {
    "Clarity":   {"rate": 1.8, "count": 22},
    "Structure": {"rate": 0.6, "count":  8},
    "Style":     {"rate": 0.4, "count":  5},
    "Form":      {"rate": 0.9, "count": 11},
    "Coverage":  {"rate": 2.1, "count": 26}
  },
  "sections": [
    {
      "heading": "Configure the Helm chart",
      "level": 2,
      "topic_type": "how-to",
      "word_count": 340,
      "metadata": {"audience": ["devops"], "sdlc_phase": ["deployment"]},
      "dimensions": {
        "Clarity":  {"rate": 3.4, "count": 12},
        "Coverage": {"rate": 4.8, "count": 16}
      },
      "findings": [
        {"check": "Cohesion.Break", "line": 42, "severity": "warning",
         "message": "Consecutive sentences share no discourse bridge."}
      ]
    }
  ]
}
```

---

## Metadata model

### Priority stack (topic_type)

```
1. Frontmatter field (file-level default)
2. Per-section annotation block (section-level override)
3. Inference via classify_section_topic() (current behaviour, fallback)
```

**Prerequisites F1 and F2 must be implemented before this stack is functional.**

### Frontmatter fields

Parsed via PyYAML before the engine blanks frontmatter. Stored in `context["frontmatter"]`.

| Canonical field | Accepted aliases | Type |
|---|---|---|
| `topic_type` | `type`, `kind`, `diataxis` | string or array |
| `sdlc_phase` | `sdlcPhase`, `stage`, `phase`, `lifecycle` | string or array |
| `tags` | `keywords`, `labels`, `categories` | string or array |
| `audience` | `target_audience`, `readers`, `for` | string or array |
| `author` | `authors`, `writer` | string or array |
| `owner` | `owners`, `maintainer`, `team`, `component` | string or array |
| `title` | — | string |

All values normalised to lowercase arrays internally.

### topic_type value normalisation

| Normalised | Accepted inputs |
|---|---|
| `howto` | `how-to`, `howto`, `how_to`, `how-to guide`, `guide` |
| `concept` | `concept`, `concepts`, `conceptual` |
| `reference` | `reference`, `ref`, `api` |
| `tutorial` | `tutorial`, `tutorials` |
| `explanation` | `explanation`, `explanatory`, `background` |
| `troubleshooting` | `troubleshooting`, `troubleshoot` |
| `faq` | `faq` |
| `general` | `general` (fallback) |

### sdlc_phase vocabulary

| Normalised | Accepted inputs |
|---|---|
| `planning` | plan, planning, discovery |
| `design` | design, architecture, spec |
| `development` | dev, development, build, implementation |
| `testing` | test, testing, qa, validation |
| `deployment` | deploy, deployment, release, ship |
| `operations` | ops, operations, run, operate, runbook |
| `maintenance` | maintain, maintenance, support |

### Per-section annotation blocks

Format: HTML comment containing a YAML frontmatter-style block.
```
<!--
---
topic_type: reference
audience: architect
sdlc_phase: design
---
-->
## API Contract
```

**F1 fix required:** parse these in a dedicated pass *before* `_blank_html_comments()`
runs. Cache parsed metadata keyed by line number. In `classify_section_topic()`, check
cache for the heading's line before running inference.

Association rule: metadata applies to the next heading after the block. A block before
any heading applies file-wide (same priority as frontmatter).

### Document title resolution

```
1. frontmatter title:    → document title; first H1/H2 is not the title
2. first H1 in body     → document title
3. first H2 in body     → document title (MkDocs pattern)
4. filename stem        → last resort (slugged, hyphens → spaces, title-cased)
```

The heading that wins the title role is excluded from topic_type inference.

`Heading.H1` rule must not fire when frontmatter `title:` is present.

### Owner field → Backstage normalisation

Backstage entity references use `group:name` or `user:name` format. Frontmatter `owner:`
values are freeform. Normalisation contract (implement alongside F2 fix):

1. If value already matches `(group|user|system):.+` → use as-is
2. If value contains `/` (e.g. `org/team`) → map to `group:team`
3. Otherwise → prefix with `group:` (most common case)

Store both raw and normalised values in score JSON.

---

## Dashboard drill-down axes

The dashboard provides filter/group-by on all metadata facets independently:

| Facet | Dashboard view |
|---|---|
| `owner` | Per-team doc health; maps to Backstage `spec.owner` |
| `audience` | Which docs targeting `developer` have poor Completeness? |
| `sdlc_phase` | Which phases have thin or low-quality documentation? |
| `tags` | All docs tagged `kubernetes` across repos |
| `topic_type` | All how-to sections with high Completeness density |
| `author` | Personal doc health (opt-in; privacy consideration for public repos) |

---

## Backstage TechDocs plugin

Two surfaces:

**Owner view** (catalog entity page):
- Doc health profile for all docs owned by that component
- Issues by dimension and severity
- Trend over last N scans
- Hooks into TechDocs publish to trigger re-score (v2; MVP uses polling)

**Reader view** (TechDocs doc page header):
- Quality chip: "doc health: 2.3/1kw · 2 warnings"
- Non-intrusive; links to full dashboard drill-down

Plugin consumes pre-computed scores from the server API, not live lint results.
`owner` field from doc frontmatter → matched to Backstage catalog `spec.owner`
(see owner normalisation above).

jtbd-tool already integrates with Backstage (`catalog-info.yaml` → job signals).
jtbd-reporter is retired (was early ideation); jtbd-tool is the sole implementation.

---

## JTBD integration (SP12)

SP12 (`rhetoric_lint/rules/jtbd_coverage.py`) reads `jtbd-manifest.json` produced by
`jtbd-tool scan` and fires a warning per job with `coverage == "missing"`.

**Status: ✅ Implemented (2026-06-07).** jtbd-tool Tier 3 complete. `--jtbd-manifest` CLI flag live.

**F3 fix still open:** Current implementation emits one finding per file per
missing job → N×M spam (5 jobs × 50 files = 250 identical findings). Fix options:

- *Preferred:* Emit one corpus-level finding per missing job via `CrossFileContext`
  (SP1 complete, CrossFileContext stub exists). One finding, path = manifest path.
- *Alternative:* Require manifest to include `primary_doc_path` per job; fire only there.

**F6 fix required:** Add a contract test — fixed text + job statement → expected Jaccard
score — run against both jtbd-tool's `auditor.py` and SP12's `_tokenize`. Ensures
tokenizer parity is enforced in CI whenever either tool changes stopwords.

**jtbd-reporter** (`~/Documents/github/jtbd-reporter`): **retired** — was early ideation.
jtbd-tool is the sole implementation and manifest source. No integration work needed.

---

## Build sequence

### Phase 0 — Engine prerequisites (this repo)

Hard blockers (must complete before Phase 1): F3 (SP12 N×M emission), F8, F10.
Soft blockers (can run in parallel with Phase 1): F6 (tokenizer contract test — testing only, no behaviour change).

| Item | Blocker | Status | File |
|---|---|---|---|
| Parse frontmatter into `context["frontmatter"]` (PyYAML) | F2 | ✅ done | `engine.py` |
| Annotation pre-pass before `_blank_html_comments()` | F1 | ✅ done | `engine.py` |
| `DIMENSION_MAP` in `const.py` (redesign pending SP_CONFIG) | F5 | ✅ done (old dims); redesign open | `const.py` |
| `rhetoric_lint/metadata.py` — frontmatter normalisation + owner → Backstage | F2, F9 | ✅ done | `metadata.py` |
| `rhetoric_lint/score.py` — `score_file()` + `ScoreResult` (boundary artifact) | — | ✅ done | `score.py` |
| `rhetoric-lint score` CLI command — calls `score_file()`, JSON to stdout | — | ✅ done | `main.py` |
| Word-count minimum floor (150w) in score output | F4 | ✅ done | `score.py` |
| SP12 emission model rework (corpus-level via CrossFileContext) | F3 | open — hard blocker | `jtbd_coverage.py` |
| SP12 tokenizer contract test | F6 | open — soft blocker | `tests/test_jtbd_coverage.py` |

### Phase 1 — Server MVP (~3–5 days)

`rhetoric_lint/server/` sub-package, installed via `[server]` extra.

- FastAPI app + GitHub OAuth
- APScheduler polling (config YAML sources)
- SQLite store (score JSON per run per file) — **append-only; never overwrite history**
- Badge endpoint (`/badge/{owner}/{repo}.json`)
- `rhetoric-lint serve` entry point

### Phase 2 — Dashboard + PR Gates + Alerts (~4–6 days)

- Jinja2 HTML dashboard: repo list → doc list → dimension drill-down → findings
- Per-topic Diataxis breakdown view
- **Trend charts**: score over last N runs; highlight regressions and improvements
- Settings UI (`/settings`): add/remove repos, configure paths and quality thresholds
- **PR inline annotations**: GitHub/GitLab status check per PR; post review comments for findings on changed lines; configurable merge gate (fail if worst-dimension density > threshold)
- **Score degradation alerts**: Slack webhook / email digest when any governed repo crosses a configured threshold; weekly summary of worst-deteriorating docs per owner

### Phase 3 — History, Insights, and Lessons (~4–5 days)

This phase turns stored scan history into organizational intelligence.

**Change history per KB:**
- Full append-only scan log: every run is a timestamped record (never overwritten)
- Per-file score delta: `Δ Clarity = +0.4/1kw since last week` — surfaced in dashboard and badge tooltip
- Annotation of *why* a score changed: correlate score deltas with git commit metadata (commit message, author, changed line count) when the repo is polled via git clone
- `GET /history/{owner}/{repo}/{path}` — time-series score JSON for any file

**Insights derived from history:**
- Regression detector: files whose score has worsened ≥ N% over the trailing window → flagged in dashboard and alert
- Improvement highlights: files that improved significantly — surfaced as positive signal, not just problem-finding
- Phase patterns: score by `sdlc_phase` tag over time — "your deployment docs degrade every quarter"
- Owner health trends: per-team quality trajectory (aggregate, not per-author unless opted in)
- JTBD coverage drift: track `Coverage.MissingJobCoverage` findings over time — are jobs getting covered or accumulating?

**Lessons for others (cross-repo / cross-org benchmarking):**
- Opt-in anonymized aggregate: repos that consent contribute dimension scores (not content) to a shared pool
- Benchmark view: "your Clarity score is 2.1/1kw; median for repos tagged `kubernetes` is 1.4/1kw"
- Pattern library: when a repo shows sustained improvement in a dimension, record what structural changes (more how-to sections, shorter sentences, added prerequisites) correlated with improvement — surfaced as "what tends to work" guidance
- Improvement playbooks: server generates a ranked list of highest-ROI changes per repo based on what moved the needle for similar repos in history
- Privacy constraint: no content leaves the server — only aggregate numeric scores and metadata tags are used for cross-repo benchmarks

**Store schema additions for Phase 3:**
```
scan_run:        id, repo, scanned_at, commit_sha, commit_message, changed_files[]
file_score:      id, scan_run_id, path, word_count, dimensions{}, findings_count
file_score_delta:file_score_id, prev_file_score_id, Δdimensions{}
insight:         id, repo, insight_type, generated_at, payload_json
benchmark_pool:  repo_slug_hash, tag[], dimension_scores{}  ← anonymized opt-in only
```

### Phase 4 — Public polling + static export + auto-fix PRs (~2–3 days)

- Git clone poller for GitHub + GitLab public repos
- Static dashboard export (for GH Pages deployment option)
- `rhetor-sources.yaml` config format
- **Auto-fix PR generation**: server opens a PR with `--fix` applied to the top-N fixable findings; requires write token; opt-in per repo

### Phase 5 — Backstage plugin (separate repo, TypeScript)

- Catalog entity page: owner doc health panel + trend sparkline
- TechDocs page: reader quality chip
- Reads from Phase 1–3 server API
- **Lessons panel**: surface "what worked for similar repos" insights inline in Backstage

---

## Open questions

| Question | Status |
|---|---|
| jtbd-reporter integration scope | **Resolved** — jtbd-reporter retired; jtbd-tool is sole impl |
| Default polling interval | Suggest 6h; confirm before Phase 1 |
| Private repo strategy (token pooling vs per-org token) | Defer to post-MVP |
| Backstage plugin repo: separate vs monorepo | **Resolved** — separate repo (TypeScript, own cadence) |
| `meta.json` `dimension:` field for Vale style dirs | Define when DIMENSION_MAP is written (F5) |
| jtbd-tool Tier 3 ETA | **Resolved** — jtbd-tool Tier 3 complete (REST API, clusterer, actor routing) |
| Server graduation to own repo | When: different deploy cadence, second backend, or dedicated contributor |
| PR annotation token scope | Read-only token for polling; separate write token for PR comments + auto-fix PRs; opt-in per repo |
| Cross-repo benchmark opt-in UX | Checkbox in `/settings` per repo; explicit consent; hash repo slug before storing |
| History retention policy | Append-only indefinitely (SQLite → Postgres); configurable max-age purge per deployment |
| Insight generation: scheduled vs on-demand | Scheduled (nightly) for trend/phase patterns; on-demand for playbook generation |

---

## Prerequisite checklist (F1–F10)

Before any Phase 1 server code is written, these must be resolved:

- [x] **F1** — Section annotation pre-pass in engine.py ✓ (implemented, see `_extract_section_annotations()`)
- [x] **F2** — Frontmatter parsed into `context["frontmatter"]` ✓ (`const.FRONTMATTER_ALIASES`, engine.py:279)
- [ ] **F3** — SP12 emission model reworked (corpus-level, not per-file) — hard blocker for Phase 1
- [x] **F4** — 150-word minimum floor in score output ✓ (`const.SCORE_MIN_WORDS = 150`, `score.py` skeleton)
- [x] **F5** — `DIMENSION_MAP` written and committed to `const.py` ✓ (const.py:591)
- [ ] **F6** — SP12 tokenizer contract test passing
- [x] **F7** — jtbd-reporter retired; jtbd-tool is sole implementation ✓
- [ ] **F8** — Polling staleness documented as known limitation
- [x] **F9** — Owner normalisation spec implemented in `metadata.py` ✓ (`normalise_owner()`, `normalise_topic_type()`, `normalise_frontmatter()`)
- [ ] **F10** — Server import constraint added to CONTRIBUTING.md
