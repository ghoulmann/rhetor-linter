# chancery-labs: Problems Inventory

All problems each tool addresses, drawn from implemented rules, planned rules, and design decisions.

---

## shela — Documentation Linter

### Prose Quality

| Problem | Rule |
|---|---|
| Sentences that don't connect to each other — no lexical or discourse bridge | Cohesion.Break |
| Sentence isolated from all surrounding text — no link in either direction | Coherence.IslandSentence |
| Section topic drifts from what the heading promised | Unity.HeadingTopicCoherence |
| Section body drifts from what the topic sentence set up | Unity.TopicSectionDrift |
| Passive construction with no identified actor — reader can't tell who does the step | Rhetoric.PassiveVoiceActorGap |
| Sentence rhythm is monotonous or wildly uneven — all the same length or one enormous outlier | Attention.SentenceRhythm |
| Single sentence is too long — exceeds working-memory capacity | Attention.SplitAttention |
| Paragraph exceeds 150 words — too much in one unit of thought | Structure.ParagraphLength |
| Section exceeds 500 words — will be split badly by RAG chunkers | Structure.ChunkBoundary |
| Section is shorter than 80 words — probably underdeveloped | Structure.ChunkTooShort |
| Excessive nominalization buries the action in abstract nouns | Rhetoric.Nominalization |
| Syntactic depth too high — sentence is too nested to parse on first read | Attention.SyntacticDepth |
| Propositional density spikes within a section — comprehension cliff | Rhetoric.ComplexitySpike |
| Metric/number density too high — reader can't absorb the data | Attention.MetricDensity |
| Document opens with high-stopword sentence that delays actual content | Rhetoric.ThroatClearing |
| Prose presents only two options when more exist | Rhetoric.FalseDilemma |
| Contrast signal ("however", "but") with no resolution — reader can't determine the takeaway | Rhetoric.UnresolvedContrast |
| Causal connective ("therefore", "thus") with no causal predecessor | Cohesion.ConnectiveMismatch |
| Assertion signal ("therefore", "this means") with no supporting evidence or example | Completeness.UnsupportedClaim |
| Demonstrative pronoun ("this", "that") with no clear antecedent | Cohesion.DeicticGhost |
| High pronoun density without enough noun anchors — reader loses referential track | Cohesion.GivennessBreak |
| Backward reference ("as described above") breaks section as standalone entry point | Cohesion.ForwardReference |
| Key term introduced early then never mentioned again | Cohesion.AbandonedTopic |
| Different sections use different words for the same concept | Cohesion.TerminologyDrift |
| Transition word doesn't match the logical relationship between sentences | Cohesion.MisusedConnective |
| Too many paragraphs of explanation before first actionable element | Completeness.ConceptOverload |
| Section opens directly with list or code block — no lead sentence explaining why | Completeness.StructureLead |
| Wall of text — long prose block with no lists, code fences, or headings to break it up | Structure.WallOfText |
| Document too long for LLM context window | Clarity.TokenBudget |

### Voice, Tone, and Terminology

Vale style rules are YAML files teams write and own — no Python required. shela loads any Vale-compatible style directory via `--style-dir`. Supported extension types cover the full Vale rule surface.

| Problem | Rule / Extension type |
|---|---|
| Trivializing language ("just", "simply", "obviously") — implies reader should find this easy | Rhetoric.TrivializingLanguage (`extends: existence`) |
| Modal ambiguity in procedural steps — mixes "must" and "should", reader can't tell what's mandatory | Rhetoric.ModalAmbiguity (`extends: existence`) |
| Tone imbalance — too authoritative or too negative relative to genre expectations | Rhetoric.ToneImbalance (`extends: existence`) |
| Non-inclusive or outdated terminology | Rhetoric.Inclusivity / Rhetoric.InclusivityFlag (`extends: substitution`) |
| Preferred-form violation — uses a deprecated or inconsistent term | Terminology.PreferredForm (`extends: substitution`) |
| Personal attack pattern (ad hominem) in argumentative doc | tone.py |
| Punctuation inconsistency — Oxford comma or quote style used inconsistently across document | Clarity.OxfordComma / Clarity.QuoteStyle (`extends: consistency`) |
| Banned or discouraged word appears too often (occurrence cap) | Custom rule (`extends: occurrence`) |
| Term used without its defined paired counterpart | Custom rule (`extends: conditional`) — e.g. "allowlist" requires "blocklist" to also appear |
| Repeated identical phrase within a window | Custom rule (`extends: repetition`) |
| Capitalisation inconsistency — product names, acronyms, headings | Custom rule (`extends: capitalization`) |
| Numeric document-level or section-level threshold violated — word count, sentence count, formula | Custom rule (`extends: metric`) — any arithmetic formula over words/sentences/syllables/characters |
| Sequence of required phrases or sections violated — e.g. "Note:" must precede warning text | Custom rule (`extends: sequence`) |
| Word appears that is not in the approved project lexicon | Custom wordlist rule (`extends: substitution` + vocab file) |
| Term not defined in the project glossary used on first occurrence | Custom conditional rule against approved-terms wordlist |

### Structure and Navigation

| Problem | Rule |
|---|---|
| Document has no top-level H1 | Heading.H1 |
| Heading uses a generic name that gives no content signal | Heading.Generic |
| Heading is vague — gives no indication of what the section contains | Heading.InformationScent |
| Two headings are nearly identical — navigation ambiguity | Heading.NearDuplicate |
| Document lacks sufficient headings or anchors for its length — hard to navigate | Navigation.FindabilityMap |
| Task-oriented section lacks imperative structure | Structure.TaskOrientation |
| Headings in a task doc are noun-only — verb-led headings would be clearer | Structure.ActionableHeadings |
| List items don't share parallel grammatical structure | Symmetry.Parallelism |
| Steps in a task list don't begin with imperative verbs | Symmetry.OrderedListImperatives |
| Content tabs across doc use inconsistent variant labels | Symmetry.TabVariantBalance |

### Readability

| Problem | Rule |
|---|---|
| Readability grade too high for intended audience — composite Lexi score (Flesch 16.5%, Gunning Fog 22.3%, ARI 23.3%, Dale-Chall 19.6%, Coleman-Liau 18.3%) below threshold | Rhetoric.ReadabilityGrade (metric: Lexi) |
| Flesch Reading Ease too low — sentence structure or word choice too complex | Clarity.FleschReadingEase |
| No single readability metric is reliable alone — disagreement between tools | Lexi composite (weighted blend of five textstat metrics; 0–100 scale) |
| Spelling errors | Spelling.Spelling |
| Valid technical terms flagged by standard spellcheckers; domain vocabulary not recognised | Spelling extension vocab files (tech.txt, aws.txt, custom wordlists) |
| Nominalizations inflate word count and obscure meaning | Clarity.Nominalizations |
| Prepositional phrase chains slow reading speed | Clarity.PrepositionalDensity |

### Markdown and Format

shela's markdownlint implementation is Python-native — findings conform to the markdownlint standard, are compatible with all markdownlint-aware editors and CI tools, and consume standard `.markdownlint.json` / `.markdownlint.yaml` config files. No CLI shelling, no Node.js dependency.

| Problem | Rule |
|---|---|
| Heading hierarchy skips levels | MD001 |
| Document doesn't start with H1 | MD041 |
| Heading style is inconsistent (ATX vs setext) | MD003 |
| Trailing spaces or hard tabs in source | MD009 / MD010 |
| Lines exceed configured length | MD013 |
| Missing blank lines around headings | MD022 |
| Missing blank lines around code fences | MD031 |
| Missing blank lines around lists | MD032 |
| Fenced code block has no language tag | MD040 |
| Document has more than one H1 | MD025 |
| Org-specific or platform-specific Markdown conventions not covered by standard rules | Python custom rules loaded via markdownlint config — teams write rules in Python, no JS and no CLI shelling required |

### Genre Conformance

| Problem | Rule |
|---|---|
| Concept doc contains procedural steps — belongs in a how-to | Concept.ProcedureLeak |
| Reference doc contains instructions — belongs in a how-to | Reference.ContainsInstructions |
| Explanation doc contains instructions | Explanation.ContainsInstructions |
| Explanation doc has no links to related concepts | Explanation.NoConnections |
| How-to step doesn't begin with an imperative verb | HowTo.NonImperativeStep |
| How-to section uses unordered list where numbered sequence is required | HowTo.UnorderedSteps |
| Tutorial offers alternative paths — tutorials must follow a single route | Tutorial.AlternativesDiversion |
| Tutorial section has no feedback cue ("you should see…") | Tutorial.NoObservationCues |
| Troubleshooting section has no remediation steps | Troubleshooting.MissingRemediation |
| Troubleshooting remediation is in unordered list — order matters | Troubleshooting.UnorderedRemediation |
| FAQ entry has no substantive answer | FAQ.EmptyAnswer |
| FAQ heading is not phrased as a question | FAQ.NonQuestionEntry |
| Procedural section has no failure guidance or error scenario | Resilience.ErrorPathPresence |
| Imperative section has no verification step or expected output | Completeness.ResultVerification |

### ADR / Postmortem Completeness

| Problem | Rule |
|---|---|
| ADR missing Status field | ADR.MissingStatus |
| ADR missing Decision section | ADR.MissingDecision |
| ADR status is Proposed/Draft but Decision section has no body | ADR.UndecidedStatus |
| ADR missing Consequences, Trade-offs, or Impact section | ADR.MissingConsequences |
| Postmortem missing Root Cause or Contributing Factors section | Postmortem.MissingRootCause |
| Postmortem missing Action Items or Corrective Actions section | Postmortem.MissingActionItems |
| Action item has no assigned owner and no due date | Postmortem.OpenActionItem |
| Postmortem missing Timeline section | Postmortem.MissingTimeline |

### JTBD Coverage

| Problem | Rule |
|---|---|
| A job the codebase performs has no documentation coverage | Coverage.MissingJobCoverage |

---

## laxa — JTBD Extractor and Coverage Auditor

| Problem | How laxa addresses it |
|---|---|
| No one knows what jobs the software actually performs — from a user's or integrator's perspective | Extracts job map from code signals — import graph, CI/CD config, call patterns, docstrings |
| Integration jobs (API surfaces, webhooks, SDK usage, third-party dependencies) are undocumented and invisible | Import graph and call pattern extraction surface integration-facing jobs alongside user-facing ones |
| Manual JTBD exercises (workshops, surveys) are expensive and immediately outdated | Derives jobs from current codebase state; re-run on every commit |
| Coverage audits are guesswork without a reliable job map | Produces a structured, code-grounded manifest with confidence scores |
| Features and integrations ship without any documentation coverage — gaps invisible until user complaint | Flags `coverage: missing` for every unmatched job; feeds shela's coverage check |
| Code changes without corresponding doc updates — drift accumulates silently | Code-docs drift detection sprint planned: flags commits, PRs, and releases that affect JTBD-mapped jobs without a corresponding documentation change |
| FAQ entries signal undocumented jobs — but nobody reads them as a gap map | Parses FAQ question text as a JTBD signal; maps questions to the job taxonomy; flags jobs that have FAQ coverage but no substantive doc coverage |
| A gap is flagged but no one knows whether, where, or how to remediate it | For each detected gap, outputs remediation guidance: whether it warrants a new doc, which existing doc should absorb it, and which genre (how-to, concept, reference, troubleshooting) fits the job |
| FAQ entries that belong in a different topic type create noise in the FAQ | Flags semantic misrouting — FAQ items whose question text maps to a how-to or concept job rather than a lookup need |
| No one knows what the CI/CD pipeline actually does from a documentation perspective | Parses GitHub Actions, GitLab CI, Jenkinsfile, Terraform, Docker Compose stage names → job signals |
| Library/dependency usage is undocumented and unchecked against docs | Maps ~200 library imports to JTBD signals via SWEBOK-grounded registry |
| No standard taxonomy for classifying software jobs — every team uses different language | Four-tier schema: Ulwick ODI + Software/DevOps extension + SWEBOK KA + Organizational processes |
| JTBD classification requires an LLM or a long annotation sprint | Core pipeline runs without LLM; all four extraction signals are rule-based |
| Polyglot codebases (Python, TypeScript, Go, JavaScript) have no unified job extraction | tree-sitter grammars per language; shared classifier and schema |
| No API for pulling job data into dashboards, portals, or custom tooling | REST API: POST /scan, POST /audit, GET /manifest/:id, GET /schema/steps |
| External docs (product sites, wikis) not captured by codebase scan alone | Optional BFS crawler for external doc coverage |
| Large codebases exceed single-pass extraction capacity | Skeleton chunking for incremental extraction |
| LLM enhancement available but not always possible (cost, privacy, offline) | `--model` flag makes LLM opt-in; all core jobs run without it |

---

## syla — Documentation Quality Server

| Problem | How syla addresses it |
|---|---|
| Doc quality is invisible at the org level — no cross-repo view | Polls all watched repos, stores scores, serves cross-repo dashboard |
| No trend data — quality improvements erode silently over time | Appends every scan result; trend charts per dimension per repo |
| No mechanism to prevent quality regressions from shipping | PR quality gates: fail or warn when post-merge score would drop below threshold |
| Quality is subjective with no shared baseline across teams | Five-dimension numeric score (Clarity, Structure, Completeness, Style, Readability) gives a common language |
| Linter results are ephemeral — run locally and forgotten | Server persists every scan; history is queryable |
| No embeddable signal that a repo's docs are in good shape | Badge endpoint (GET /badge/:repo) — embeddable SVG, always current |
| No alert when a team's doc score regresses | Slack alerts on significant score drops between scans |
| Doc health not visible in the tools engineers already use (Backstage, GitHub) | Backstage plugin (doc health card alongside build status and SLOs); GitHub PR check integration |
| No REST API for custom integrations or reporting pipelines | score_file / ScoreResult boundary; server exposes scores over HTTP |
| Server and linter versioned independently but tightly coupled | Import boundary constraint: server only imports score_file and ScoreResult — no internal linter coupling |
| Platform and DX leads lack a single place to prioritize doc improvement effort | Dashboard shows worst-performing docs and dimensions across all repos |
