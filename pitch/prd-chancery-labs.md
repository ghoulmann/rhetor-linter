# PRD: Chancery Labs Toolkit

**Status:** Active development  
**Date:** 2026-06-09  
**Audience:** Engineering managers, tech leads, cross-functional team  
**Working repo:** `rhetor-linter` (rename to Chancery Labs at Gate 2 — see Naming)

---

## Problem

Technical documentation in engineering organizations has no continuous quality signal. Prose quality, structural coherence, and coverage against user needs all degrade invisibly between release cycles. Existing tools either check syntax (markdownlint, prettier) or style conventions (Vale, Grammarly Business) — none combines rhetorical analysis, Diataxis topic-type awareness, and job-to-be-done coverage into a single observable system.

The consequence for teams: low-quality docs surface through support load, onboarding friction, and LLM retrieval failures — not through any dashboard or gate that could have caught them earlier.

### Why this matters more now: AI ingestion

Teams increasingly use AI assistants, support bots, and RAG pipelines grounded on their documentation. Research on retrieval-augmented generation identifies the documentation failure modes that most reliably produce bad outputs:

- **Coverage gaps** → hallucination. When a user or integration job has no documentation, a grounded AI answers from adjacent context rather than admitting it doesn't know.
- **Section size and topic drift** → retrieval fragmentation. Sections exceeding the RAG-optimal window (400–600 words) are split mid-argument at ingestion; sections where the body drifts from the heading retrieve against the wrong query.
- **Terminology inconsistency** → embedding collision. When the same concept has multiple names across the doc set, embedding-based retrieval returns the wrong docs.
- **Stale content** → confident wrong answers. Code-docs drift is the most dangerous failure mode: the AI answers from a doc that was once correct and is now wrong.

These are not edge cases. They are the primary driver of LLM-based documentation failure at scale. Chancery Labs addresses all of them at the source — before content enters any ingestion pipeline.

**What we need:**

- A linter that catches rhetorical problems (not just syntax) and understands what kind of doc it's reading (concept, how-to, reference, tutorial)
- A scoring layer that produces stable, comparable metrics across files and repos
- A server that accumulates scan history, serves badges, and supports trend analysis
- A Backstage integration so doc health is visible where engineers already work

---

## The Chancery Labs Toolkit

Three components, one clean boundary between them:

| Component | Working name | Role |
|---|---|---|
| **shela** | `rhetoric-lint` (CLI) | Linter: text in → findings out. Pure function, no state. |
| **syla** | server (in-repo, `[server]` extra) | Stateful orchestrator: polls repos, stores scores, serves dashboard and badge endpoints. |
| **laxa** | auditor (future) | Cross-org benchmarking and governance audits. |

**The boundary artifact** is `rhetoric_lint/score.py` → `score_file()` → `ScoreResult`. syla calls this function and stores the result. It never touches spaCy, Vale rule parsing, or AST internals directly. shela never has state, HTTP, auth, or persistence.

---

## shela — The Linter

### What it does

shela is a Python CLI linter for Markdown technical documentation. It runs:

1. **spaCy NLP** — syntactic depth, nominalization, passive voice, tone imbalance, readability
2. **Vale-compatible YAML rules** — existence, substitution, metric, readability, spelling, and 7 other types; genre-gated; auto-fix support
3. **Native markdownlint rules** — 12 MD rules plus custom Python rule extension
4. **Genre + topic-type classification** — classifies each document (howto, tutorial, concept, explanation, reference, adr, postmortem, changelog, readme, general) and each section independently (howto, concept, reference, tutorial, explanation, troubleshooting, faq)

Classification runs before rules. Rules that are only meaningful for specific topic types self-qualify — no global genre gate.

### Key differentiator

No other linter does **per-section topic-type classification**. A single doc can have concept sections, how-to sections, and reference sections. shela scores each kind separately and fires appropriate rules for each. This is what makes the Diataxis breakdown in syla's dashboard meaningful.

### Current state (as of 2026-06-09)

All planned linter features through SP12 are implemented:

- ~28 NLP rule modules covering cohesion, coherence, unity, symmetry, rhetoric, structure, completeness, ADR, postmortem, tutorial, howto, concept, explanation, reference, FAQ, troubleshooting
- Vale runner: all 10 rule types, genre gating, vocab suppression, auto-fix
- markdownlint runner: 12 native MD rules + Python custom rule loader
- JTBD coverage rule (`Coverage.MissingJobCoverage`): reads `jtbd-manifest.json` from jtbd-tool, fires per missing job
- Scoring boundary: `score_file()` → `ScoreResult` implemented; `rhetoric-lint score` CLI command live
- Frontmatter parsing and section annotation pre-pass (F1/F2): implemented
- 150-word minimum floor for scoring: implemented
- `DIMENSION_MAP` in `const.py`: implemented

### Scoring dimensions

Five dimensions. Source of truth is `const.DIMENSION_MAP`. A redesign (SP_CONFIG, pending) retires the old Completeness dimension and adds Form and Coverage:

| Dimension | What it measures |
|---|---|
| **Clarity** | Prose quality: cohesion, readability, sentence complexity, passive voice |
| **Structure** | Document shape: headings, navigation, parallelism, wall-of-text |
| **Style** | Word-level choices: terminology, inclusivity, trivializing language |
| **Form** | Template adherence for topic type: howto steps, ADR structure, tutorial cues |
| **Coverage** | Depth and relevance: resilience (error paths), JTBD job coverage, curriculum gaps |

The score unit is **findings per 1,000 words** (density rate) — no composite 0–100 score. This allows meaningful comparison across docs of different lengths.

---

## syla — The Server

### What it does

syla is the stateful layer that makes shela's findings observable at repo and organization scale:

- **Polls repos** on a schedule (git clone --depth=1); calls `score_file()` per .md file
- **Stores score history** append-only (never overwrites; SQLite → Postgres migration path)
- **Badge endpoint** — Shields.io-compatible JSON per repo; drop-in for any README
- **Dashboard** — per-repo and per-doc health, dimension drill-down, Diataxis per-topic breakdown
- **PR gates** — GitHub/GitLab status check; inline review comments on changed lines; configurable density gate for merge blocking
- **Alerts** — Slack webhook or email digest when a governed repo crosses a configured threshold

### Data flow

```
rhetor-sources.yaml (config)
  → APScheduler (poll on schedule, default 6h)
  → git clone --depth=1 target repo
  → score_file() [rhetoric_lint.score] per .md file
  → ScoreResult JSON stored per run per file (append-only)
  → Dashboard reads store
  → Badge endpoint reads store
  → Backstage plugin reads API
```

### Build sequence

#### Phase 0 — Engine prerequisites (current focus)

Hard blockers for Phase 1:

| Item | Status |
|---|---|
| F3: SP12 emission rework — currently emits N×M findings (5 jobs × 50 files = 250 duplicates); must emit one corpus-level finding via CrossFileContext | **Open — hard blocker** |
| F8: Polling staleness documented as known limitation | Open |
| F10: Server import constraint added to CONTRIBUTING.md | Open |

Soft blockers (can run parallel with Phase 1):

| Item | Status |
|---|---|
| F6: SP12 tokenizer contract test | Open |

All other Phase 0 prerequisites (F1, F2, F4, F5, F7, F9) are complete.

#### Phase 1 — Server MVP (~3–5 days)

`rhetoric_lint/server/` sub-package, installed via `pip install rhetoric-lint[server]`.

Deliverables:
- FastAPI app + GitHub OAuth
- APScheduler polling from `rhetor-sources.yaml`
- SQLite store (score JSON per run per file)
- Badge endpoint (`/badge/{owner}/{repo}.json`)
- `rhetoric-lint serve` entry point

Done criterion: badge endpoint returns valid Shields.io JSON for a configured public repo.

#### Phase 2 — Dashboard + PR Gates + Alerts (~4–6 days)

Deliverables:
- Jinja2 HTML dashboard: repo list → doc list → dimension drill-down → per-topic breakdown
- Trend charts: score over last N runs
- Settings UI: add/remove repos, configure paths and thresholds
- PR inline annotations and merge gate
- Score degradation alerts (Slack/email)

Done criterion: a degradation in a governed repo's worst dimension triggers an alert within one polling cycle.

#### Phase 3 — History + Insights (~4–5 days)

Turns scan history into organizational intelligence:

- Per-file score delta: `Δ Clarity = +0.4/1kw since last week`
- Regression detector and improvement highlights
- Phase patterns: score by `sdlc_phase` over time
- JTBD coverage drift tracking
- Opt-in cross-repo anonymized benchmarking (no content leaves the server — scores and metadata tags only)

#### Phase 4 — Public polling + static export + auto-fix PRs (~2–3 days)

- `rhetor-sources.yaml` as the canonical config format
- Static dashboard export for GitHub Pages deployment option
- Auto-fix PR generation: server opens a PR with `--fix` applied to top-N fixable findings (opt-in per repo; requires write token)

---

## laxa — The Auditor (Phase 5+)

laxa is not yet in active development. It is the governance and cross-org audit surface — a separate tool that consumes syla's API to produce compliance reports, quality audits, and improvement playbooks at organizational scale.

---

## Backstage Plugin (Phase 5, separate repo)

A TypeScript plugin in its own repo. Two surfaces:

- **Owner view**: doc health profile for all docs owned by a Backstage catalog entity; issues by dimension; trend sparkline
- **Reader view**: quality chip in the TechDocs doc page header

The plugin reads pre-computed scores from syla's API — no direct linter calls. jtbd-tool already integrates with Backstage (`catalog-info.yaml` → job signals); the plugin will surface Coverage dimension findings in that same context.

---

## Repo and Deployment

**Current:** Everything lives in `rhetor-linter`. The server sub-package is `[server]` extra. Deploy target for MVP: Fly.io / Render free tier.

**Graduation condition** (server → own repo): when any of these becomes true:
- Server needs to deploy at a different version than the linter
- Server integrates a second analysis backend
- A contributor works exclusively on server and never touches linter rules

**Server import constraint:** rule modules in `rhetoric_lint/rules/` must never import server-layer packages at module level. This constraint belongs in CONTRIBUTING.md (F10, currently open).

---

## Naming

The Chancery Labs name and component names (shela, syla, laxa) are decided and will be applied at Gate 2 (repo creation / first public release). Until then, the working names stay:

| Future name | Current working name |
|---|---|
| Chancery Labs | rhetor-linter (GitHub org/repo) |
| shela | rhetoric-lint (CLI), `rhetoric_lint` (package) |
| syla | (not yet created) |
| laxa | (not yet created) |

Etymology: Chancery — the medieval office that authenticated and transmitted official documents. shela — she'ela, the question put to the text. syla — coined short form; transmits findings. laxa — from halaxa, the normative path.

---

## What Is Not in Scope

The following are intentionally out of scope for the Chancery Labs toolkit. They are either infrastructure concerns, require human review, or are covered by complementary tools:

- External link checking (markdown-link-check, htmltest)
- Image/media asset validation (Lighthouse, visual diffing)
- Cross-doc information architecture (jtbd-tool scope)
- Typography and layout (CSS/visual design)
- Precision and factual accuracy (human SME review)
- Strawman fallacy detection (heuristic too imprecise; human peer review)

---

## Open Questions

| Question | Status |
|---|---|
| Default polling interval | Suggest 6h; confirm before Phase 1 |
| Private repo strategy (per-org token vs. token pooling) | Defer to post-MVP |
| Cross-repo benchmark opt-in UX | Checkbox in `/settings`; explicit consent; hash repo slug before storing |
| History retention policy | Append-only indefinitely; configurable max-age purge |
| PR annotation token scope | Read-only for polling; separate write token for PR comments + auto-fix; opt-in per repo |
