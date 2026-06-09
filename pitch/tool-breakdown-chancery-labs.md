# chancery-labs: Tool-by-Tool Breakdown

---

## shela — Documentation Linter

### Problem

Documentation teams have no systematic way to catch prose quality problems before they reach users — clarity failures, structural inconsistencies, tone mismatches, and genre violations are invisible to standard linters and only surface through complaints or reviews. The problem compounds across a large doc set because no single reviewer has the bandwidth to audit everything consistently.

### Solution

shela is a CLI prose linter for Markdown documentation. It runs in CI alongside code linters, applies NLP-based rules and style checks to every doc on every commit, and outputs structured findings with severity levels and line numbers. It auto-fixes what it can and scores each file across five quality dimensions.

### Features and Benefits

**NLP prose rules (~30 rules via spaCy)**
Each rule targets a specific prose failure mode — coherence breaks between sentences, topic drift within sections, passive constructions without an identified actor, tone imbalance, sentence length monotony, excessive nominalization, syntactic complexity. Catches quality issues that no regex or grammar checker can find.

**Vale YAML style rules — existence, substitution, occurrence, metric, capitalization, repetition, consistency, conditional, readability, sequence**
The full Vale rule surface, loaded from any `--style-dir`. Teams write rules in YAML and ship them alongside their docs — no Python, no code review friction. Bundled styles cover trivializing language, inclusive terminology, Oxford comma, quote style, and readability. Custom styles extend to any naming convention, brand voice, or compliance requirement.

**Vale wordlists and approved-terms lexicon**
Substitution and conditional rules backed by plain-text wordlist files. Teams define their approved product terms, brand names, and preferred vocabulary; shela flags any deviation. Wordlists are version-controlled alongside the docs and updated by writers, not engineers.

**Vale metric rules (formula-based numeric enforcement)**
Any arithmetic expression over words, sentences, syllables, or characters can be a rule — per paragraph, per section, or per document. Enforces word-count targets, sentence-length caps, or custom readability formulas without writing code.

**Spellcheck with custom dictionary additions (`extends: spelling` via spylls)**
Spell-checking via spylls (offline, no API). Bundled dictionaries: en_US, sv_SE, ru. Domain vocabulary added via plain-text vocab files (`tech.txt`, `aws.txt`, or any custom file) — one word per line, case-insensitive. Valid technical terms no longer generate noise.

**markdownlint enforcement (12 rules + custom Python rules)**
Python-native markdownlint implementation — findings conform to the markdownlint standard and are compatible with all markdownlint-aware editors, CI tools, and config files. No CLI shelling, no Node.js dependency. 12 standard rules ship out of the box. Teams add org-specific rules as Python functions loaded via the markdownlint config — no JavaScript required.

**Lexi composite readability score**
Readability graded using the Lexi composite metric (weighted blend of Flesch Reading Ease, Gunning Fog, ARI, Dale-Chall, and Coleman-Liau — matching the Rebilly/lexi formula). Gives a single 0–100 score that is more stable and less gameable than any single metric. Configurable threshold per genre.

**JTBD coverage check (`--jtbd-manifest`)**
Accepts a manifest from laxa and flags any job the codebase performs that has no corresponding documentation coverage. Turns invisible gaps into lint findings — surfaced in CI before they reach users.

**Auto-fix (`--fix`)**
Applies deterministic fixes in-place: substitution rule corrections, formatting normalisation, style replacements. Reduces the manual effort to resolve findings.

**5-dimension quality scoring (density rate)**
Aggregates findings into five dimensions: Clarity (prose quality, readability), Structure (headings, navigation), Style (word-level choices, terminology), Form (template adherence — ADR structure, how-to steps, tutorial cues), and Coverage (JTBD job coverage, error paths, resilience). Score unit is findings per 1,000 words — a density rate that allows meaningful comparison across docs of different lengths.

**Per-section Diataxis breakdown**
Scores each dimension separately per topic type within a single file — concept sections, how-to sections, and reference sections in the same doc are scored independently. No other linter does this. It makes the distinction between "the doc is bad" and "the how-to sections in this doc are bad" visible and actionable.

**Genre-aware rules**
Distinguishes how-to guides, tutorials, concept docs, ADRs, postmortems, READMEs, and changelogs. Applies the right rules to each genre — imperative verb checks in how-tos, decision-record structure checks in ADRs — rather than running a single undifferentiated rule set against everything.

**Cross-file analysis (CrossFileContext)**
Two multi-file rules detect problems no single-file linter can: DependencyReveal flags concepts referenced before they are defined anywhere in the doc set; ConceptReintroductionPenalty flags sections in different files that re-explain the same concept (Jaccard ≥ 0.60 on content lemma sets).

**CI integration (pre-commit hooks, GitHub Actions)**
Runs automatically on every commit and PR without manual invocation. Quality checks are part of the build, not a separate process that gets skipped under deadline pressure.

**Section annotations**
YAML blocks before any heading can override the genre classifier for that section. Authors can annotate ambiguous sections explicitly rather than relying on inference.

**Frontmatter parsing**
Reads doc metadata (topic type, owner, audience, SDLC phase) from YAML frontmatter and uses it to tune rule application and scoring. Teams that invest in metadata get more precise findings.

---

## laxa — JTBD Extractor and Coverage Auditor

### Problem

No team knows with confidence what jobs their software actually performs — from a user's perspective or an integrator's. Manual JTBD exercises (workshops, surveys, annotation sprints) are expensive, inconsistent, and immediately outdated when the code changes. Integration jobs (API surfaces, webhook handlers, SDK usage, third-party dependencies) are especially invisible — they show up as support escalations, not as missing documentation. Without a reliable job map covering both user and integration jobs, coverage audits are guesswork. And even when coverage exists, it drifts: commits, PRs, and releases that affect JTBD-mapped jobs without a corresponding doc change are undetectable without tooling.

### Solution

laxa is a CLI that reads a codebase and infers its jobs-to-be-done from the code itself — imports, CI/CD configuration, call patterns, and docstrings — with no manual annotation and no LLM required for the core pipeline. It outputs a stable `jtbd-manifest.json` that downstream tools (shela, syla) use to audit coverage.

### Features and Benefits

**Import graph analysis (~200 library registry entries, SWEBOK-grounded)**
Maps library imports to job signals with 0.90 confidence. A codebase importing `snyk` signals "audit dependencies for CVEs"; importing `helm` signals "deploy application to Kubernetes." Provides the highest-confidence, lowest-noise signal in the pipeline.

**CI/CD config parsing (GitHub Actions, GitLab CI, Jenkinsfile, Terraform, Docker Compose)**
Reads pipeline stage names and maps them to job categories with 0.95 confidence. Stage names are the most explicit statement of what a pipeline does — laxa reads them so you don't have to.

**Call pattern extraction (subprocess, HTTP clients, cloud SDK calls)**
Analyzes function bodies for call patterns that reveal job intent — `boto3.client("ec2")` signals provisioning, `requests.post` to a known endpoint signals integration. Provides signal the import graph alone misses.

**Name/docstring NLP (spaCy dep parse)**
Parses function names and first-sentence docstrings to extract root verb + direct object → job map lookup. The lowest-confidence signal (0.45–0.65) but covers code that the higher-confidence signals don't reach.

**Four-tier job schema (Ulwick ODI + Software/DevOps + SWEBOK + Organizational)**
Classifies jobs against a four-tier taxonomy grounded in published methodology: universal job steps (Define, Locate, Prepare, Execute…), software/DevOps extensions (Deploy, Debug, Provision, Recover…), SWEBOK knowledge area subtypes (Confirm/SAST, Confirm/SCA, Deploy/CI…), and organizational process verbs (Plan, Assign, Track, Govern…). Jobs land in a structured, cross-comparable taxonomy rather than free-text labels.

**Confidence scoring and signal hierarchy**
Each job carries a confidence score and the signal that produced it. Conflict resolution follows a defined hierarchy: CI config > import > call pattern > docstring. Teams can inspect and trust the source of every job in the manifest.

**Doc coverage audit (Jaccard similarity)**
For each job in the manifest, computes similarity against doc paragraphs and flags jobs below a configurable threshold as `coverage: missing`. Produces an auditable, reproducible coverage report.

**FAQ signal extraction**
Parses FAQ entries as a gap-detection signal: questions that have no corresponding coverage elsewhere in the doc set reveal jobs that slipped through the initial coverage map. Each FAQ-signaled gap is classified against the JTBD taxonomy and assessed for remediation: whether it should be addressed, where (which doc, which section), and how (which genre — how-to, concept, reference, troubleshooting). FAQ items that belong in a different doc type entirely are flagged as semantic misrouting rather than coverage gaps.

**Stable manifest output (`jtbd-manifest.json`)**
Versioned JSON schema. Stable across laxa releases so downstream tooling (shela, syla, custom scripts) can depend on it without breakage.

**REST API (`laxa serve`)**
`POST /scan`, `POST /audit`, `GET /manifest/:id`, `GET /schema/steps`. Enables integration into platforms, dashboards, and custom tooling without CLI invocation.

**Optional LLM enhancement (`--model`)**
When an LLM is available, laxa can enrich job statements and resolve ambiguous signals. The core pipeline runs without it — LLM is an upgrade, not a dependency.

**Multi-language support**
Python, TypeScript, JavaScript, Go via tree-sitter grammars. Groovy/Jenkinsfile via regex + tree-sitter-groovy (planned). Covers the majority of polyglot engineering org codebases.

---

## syla — Documentation Quality Server

### Problem

Documentation quality is invisible at the org level — each team has a local sense of whether their docs are good, but there is no cross-repo view, no trend data, and no mechanism to prevent regressions from shipping. Quality improvements made in one quarter quietly erode in the next with no alert.

### Solution

syla is a stateful scoring server that polls repos, stores dimension scores over time, and makes documentation health a first-class org metric. It surfaces quality data where engineering and product teams already look — GitHub PR checks, Backstage, Slack — without requiring anyone to run a separate tool.

### Features and Benefits

**Repo polling and score storage (APScheduler + SQLite)**
Runs shela against watched repos on a configurable schedule and persists every scan result. Teams get a continuous quality history without manual intervention.

**Badge endpoints (embeddable SVG)**
`GET /badge/:repo` returns a quality badge suitable for README files and internal portals. Gives repos a visible, always-current quality signal that authors and reviewers see before opening the doc.

**Per-topic Diataxis breakdown (key differentiator)**
Scores each dimension separately per topic type — concept sections, how-to sections, and reference sections within the same file are scored independently. No other documentation quality tool does this. It makes "the how-to sections in this doc need work" a data point, not a judgment call. Teams can see precisely which topic types are degrading across the repo and target improvement effort accordingly.

**5-dimension score history and trend charts**
Per-repo and per-dimension trend lines over time. Teams can see whether Clarity is improving after a writing sprint, whether Structure is degrading as a repo grows, and where to focus effort next. Score unit is findings per 1,000 words — directly comparable across docs of different lengths.

**Score delta and commit correlation**
Per-file score delta surfaced as `Δ Clarity = +0.4/1kw since last week`, correlated with the git commits that changed the score. Teams can see not just that a score changed but why — which author, which commit, which changed-line count drove the shift.

**Cross-repo anonymized benchmarking (opt-in)**
Repos that consent contribute dimension scores (not content) to a shared pool. Benchmark view: "your Clarity score is 2.1/1kw; median for repos tagged `kubernetes` is 1.4/1kw." No content leaves the server — scores and metadata tags only.

**Improvement playbooks**
When a repo shows sustained improvement in a dimension, the server records which structural changes correlated with it — shorter sentences, more how-to sections, added prerequisites. Playbooks surface ranked, highest-ROI changes per repo based on what moved the needle for similar repos in history.

**PR quality gates**
Fails or warns a PR when the post-merge score would drop below a configured threshold. Prevents silent quality regressions from shipping without giving reviewers a chance to address them.

**Auto-fix PRs**
Server opens a PR with `--fix` applied to the top-N fixable findings — opt-in per repo, requires write token. Reduces the manual effort to clear a backlog of deterministic findings.

**Slack alerts on score regressions**
Notifies the owning team when a score drops significantly between scans. Quality regressions are surfaced immediately, not discovered in a quarterly review.

**GitHub OAuth**
Authenticates users via GitHub. No separate credential management; access follows existing GitHub org membership and repo permissions.

**Backstage plugin**
Surfaces per-repo doc health as a Backstage catalog card alongside build status, SLOs, and ownership. Doc quality becomes part of the standard engineering health picture that directors and platform teams already review.

**REST API (score_file / ScoreResult boundary)**
The server only imports `score_file` and `ScoreResult` from shela. Clean separation means the server and linter can be versioned and deployed independently. Custom integrations can call the scoring API directly.

**Dashboard (per-repo and cross-repo)**
Web UI showing current scores, dimension breakdowns per topic type, trend charts, and worst-performing docs. Gives DX leads and engineering directors a single place to assess org-wide documentation health.

---

## AI Risk Reduction

AI assistants, support bots, and RAG pipelines ingest documentation and use it to answer questions. The quality of those answers depends almost entirely on the quality of what gets ingested. Research on retrieval-augmented generation identifies the documentation failure modes that most reliably produce friction and dead ends:

**Coverage gaps produce hallucination.** When a job the software performs — user-facing or integration-facing — has no documentation, a grounded AI answers from adjacent context rather than saying it doesn't know. laxa's job manifest and shela's coverage check close this before any AI ingests the docs. FAQ-signaled gaps are caught as a second pass before they pollute the retrieval index.

**Section size and coherence determine retrieval quality.** RAG systems chunk documents at ingestion. Sections exceeding the optimal window (400–600 words) get split mid-argument; the retrieved chunk is incomplete and the generated answer is too. Sections where the body drifts from the heading retrieve against the wrong query. shela's chunk boundary and topic-coherence rules address this at the source.

**Terminology inconsistency degrades embedding similarity.** When the same concept is named differently across docs, embedding-based retrieval produces collisions. shela's terminology drift detection enforces consistent vocabulary across the full doc set — a retrieval quality requirement, not just a style preference.

**Passive constructions without agents break action extraction.** Task-oriented AI use cases depend on identifying who does what. "The configuration should be set" has no subject. Catching actorless passive voice before ingestion removes this failure class.

**Stale docs produce confident wrong answers.** Drift — code that changed without a corresponding doc update — is the most dangerous RAG failure mode: the model answers from content that was once correct and is now wrong. laxa's code-docs drift detection flags this at PR merge time, before stale content enters the ingestion pipeline.

**FAQ misrouting pollutes the retrieval signal.** FAQ entries that belong in a how-to create misleading matches for procedural queries. Semantic misrouting detection keeps the FAQ from degrading retrieval precision for the rest of the doc set.

**syla prevents drift from accumulating.** syla's continuous polling means stale or degraded content is caught at the scan cycle, not when an AI user surfaces it. Trend data shows which docs are getting worse before they become retrieval hazards.
