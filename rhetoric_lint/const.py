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
    "Completeness.ConceptOverload":     "Too many paragraphs of explanation appear before the first actionable step or structural element.",
    "Completeness.StructureLead":       "Section opens directly with a list or code block without a lead sentence explaining its purpose.",
    "Engine.OversizedDocument":         "Document exceeds NLP_MAX_CHARS; full-document NLP analysis was truncated. Section-level checks run on the complete file.",
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
    # New rules (Round 4)
    "Cohesion.TerminologyDrift": "suggestion",
    "Cohesion.AbandonedTopic": "suggestion",
    "Cohesion.MisusedConnective": "suggestion",
    "Completeness.ConceptOverload": "suggestion",
    "Completeness.StructureLead": "suggestion",
    "Engine.OversizedDocument": "suggestion",
}
