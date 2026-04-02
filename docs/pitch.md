Rhetoric-lint is a command-line tool that inspects Markdown and gives clear, practical suggestions to make docs easier to read, scan, and use.

- What it does: scans Markdown files and flags readability and structure issues — very long sentences, vague or generic headings, non-parallel lists, missing top-level titles, sections that jump topics, and paragraphs that don't connect.
- Why it helps: it gives concrete, fixable guidance (split this sentence, make the heading actionable, add an example) so authors can improve content quality before publishing.
- How to run: use the `rhetoric-lint` command on a file or folder; output formats include human text and machine-friendly JSON/YAML for CI.
- Severity and filtering: issues are classified as suggestions, warnings, or errors so teams can focus on what matters.
- Configuration: a config file can enable/disable checks and tune thresholds (e.g., maximum sentence length).

Bridging docs-as-code to docs-as-infrastructure

- Treats docs as systems: it looks at full document structure (headings, sections, lists) and relationships between parts, helping teams model documentation as connected, navigable units rather than isolated files.
- Enables automation: structured output and configurable rules make it possible to run content checks in CI, gate merges, and track doc health over time — the same way code quality is enforced.
- Improves discoverability: checks for heading “scent”, navigation maps, and section alignment so docs are easier for users and search systems to find and use.
- Reduces reader effort: by measuring cohesion, sentence length, and information spikes, it helps keep content scannable and focused for quick-answer use cases.

Value beyond templates, topic models, and style guides

- Verifies real connections, not just labels: templates ensure sections exist; rhetoric-lint checks whether those sections actually contain the expected content and semantic connections.
- Enforces actionability: it detects whether a “How-to” or task list is actually actionable and followed by expected results or examples, not just present because a template required it.
- Finds structural anti-patterns templates miss: wall-of-text, mismatched list forms, missing internal links, and non-sequitur paragraphs are practical issues templates and topic models often overlook.
- Produces CI-ready data: outputs structured issues for automation and triage, making doc health visible and measurable across a product’s lifecycle.

Why this matters for headless LLM-produced docs

- LLMs write text fast, but they often miss structural needs: generated content can be fluent yet lack clear examples, navigation, consistency, or cohesion between sections.
- Post-process and quality-check LLM outputs: rhetoric-lint can be used after generation to flag gaps (missing examples, weak headings, non-actionable steps) so generated drafts are raised to production quality.
- Prevents scale problems: when many documents are produced by models, automated checks catch repeatable issues at scale instead of relying on manual review.
- Complements, doesn't replace, content review: it highlights where human attention is needed (missing facts, absent examples, or structural fixes) so reviewers focus on high-value edits.

Research backing

Research in technical communication and human–computer interaction supports the kinds of checks rhetoric-lint applies: breaking text into short, focused chunks reduces cognitive load; clear, descriptive headings improve scanning and findability; cohesive links between sentences and sections improve comprehension; and task-focused examples increase task success. Below are representative sources you can cite when describing the tool's foundations.

Representative recent sources (2023–2026):

- Nielsen Norman Group articles (2023–2025) on web reading, writing, and information scent.
- Recent HCI and educational-psychology reviews (2023–2025) on cognitive load and chunking in instructional materials.
- Applied linguistics and discourse-cohesion studies (2023–2024) addressing coherence in technical and instructional texts.
- Recent papers and workshop reports (2023–2026) on automated documentation quality and evaluation of model-generated content.

In short: use rhetoric-lint to turn Markdown — whether hand-written or machine-generated — into reliable, navigable documentation that fits into automated workflows and supports a stable docs architecture.