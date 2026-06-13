# Thresholds and simple linguistic dictionaries

# Unity: proportion of nouns required to form a coherent topic
UNITY_MIN_NOUN_RATIO = 0.05
UNITY_MIN_HEADING_TOPIC_CONTENT_OVERLAP = 0.2
UNITY_MIN_TOPIC_SECTION_CONTENT_OVERLAP = 0.15
UNITY_ENABLE_NOUN_DENSITY_FALLBACK = False

# Cohesion givenness thresholds
COHESION_MAX_PRONOUN_DENSITY = 0.35
COHESION_MAX_PRONOUN_NOUN_RATIO = 1.5
COHESION_MIN_REPEATED_CONTENT_RATIO = 0.2

# Attention: max tokens per sentence before flagging
MAX_SENTENCE_TOKENS = 45

# Headings: require a top-level H1
REQUIRE_H1 = True

# Simple pronoun list (for cohesion checks)
PRONOUNS = [
    "he",
    "she",
    "they",
    "we",
    "it",
    "this",
    "that",
    "these",
    "those",
]

# Signposting words grouped by rhetorical relation (TAACO-inspired categories)
SIGNPOSTS = {
    "sequential": [
        "first",
        "firstly",
        "second",
        "secondly",
        "next",
        "afterward",
        "afterwards",
        "then",
        "after",
        "finally",
        "in conclusion",
        "to conclude",
        "before",
        "subsequently",
    ],
    "adversative": [
        "however",
        "but",
        "although",
        "nevertheless",
        "on the other hand",
        "on the contrary",
        "in contrast",
        "by contrast",
        "even so",
        "all the same",
        "yet",
        "instead",
    ],
    "causal": [
        "because",
        "therefore",
        "thus",
        "consequently",
        "so",
        "as a result",
        "for this reason",
        "as a consequence",
        "which means",
        "hence",
    ],
    "additive": [
        "also",
        "further",
        "moreover",
        "in addition",
        "additionally",
        "what is more",
        "not only that",
        "along with this",
        "beyond that",
        "besides",
    ],
}

# Cohesion overlap/connective thresholds
COHESION_MIN_CONTENT_OVERLAP_STRONG = 0.2
COHESION_MIN_CONTENT_OVERLAP_WITH_CONNECTIVE = 0.08
COHESION_CONNECTIVE_WINDOW_TOKENS = 5

# Weak verbs mapping to more vivid alternatives (technical-writing friendly)
WEAK_VERBS = {
    "get": ["fetch", "retrieve", "obtain"],
    "do": ["perform", "execute", "carry out"],
    "make": ["create", "construct", "compose"],
    "check": ["verify", "validate", "inspect"],
    "have": ["contain", "include", "hold"],
}

# Generic heading tokens to detect non-descriptive sections
GENERIC_HEADINGS = [
    "overview",
    "introduction",
    "setup",
    "general",
    "notes",
    "miscellaneous",
    "generic",
]

# Task list identification patterns (for ordered list imperative checks)
TASK_LIST_KEYWORDS = [
    "how to",
    "steps",
    "procedure",
    "instructions",
    "deploy",
    "deploying",
    "install",
    "installing",
    "setup",
    "configure",
    "configuring",
]

# Patterns in text preceding a list that indicate task-oriented content
TASK_INTRO_PATTERNS = [
    "follow these steps",
    "to do this",
    "procedure",
    "instructions",
    "steps below",
    "do the following",
]

# Modal ambiguity (Rhetoric.ModalAmbiguity)
PRESCRIPTIVE_MODALS = ["must", "shall", "required", "have to", "need to", "has to", "needs to"]
ADVISORY_MODALS = ["should", "may", "might", "recommend", "consider", "optional"]

# Forward reference phrases (Cohesion.ForwardReference)
FORWARD_REFERENCE_PHRASES = [
    "as described above",
    "as mentioned above",
    "as shown above",
    "as outlined above",
    "in the previous section",
    "from the previous section",
    "the previous step",
    "from the earlier",
    "as we saw",
    "as we discussed",
    "per the above",
]

# Patterns that indicate descriptive/explanatory content (NOT task lists)
DESCRIPTIVE_LIST_PATTERNS = [
    "workflow is as follows",
    "workflow of",
    "pipeline is as follows",
    "pipeline works as follows",
    "process is as follows",
    "process works as follows",
    "benefits",
    "features",
    "components",
]

# Minimum list size for parallelism checking
MIN_LIST_SIZE_FOR_PARALLELISM = 4

# Standard section names that are structurally valid at H2 level when the H1 is specific.
# At H3+, these names still trigger an enrichment suggestion (see Heading.InformationScent).
# Extend via config: { "STANDARD_SECTION_NAMES": ["my-section", ...] }
STANDARD_SECTION_NAMES = {
    "requirements", "prerequisites", "overview", "introduction", "summary",
    "getting started", "installation", "setup", "configuration", "usage",
    "examples", "faq", "troubleshooting", "changelog", "contributing",
    "license", "references", "appendix", "notes", "conclusion", "features",
}

# Thresholds used across rules (tunable)
THRESHOLDS = {
    "PROPOSITIONAL_DENSITY": 0.6,
    "THROAT_CLEARING_SALIENCE": 0.8,  # stopword ratio above which throat-clearing is signaled
    "TASK_DENSITY_RATIO": 0.3,
    "MAX_NODE_DISTANCE": 3,
}

# ---------------------------------------------------------------------------
# Genre classification thresholds
# ---------------------------------------------------------------------------

# Set to True only after the validation corpus achieves per-genre F1 >= 0.78
GENRE_GATE_ENABLED = False

# Maximum characters passed to the full-document spaCy pipeline.
# The en_core_web_sm pipeline (parser + NER) uses ~1GB RAM per 100K chars;
# files larger than this threshold have their full-doc nlp() call truncated.
# Per-section/paragraph nlp() calls are unaffected and run on the full file.
NLP_MAX_CHARS = 500_000

# Structural density thresholds (relative to total paragraph blocks)
GENRE_CODE_FENCE_THRESHOLD = 0.08      # fraction of blocks that are code fences → technical
GENRE_TABLE_THRESHOLD = 0.03           # fraction of blocks that are tables
GENRE_BLOCKQUOTE_THRESHOLD = 0.02      # fraction of blocks that are blockquotes
GENRE_LIST_ITEM_THRESHOLD = 0.30       # fraction of blocks that are list items

# Citation density: matches per 1 000 chars
GENRE_CITATION_THRESHOLD = 0.04

# Heading structure thresholds
GENRE_NUMBERED_HEADING_THRESHOLD = 0.30   # fraction of headings that are numbered
GENRE_IMRAD_HEADING_MIN_MATCHES = 2       # number of IMRaD headings required → scientific

# Biber-derived linguistic thresholds
GENRE_NOMINALIZATION_THRESHOLD = 0.08    # fraction of alpha tokens with nominalizing suffix
GENRE_PASSIVE_THRESHOLD = 0.15           # fraction of alpha tokens with passive dependency

# ADR / Postmortem genre thresholds
GENRE_ADR_SECTION_MIN_MATCHES = 2        # ADR section headings required (with Status: line)
GENRE_POSTMORTEM_HEADING_MIN_MATCHES = 3 # postmortem headings required

# ---------------------------------------------------------------------------
# Deictic pronouns (used by Cohesion.DeicticGhost)
DEICTIC_PRONOUNS = {"this", "that", "these", "those"}

# Error-path keywords (used by Resilience.ErrorPathPresence)
ERROR_PATH_KEYWORDS = [
    "error", "fail", "failed", "failure", "exception",
    "troubleshoot", "troubleshooting", "common issue",
    "if this fails", "warning", "caution", "note:",
]

# ---------------------------------------------------------------------------
# Terminology consistency (Cohesion.TerminologyDrift)
TERMINOLOGY_MIN_TOKEN_LENGTH = 4
TERMINOLOGY_STEM_PREFIX_LEN = 6

# Lexical chain lifecycle (Cohesion.AbandonedTopic)
LEXICAL_CHAIN_MIN_EARLY_MENTIONS = 2
LEXICAL_CHAIN_EARLY_SECTION_COUNT = 2

# Discourse marker validation (Cohesion.MisusedConnective)
COHESION_ADVERSATIVE_MAX_OVERLAP = 0.4

# Concept-to-task ratio (Completeness.ConceptOverload)
COMPLETENESS_MAX_PROSE_BEFORE_ACTION = 3
COMPLETENESS_MAX_PROSE_ONLY_PARAGRAPHS = 5

# Minimum list items before a lead sentence is required (Completeness.StructureLead)
COMPLETENESS_STRUCT_LEAD_MIN_LIST_ITEMS = 3

# ---------------------------------------------------------------------------
# Rule descriptions (used by `rhetoric-lint rules` subcommand)
# ---------------------------------------------------------------------------
RULE_DESCRIPTIONS = {
    "Heading.H1":                       "Document is missing a top-level H1 heading.",
    "Heading.Generic":                  "Heading uses a generic name (overview, introduction, setup, etc.) that gives no content signal.",
    "Heading.VividScent":               "Heading language is weak or vague; a more specific heading would improve navigation.",
    "Heading.InformationScent":         "Heading gives no indication of what the section contains.",
    "Heading.NearDuplicate":            "Two headings are nearly identical (Jaccard ≥ 0.70), creating navigation ambiguity.",
    "Unity.HeadingTopicCoherence":      "Heading and topic sentence share too few content words; the section may not deliver what the heading promises.",
    "Unity.TopicSectionDrift":          "Topic sentence content words overlap poorly with the body; the section drifts from its stated topic.",
    "Unity.NounDensity":                "Noun ratio is below the minimum threshold, indicating thin or vague prose.",
    "Cohesion.GivennessBreak":          "High pronoun density without enough noun anchors; readers may lose referential track.",
    "Cohesion.Break":                   "Consecutive sentences share no discourse bridge (pronoun givenness, content overlap, signpost, lemma, or synset).",
    "Coherence.IslandSentence":         "Sentence is isolated — no lexical or discourse connection to surrounding text.",
    "Symmetry.Parallelism":             "List items do not share parallel grammatical structure.",
    "Symmetry.OrderedListImperatives":  "Steps in a task list do not begin with imperative verbs.",
    "Structure.TaskOrientation":        "Task-oriented section lacks imperative structure.",
    "Rhetoric.ComplexitySpike":         "Propositional density spikes sharply within a section, creating a comprehension cliff.",
    "Rhetoric.ThroatClearing":          "Section opens with a high-stopword sentence that delays the actual content.",
    "Attention.SplitAttention":         "Sentence exceeds the maximum token count, taxing working memory.",
    "Attention.Chunking":               "Paragraph is too long without structural breaks to aid chunking.",
    "Completeness.ResultVerification":  "Imperative section contains no verification step or expected output.",
    "Completeness.SchemaMapping":       "Section is missing expected structural elements for its apparent type.",
    "Structure.WallOfText":             "Long prose block with no lists, code fences, or headings to break it up.",
    "Navigation.FindabilityMap":        "Document lacks sufficient navigational structure (headings, anchors) for its length.",
    "Structure.ActionableHeadings":     "Headings are noun-only in a task-oriented document; verb-led headings would be clearer.",
    "Curriculum.MissingAssessment":     "Curriculum section has no assessment, exercise, or learning-check element.",
    "ADR.MissingStatus":                "ADR is missing a Status: field (e.g. 'Status: Accepted').",
    "ADR.MissingDecision":              "ADR is missing a Decision section.",
    "ADR.UndecidedStatus":              "ADR Status is Proposed/Draft but Decision section has no body.",
    "ADR.MissingConsequences":          "ADR is missing a Consequences, Trade-offs, or Impact section.",
    "Postmortem.MissingRootCause":      "Postmortem has no Root Cause or Contributing Factors section.",
    "Postmortem.MissingActionItems":    "Postmortem has no Action Items or Corrective Actions section.",
    "Postmortem.OpenActionItem":        "Action item has no assigned owner and no due date.",
    "Postmortem.MissingTimeline":       "Postmortem has no Timeline section.",
    # Topic types
    "Concept.ProcedureLeak":                "Concept section contains procedural steps — move to a How-To section.",
    "Troubleshooting.MissingRemediation":   "Troubleshooting section has no ordered remediation steps.",
    "Troubleshooting.UnorderedRemediation": "Troubleshooting remediation steps are in an unordered list; order matters.",
    "HowTo.NonImperativeStep":              "How-To step does not begin with an imperative verb.",
    "HowTo.UnorderedSteps":                 "How-To section uses an unordered list where a numbered sequence is required.",
    "FAQ.EmptyAnswer":                      "FAQ entry has no substantive answer.",
    "FAQ.NonQuestionEntry":                 "FAQ heading is not phrased as a question.",
    "Tutorial.NoObservationCues":           "Tutorial section has no feedback mechanism ('you should see', 'notice that', etc.).",
    "Tutorial.AlternativesDiversion":       "Tutorial offers alternative paths — tutorials must follow a single route.",
    "Reference.ContainsInstructions":       "Reference section contains procedural steps — move to a How-To section.",
    "Explanation.ContainsInstructions":     "Explanation section contains procedural steps — move to a How-To section.",
    "Explanation.NoConnections":            "Explanation section has no links to related concepts.",
    # Doc templates — Product Overview
    "ProductOverview.MissingOverview":      "Product Overview is missing an Overview or Introduction section.",
    "ProductOverview.MissingCapabilities":  "Product Overview is missing a Capabilities or Features section.",
    "ProductOverview.MissingUseCases":      "Product Overview is missing a Use Cases section.",
    "ProductOverview.ProcedureLeak":        "Product Overview contains procedural steps — link to a How-To instead.",
    # Doc templates — Architecture
    "Architecture.MissingOverview":         "Architecture doc is missing an Overview section.",
    "Architecture.MissingTechnicalDesign":  "Architecture doc is missing a Components or Technical Design section.",
    "Architecture.ProcedureLeak":           "Architecture doc contains procedural steps — all sections should be Concept type.",
    # Doc templates — Use Cases
    "UseCases.MissingOverview":             "Use Cases doc is missing an Overview section.",
    "UseCases.MultipleUseCasesInSection":   "Use Cases section describes multiple use cases — one use case per section.",
    # Doc templates — Onboarding
    "Onboarding.MissingOverview":           "Onboarding doc is missing an Overview section.",
    "Onboarding.MissingRequirements":       "Onboarding doc is missing a Requirements or Prerequisites section.",
    "Onboarding.MissingSteps":              "Onboarding doc is missing a How-To steps section.",
    # Doc templates — Quick Start
    "QuickStart.MissingOverview":           "Quick Start is missing an Overview section.",
    "QuickStart.MissingPrerequisites":      "Quick Start is missing a Prerequisites section.",
    "QuickStart.MissingCoreTask":           "Quick Start is missing a core task How-To section.",
    "QuickStart.MissingVerification":       "Quick Start is missing a Verify step — readers need confirmation that setup succeeded.",
    "QuickStart.MissingNextSteps":          "Quick Start is missing a Next Steps section.",
    # Doc templates — Platform Onboarding
    "PlatformOnboarding.MissingOverview":       "Platform Onboarding is missing an Overview section.",
    "PlatformOnboarding.MissingPrerequisites":  "Platform Onboarding is missing a Prerequisites section.",
    "PlatformOnboarding.MissingEnvSetup":       "Platform Onboarding is missing an Environment Setup section.",
    "PlatformOnboarding.MissingAuth":           "Platform Onboarding is missing an Authentication section.",
    "PlatformOnboarding.MissingWorkflow":       "Platform Onboarding is missing a Workflow section.",
    "PlatformOnboarding.MissingVerification":   "Platform Onboarding is missing a Verify step.",
    "PlatformOnboarding.MissingKeyConcepts":    "Platform Onboarding is missing a Key Concepts section.",
    "PlatformOnboarding.MissingNextSteps":      "Platform Onboarding is missing a Next Steps section.",
    "PlatformOnboarding.MissingTroubleshooting": "Platform Onboarding is missing a Troubleshooting section.",
    "Cohesion.DeicticGhost":            "Demonstrative pronoun (this/that/these/those) with no identifiable antecedent in the preceding sentences.",
    "Resilience.ErrorPathPresence":     "Procedural section has no failure guidance, troubleshooting note, or error scenario.",
    "Cohesion.TerminologyDrift":        "Different sections use different words for the same concept (e.g., 'endpoint' vs. 'route').",
    "Cohesion.AbandonedTopic":          "A key term introduced early in the document is never mentioned again in later sections.",
    "Cohesion.MisusedConnective":       "A transition word (e.g., 'however', 'therefore') does not match the actual relationship between sentences.",
    "Rhetoric.TrivializingLanguage":    "Prose uses trivializing language ('simply', 'just', 'easily', 'obviously', 'of course', 'straightforward') that implies the reader should find this easy, creating a face threat when they don't.",
    "Rhetoric.ModalAmbiguity":          "An ordered procedure list mixes prescriptive modals (must, shall, required) with advisory modals (should, may, recommend), making it unclear which steps are mandatory and which are optional.",
    "Cohesion.ForwardReference":        "Prose contains a backward-reference phrase ('as described above', 'in the previous section', etc.) that creates a linear dependency, preventing the section from functioning as a standalone entry point.",
    "Completeness.ConceptOverload":     "Too many paragraphs of explanation appear before the first actionable step or structural element.",
    "Completeness.StructureLead":       "Section opens directly with a list or code block without a lead sentence explaining its purpose.",
    "Engine.OversizedDocument":         "Document exceeds NLP_MAX_CHARS; full-document NLP analysis was truncated. Section-level checks run on the complete file.",
    "Rhetoric.UnresolvedContrast":      "A contrast signal (however, but, although, etc.) appears without a following resolution — the reader cannot determine the takeaway.",
    # SP9
    "Rhetoric.PassiveVoiceActorGap":    "Passive construction without an explicit by-agent. In instructional prose, actorless passives obscure who performs the step.",
    "Attention.SentenceRhythm":         "Section has monotonous or wildly uneven sentence-length pacing (high CV or extreme min/max ratio).",
    "Completeness.UnsupportedClaim":    "Assertion signal (therefore, this means, thus, etc.) not followed by evidence, an example, or a code sample within 2 sentences.",
    # SP12 — JTBD coverage
    "Coverage.MissingJobCoverage":      "A JTBD job detected by jtbd-tool has no documentation coverage in this file.",
    # SP20 — markdownlint extensions
    "Structure.StackedHeadings":        "Heading immediately follows another heading with no content between them (empty section).",
    "Structure.ListLeadColon":          "List block is not preceded by a sentence ending in a colon.",
    "Structure.ImageInTable":           "Image is embedded inside a table cell.",
    "Structure.SingleHeaderRow":        "Table has more than one GFM delimiter row; expected exactly one header separator.",
    # SP19 — Clarity Vale YAML pack
    "Clarity.NoPlease":                 "Avoid 'please' in technical documentation — it adds no information.",
    "Clarity.PositiveLanguage":         "Negative construction found — consider rephrasing positively to clarify what users can do.",
    "Clarity.NoGerundHeadings":         "Gerund heading detected — prefer a noun or imperative form for non-task sections.",
    "Clarity.HardCodedVersions":        "Hard-coded version number found — use a variable, placeholder, or changelog link instead.",
    "Clarity.HeadingSentenceCase":      "Heading is not sentence-cased — capitalize the first word only (proper nouns excepted).",
    "Clarity.HeadingLength":            "Heading exceeds 10 words — shorter headings improve navigation scannability.",
    "Clarity.NoQuestionHeadings":       "Question heading found outside a FAQ section — reserve question headings for FAQ docs.",
    "Clarity.ParagraphSentenceCount":   "Paragraph has more than 5 sentences — break into shorter paragraphs.",
    "Clarity.TableHeaderCase":          "Table header is not sentence-cased — capitalize the first word only (proper nouns excepted).",
}

# ---------------------------------------------------------------------------
# Rule severity mapping: error, warning, suggestion
RULE_SEVERITY_LEVELS = {
    # Errors (hard stops)
    "Coherence.IslandSentence": "error",
    "Completeness.ResultVerification": "error",
    # Warnings (quality concerns)
    "Heading.Generic": "warning",
    "Heading.InformationScent": "warning",
    "Structure.TaskOrientation": "warning",
    "Rhetoric.ComplexitySpike": "warning",
    "Structure.WallOfText": "warning",
    "Navigation.FindabilityMap": "warning",
    "Symmetry.Parallelism": "warning",
    "Symmetry.OrderedListImperatives": "warning",
    "Cohesion.GivennessBreak": "warning",
    # Suggestions (polish)
    "Heading.VividScent": "suggestion",
    "Heading.NearDuplicate": "suggestion",
    "Rhetoric.ThroatClearing": "suggestion",
    "Attention.SplitAttention": "suggestion",
    "Attention.Chunking": "suggestion",
    "Completeness.SchemaMapping": "suggestion",
    "Structure.ActionableHeadings": "suggestion",
    "Unity.HeadingTopicCoherence": "warning",
    "Unity.TopicSectionDrift": "suggestion",
    # Curriculum (genre-gated)
    "Curriculum.MissingAssessment": "suggestion",
    # ADR
    "ADR.MissingStatus":        "warning",
    "ADR.MissingDecision":      "error",
    "ADR.UndecidedStatus":      "warning",
    "ADR.MissingConsequences":  "warning",
    # Postmortem
    "Postmortem.MissingRootCause":   "error",
    "Postmortem.MissingActionItems": "error",
    "Postmortem.OpenActionItem":     "warning",
    "Postmortem.MissingTimeline":    "warning",
    # Topic types
    "Concept.ProcedureLeak":                "warning",
    "Troubleshooting.MissingRemediation":   "warning",
    "Troubleshooting.UnorderedRemediation": "warning",
    "HowTo.NonImperativeStep":              "suggestion",
    "HowTo.UnorderedSteps":                 "warning",
    "FAQ.EmptyAnswer":                      "warning",
    "FAQ.NonQuestionEntry":                 "suggestion",
    "Tutorial.NoObservationCues":           "suggestion",
    "Tutorial.AlternativesDiversion":       "warning",
    "Reference.ContainsInstructions":       "warning",
    "Explanation.ContainsInstructions":     "warning",
    "Explanation.NoConnections":            "suggestion",
    # Doc templates
    "ProductOverview.MissingOverview":      "warning",
    "ProductOverview.MissingCapabilities":  "warning",
    "ProductOverview.MissingUseCases":      "suggestion",
    "ProductOverview.ProcedureLeak":        "warning",
    "Architecture.MissingOverview":         "warning",
    "Architecture.MissingTechnicalDesign":  "warning",
    "Architecture.ProcedureLeak":           "warning",
    "UseCases.MissingOverview":             "warning",
    "UseCases.MultipleUseCasesInSection":   "suggestion",
    "Onboarding.MissingOverview":           "warning",
    "Onboarding.MissingRequirements":       "warning",
    "Onboarding.MissingSteps":              "error",
    "QuickStart.MissingOverview":           "warning",
    "QuickStart.MissingPrerequisites":      "warning",
    "QuickStart.MissingCoreTask":           "error",
    "QuickStart.MissingVerification":       "warning",
    "QuickStart.MissingNextSteps":          "suggestion",
    "PlatformOnboarding.MissingOverview":       "warning",
    "PlatformOnboarding.MissingPrerequisites":  "warning",
    "PlatformOnboarding.MissingEnvSetup":       "warning",
    "PlatformOnboarding.MissingAuth":           "warning",
    "PlatformOnboarding.MissingWorkflow":       "warning",
    "PlatformOnboarding.MissingVerification":   "warning",
    "PlatformOnboarding.MissingKeyConcepts":    "suggestion",
    "PlatformOnboarding.MissingNextSteps":      "suggestion",
    "PlatformOnboarding.MissingTroubleshooting": "warning",
    # Cohesion / Resilience
    "Cohesion.DeicticGhost": "warning",
    "Resilience.ErrorPathPresence": "warning",
    "Rhetoric.ModalAmbiguity": "warning",
    # New rules (Round 4)
    "Cohesion.TerminologyDrift": "suggestion",
    "Cohesion.AbandonedTopic": "suggestion",
    "Cohesion.MisusedConnective": "suggestion",
    "Rhetoric.TrivializingLanguage": "suggestion",
    "Cohesion.ForwardReference": "suggestion",
    "Completeness.ConceptOverload": "suggestion",
    "Completeness.StructureLead": "suggestion",
    "Engine.OversizedDocument": "suggestion",
    "Rhetoric.UnresolvedContrast": "suggestion",
    # SP8 — NLP rule expansion
    "Attention.SyntacticDepth": "suggestion",
    "Rhetoric.Nominalization": "suggestion",
    "Attention.MetricDensity": "suggestion",
    "Rhetoric.ToneImbalance": "suggestion",
    "Terminology.PreferredForm": "warning",
    "Symmetry.TabVariantBalance": "warning",
    # SP9 — ProsePartner gaps
    "Rhetoric.PassiveVoiceActorGap": "suggestion",
    "Attention.SentenceRhythm": "suggestion",
    "Completeness.UnsupportedClaim": "suggestion",
    # SP12 — JTBD coverage
    "Coverage.MissingJobCoverage": "warning",
    # SP20 — markdownlint extensions
    "Structure.StackedHeadings": "warning",
    "Structure.ListLeadColon": "suggestion",
    "Structure.ImageInTable": "warning",
    "Structure.SingleHeaderRow": "warning",
    # SP19 — Clarity Vale YAML pack
    "Clarity.NoPlease": "suggestion",
    "Clarity.PositiveLanguage": "suggestion",
    "Clarity.NoGerundHeadings": "suggestion",
    "Clarity.HardCodedVersions": "suggestion",
    "Clarity.HeadingSentenceCase": "suggestion",
    "Clarity.HeadingLength": "suggestion",
    "Clarity.NoQuestionHeadings": "suggestion",
    "Clarity.ParagraphSentenceCount": "suggestion",
    "Clarity.TableHeaderCase": "suggestion",
}

# ---------------------------------------------------------------------------
# Rhetoric.UnresolvedContrast (SP_CONTRAST)
# ---------------------------------------------------------------------------

CONTRAST_SIGNALS = [
    "however", "but", "although", "nevertheless", "on the other hand",
    "on the contrary", "in contrast", "by contrast", "even so", "yet",
    "despite", "nonetheless", "that said", "while", "whereas",
    "notwithstanding",
]

CONTRAST_RESOLUTION_SIGNALS = [
    "therefore", "thus", "so", "as a result", "consequently", "this means",
    "which means", "instead", "rather", "still", "ultimately", "in practice",
    "in fact", "the key point", "the solution", "to address this",
]

CONTRAST_UNRESOLVED_MAX_PER_PARA = 2
CONTRAST_MIN_SENTENCES = 3

# Body-NLP tiebreaker: imperative-sentence ratio threshold for howto detection
SECTION_IMPERATIVE_RATIO_HOWTO = 0.40

# ---------------------------------------------------------------------------
# SP9 — ProsePartner gaps
# ---------------------------------------------------------------------------

# Attention.SentenceRhythm
SENTENCE_RHYTHM_CV_MAX = 0.8
SENTENCE_RHYTHM_SPIKE_RATIO = 4.0
SENTENCE_RHYTHM_MIN_SENTENCES = 4

# Completeness.UnsupportedClaim
UNSUPPORTED_CLAIM_LOOKAHEAD_SENTENCES = 2
UNSUPPORTED_CLAIM_MAX_PER_PARA = 2

# ---------------------------------------------------------------------------
# Runner / style infrastructure (SP1)
# ---------------------------------------------------------------------------

# Directories to search for Vale-compatible style sets.
# Populated at runtime by --style-dir CLI flags or config key.
STYLE_DIRS: list = []

# Style names to enable (empty list = all styles in STYLE_DIRS).
# Populated at runtime by --style CLI flag or config key.
ENABLED_STYLES: list = []

# markdownlint integration toggle.  Set to False with --no-markdownlint.
MARKDOWNLINT_ENABLED: bool = True

# Path to a .markdownlint.json / .markdownlint.yaml config file.
# Empty string = auto-discover from the linted file's directory toward root.
MARKDOWNLINT_CONFIG: str = ""

# Path to an optional custom terminology JSON file (list of preferred terms).
# Empty string = disabled.
TERMINOLOGY_FILE: str = ""

# ---------------------------------------------------------------------------
# SP8 — NLP Rule Expansion thresholds
# ---------------------------------------------------------------------------

# Attention.SyntacticDepth — requires BOTH depth AND nested clause conditions
SYNTACTIC_DEPTH_MAX = 10
NESTED_CLAUSE_MAX = 4

# Attention.MetricDensity
METRIC_DENSITY_RATIO = 0.30
METRIC_DENSITY_WINDOW = 10
METRIC_DENSITY_WINDOW_MAX = 3
METRIC_DENSITY_MIN_TOKENS = 12

# Rhetoric.Nominalization
NOMINALIZATION_SUFFIXES = ("-tion", "-ment", "-ance", "-ity", "-ness")
# Common technical nouns that end in nominalization suffixes but are standard domain terms
NOMINALIZATION_EXCEPTIONS: list = [
    "application", "information", "condition", "conditions", "operation", "operations",
    "specification", "specifications", "transition", "transitions", "administration",
    "version", "versions", "location", "locations", "connection", "connections",
    "section", "sections", "option", "options", "function", "functions",
    "position", "positions", "definition", "definitions", "extension", "extensions",
    "action", "actions", "nation", "nations", "mention", "mentions",
    "intention", "attention", "convention", "conventions", "permission", "permissions",
    "documentation", "configuration", "authorization", "authentication",
    "representation", "presentation", "annotation", "annotations",
    "exception", "exceptions", "subscription", "subscriptions",
    "collection", "collections", "pagination", "transformation",
    "termination", "communication", "notification", "notifications",
    "integration", "integrations", "creation", "deletion", "generation",
    "evaluation", "iteration", "iteration",
    # -ment forms
    "statement", "statements", "environment", "environments", "requirement",
    "requirements", "management", "deployment", "deployments", "argument",
    "arguments", "fragment", "fragments", "alignment",
    # -ity forms
    "functionality", "availability", "visibility", "security", "priority",
    "validity", "immutability", "durability", "scalability", "reliability",
    "compatibility", "stability", "responsibility", "capability", "activity",
    "quality", "capacity", "community", "identity", "integrity",
    # -ance/-ence forms
    "performance", "reference", "references", "instance", "instances",
    "interface", "interfaces", "sequence", "sequences", "variance",
]

# Rhetoric.ToneImbalance
AUTHORITATIVE_MODALS: list = [
    "must", "shall", "required", "have to", "need to", "always", "never",
]
EMPATHETIC_SOFTENERS: list = [
    "may", "might", "can", "could", "consider", "suggest", "recommend", "optionally",
]
NEGATIVE_FRAMING: list = [
    "cannot", "can't", "won't", "will not", "do not", "don't", "never", "fail",
    "error", "invalid", "broken", "missing", "unable",
]
TONE_AUTHORITATIVE_MAX = 0.15   # fraction of alpha tokens
TONE_NEGATIVE_MAX = 0.20        # fraction of alpha tokens
TONE_INSTRUCTIONAL_GENRES = frozenset({"howto", "tutorial"})

# Symmetry.TabVariantBalance
TAB_VARIANT_STEP_TOLERANCE = 1

# ---------------------------------------------------------------------------
# F5 — Dimension → rule prefix mapping
# Five curated scoring dimensions. Rules are assigned by their check prefix.
# Vale YAML rules are bucketed under Style; readability YAML under Readability.
# ---------------------------------------------------------------------------

DIMENSION_MAP: dict = {
    "Clarity": [
        "Rhetoric",
        "Attention",
        "Cohesion",
        "Coherence",
    ],
    "Structure": [
        "Heading",
        "Symmetry",
        "Structure",
        "Navigation",
    ],
    "Completeness": [
        "Completeness",
        "Resilience",
        "Curriculum",
    ],
    "Style": [
        "Unity",
        "Lexical",
        "Terminology",
        # Vale YAML style rules (any check containing a dot-separated style prefix)
        "Rhetoric.TrivializingLanguage",
        "Rhetoric.Terminology",
        "Rhetoric.Inclusivity",
        "Rhetoric.InclusivityFlag",
        "Clarity.FleschReadingEase",
        "Clarity.Nominalizations",
        "Clarity.PrepositionalDensity",
    ],
    "Readability": [
        "Rhetoric.ReadabilityGrade",
        "Clarity.FleschReadingEase",
    ],
}

# Fallback dimension for rules not matched by any prefix above.
DIMENSION_DEFAULT = "Style"

# ---------------------------------------------------------------------------
# F2 — Frontmatter field aliases
# Canonical key → list of accepted aliases (all lowercased at parse time).
# ---------------------------------------------------------------------------

FRONTMATTER_ALIASES: dict = {
    "topic_type":  ["topic_type", "doctype", "doc_type", "type"],
    "sdlc_phase":  ["sdlc_phase", "sdlc", "phase"],
    "audience":    ["audience", "target_audience"],
    "owner":       ["owner", "team", "maintainer"],
    "author":      ["author", "authors"],
    "tags":        ["tags", "keywords", "labels"],
    "title":       ["title"],
}

# ---------------------------------------------------------------------------
# F4 — Scoring floor
# Documents below this word count suppress the quality badge.
# ---------------------------------------------------------------------------

SCORE_MIN_WORDS: int = 150

# ---------------------------------------------------------------------------
# SP12 — JTBD coverage integration
# ---------------------------------------------------------------------------

JTBD_MANIFEST_PATH: str = ""          # path to jtbd-manifest.json; empty = rule disabled
JTBD_COVERAGE_JACCARD_MIN: float = 0.30
