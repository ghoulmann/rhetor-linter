# chancery-labs: Documentation Quality You Can Measure and Ship

---

## The Problem

Documentation ships with gaps your users find before your team does. A perfectly formatted doc can still omit half of what the feature does. Quality erodes commit by commit — no one notices until a support ticket arrives, a new hire spends a day confused, or a customer escalates.

Existing tools check prose in isolation: grammar, heading levels, link validity. None of them know what the software actually does, so none of them can tell you when the docs don't cover it. And when every team grades their own docs, "good enough" is subjective and undiscoverable across the org.

---

## What chancery-labs Does

chancery-labs is a three-tool system that closes the gap between what your code does and what your docs say about it. It makes documentation quality measurable, trackable, and visible across the whole org — without LLM dependencies and without manual auditing.

---

## The Three Tools

**shela** is the documentation linter. It runs in CI and catches prose problems — clarity, structure, tone, readability — along with coverage gaps: jobs the product does that the docs don't mention. It auto-fixes what it can and produces a quality score across five dimensions: Clarity, Structure, Completeness, Style, and Readability.

**laxa** is the codebase reader. It analyzes the code itself to produce a structured map of what the software does — covering both user-facing jobs and integration jobs (API surfaces, webhooks, SDK usage, third-party dependencies). No manual tagging, no team surveys, no LLM required. That manifest feeds directly into shela's coverage checks. When a feature or integration ships without doc coverage, the CI build tells you, not your users. A planned code-docs drift sprint will flag commits, PRs, and releases that affect JTBD-mapped jobs without a corresponding documentation change.

**syla** is the quality server. It tracks documentation scores over time across all your repos, serves embeddable badges, raises PR gates when quality drops below threshold, and surfaces everything in a dashboard and a Backstage plugin. Doc health becomes a first-class org metric alongside build status and SLOs.

---

## What Teams Get

- Documentation gaps surface as CI findings before users hit them
- Doc quality becomes a measurable number, not a subjective judgment
- Platform and DX teams get org-wide visibility into doc health in one place
- PR gates prevent quality regressions from shipping silently
- Coverage is grounded in what the code actually does — not keyword matching, not guesswork

---

## Why This Matters for AI-Powered Products

AI assistants, support bots, and RAG pipelines ingest your documentation and use it to answer questions. The quality of those answers depends almost entirely on the quality of what gets ingested. Research on retrieval-augmented generation identifies the documentation failure modes that most reliably produce friction and dead ends for users:

**Coverage gaps produce hallucination.** When a job the software performs has no documentation, a grounded AI answers from adjacent context rather than saying it doesn't know. Users get confident wrong answers. laxa's job manifest and shela's coverage check close this before any AI ingests the docs.

**Section size and coherence determine retrieval quality.** RAG systems chunk documents at ingestion. Sections that exceed the optimal window (400–600 words) get split mid-argument; the retrieved chunk is incomplete and the generated answer is too. Sections where the body drifts from the heading retrieve against the wrong query. chancery-labs enforces chunk boundaries and topic coherence at the rule level.

**Terminology inconsistency degrades embedding similarity.** When the same concept is named differently across docs, embedding-based retrieval produces collisions — the right doc ranks below irrelevant ones. Consistent vocabulary across the full doc set is a retrieval quality requirement, not just a style preference.

**Passive constructions without agents break action extraction.** Task-oriented AI use cases depend on identifying who does what. "The configuration should be set" has no subject; an AI generating a runbook from it produces an incomplete instruction. Catching actorless passive voice before ingestion removes this failure class.

**Stale docs produce confident wrong answers.** Drift — code that changed without a corresponding doc update — is the most dangerous RAG failure mode: the model answers from content that was once correct and is now wrong. Code-docs drift detection flags this at PR merge time, before stale content enters the ingestion pipeline.

**FAQ misrouting pollutes the retrieval signal.** FAQ entries that belong in a how-to create misleading matches for procedural queries. Detecting semantic misrouting keeps the FAQ from degrading retrieval precision for the rest of the doc set.

These are not documentation aesthetics. They are the specific, peer-researched failure modes that cause AI-grounded systems to produce friction, dead ends, and wrong answers at scale.

---

## Status

| Tool | Status |
|------|--------|
| shela | Active — linting, auto-fix, scoring, and CI integration shipping |
| laxa | Active — codebase extraction and manifest generation in development |
| syla | In design — scoring API and Backstage integration spec complete |

All three tools are open source. The full pipeline runs in CI without an API key.
