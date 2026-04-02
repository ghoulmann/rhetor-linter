# Linter vs. LLM Analysis: `testdoc.md`

**Document:** `testdoc.md` — MkDocs Installation guide (≈100 lines, ~600 tokens; instructional prose with code blocks)  
**Date:** 2026-03-11  
**Linter version:** rhetor-lint (all rules, `--min-severity suggestion`)

---

## 1. Linter Raw Output (all 11 findings)

| # | Line | Check | Severity | Message |
|---|------|-------|----------|---------|
| L1 | 3 | `Heading.InformationScent` | warning | H2 'Requirements' has no semantic overlap with doc H1 |
| L2 | 51 | `Heading.InformationScent` | warning | H2 'Installing MkDocs' has no semantic overlap with doc H1 |
| L3 | 1 | `Unity.HeadingTopicCoherence` | warning | Section heading and topic sentence weakly aligned (overlap 0.00) |
| L4 | 3 | `Unity.HeadingTopicCoherence` | warning | Section heading and topic sentence weakly aligned (overlap 0.00) |
| L5 | 22 | `Unity.TopicSectionDrift` | suggestion | Topic sentence drifts from later content (overlap 0.10) |
| L6 | 51 | `Unity.HeadingTopicCoherence` | warning | Section heading and topic sentence weakly aligned (overlap 0.00) |
| L7 | 7 | `Structure.TaskOrientation` | warning | Section 'Requirements' task density 0.00 < 0.30 |
| L8 | 53 | `Structure.TaskOrientation` | warning | Section 'Installing MkDocs' task density 0.00 < 0.30 |
| L9 | 71 | `attention.long_sentence` | warning | Long sentence (66 tokens) |
| L10 | 59 | `Cohesion.Break` | warning | Cohesion break between sentences |
| L11 | 61 | `Cohesion.Break` | warning | Cohesion break between sentences |

**Rules with zero findings:** `Heading.H1`, `Heading.Generic`, `Heading.VividScent`, `Unity.TopicSectionDrift` (most sections), `Symmetry.Parallelism`, `Symmetry.OrderedListImperatives`, `Rhetoric.ComplexitySpike`, `Rhetoric.ThroatClearing`, `Completeness.ResultVerification`, `Completeness.SchemaMapping`, `Structure.WallOfText`, `Navigation.FindabilityMap`, `Structure.ActionableHeadings`, `Cohesion.PronounDensity`, `Cohesion.PronounNounImbalance`

---

## 2. LLM Ground-Truth Analysis

Below is a manual, category-by-category assessment of `testdoc.md` using the same rule taxonomy.

---

### 2.1 Headings

#### `Heading.H1` — ❌ FALSE NEGATIVE (linter missed)
The document **has** an H1 ("MkDocs Installation"); `REQUIRE_H1=True` correctly suppressed the trigger. **No issue here — correctly silent.**

#### `Heading.Generic` — CORRECT SILENCE
- "Requirements", "Installing Python", "Installing pip", "Installing MkDocs" — none are from a generic-words list. These are specific and domain-relevant. Correct: no flag.

#### `Heading.VividScent` — CORRECT SILENCE
Headings use no weak verbs (get/make/do). "Installing" is a concrete action verb. Correct.

#### `Heading.InformationScent` (L1, L2) — ⚠️ FALSE POSITIVES

**LLM assessment:**
- "Requirements" as H2 under "MkDocs Installation" is contextually related: requirements are a natural prerequisite section of an installation guide. WordNet synset overlap between "MkDocs Installation" and "Requirements" will be low because "requirements" is generic, but the topical relationship is clear to any reader.
- "Installing MkDocs" as H2 under "MkDocs Installation" H1 is highly related — it directly contains the word "Installing" and is about MkDocs. This warning is a **clear false positive**. The H1 and H2 share a direct word ("MkDocs") and the same concept domain.

**Verdict:** Both findings are false positives. The synset-comparison method does not handle:
1. Single-word generic section names ("Requirements") that are structurally standard in documentation
2. Near-duplicate lexical overlap between H1 and H2 (sharing core keyword)

---

### 2.2 Unity

#### `Unity.HeadingTopicCoherence` (L3, L4, L6) — ⚠️ MIXED / FALSE POSITIVES

**LLM assessment per section:**

- **L3 (line 1, H1 "MkDocs Installation"):** The "topic sentence" the linter resolves is likely "A detailed guide." — which has zero content-word overlap with "MkDocs Installation." This is a byline / subtitle, not a topic sentence. The real introductory sentence is inside Requirements. The linter is being fooled by a decorative byline.

- **L4 (line 3, H2 "Requirements"):** First substantial sentence is "MkDocs requires a recent version of Python and the Python package manager, pip, to be installed on your system." This sentence actually has excellent content alignment with "Requirements" — it states what is required. The overlap score of 0.00 is almost certainly due to the topic sentence detection failing (possibly resolving to the wrong paragraph or the code block that follows). This is a **false positive**.

- **L6 (line 51, H2 "Installing MkDocs"):** First sentence is "Install the `mkdocs` package using pip." The heading is "Installing MkDocs." The word "mkdocs" appears in both, "install" is the lemma of "Installing." Overlap should be high but scores 0.00 — almost certainly a **tokenization/lemmatization failure** with code-formatted terms (`mkdocs` in backticks not being recognized as a content word).

**Verdict:** All three `Unity.HeadingTopicCoherence` warnings are false positives caused by two bugs:
1. Byline/subtitle ("A detailed guide.") being treated as the topic sentence for H1
2. Code-formatted words (backtick spans) being ignored in overlap computation

#### `Unity.TopicSectionDrift` (L5) — ✅ VALID (borderline)

**LLM assessment (line 22, H3 "Installing Python"):**  
Topic sentence: "Install Python using your package manager of choice, or by downloading an installer appropriate for your system from python.org and running it."  
Remaining content: Windows-specific NOTE blockquote about PATH.  
The drift (overlap 0.10) is real — the topic sentence discusses generic installation but the body is Windows-specific. However, this is a NOTE/blockquote which is a conditional aside, not a different topic. A human reader would not flag this as a structural problem.

**Verdict:** Borderline — technically detectable drift but not a real quality issue given the blockquote/conditional nature.

---

### 2.3 Symmetry

#### `Structure.TaskOrientation` (L7, L8) — ⚠️ FALSE POSITIVES

**LLM assessment:**
- Section "Requirements" (line 7): Contains prose + code blocks. Task density 0.00 because no list items. However, this section DOES have task-oriented code blocks (`$ python --version`, `$ pip --version`) and ends with a navigation link ("may skip down to..."). The section serves its purpose without a list. A requirements section in an install guide does not need a "task-based list" — it's a verification/check section.
- Section "Installing MkDocs" (line 53): Contains code blocks and prose. The entire section IS a sequence of tasks (install command, verify command). Not having a Markdown list doesn't mean it's non-task-oriented — the tasks are expressed through code fences.

**Verdict:** Both are false positives. The task-density metric counts list items but ignores code fences as bearers of task content. For technical documentation, code blocks are a primary vehicle for tasks.

#### `Symmetry.Parallelism` — CORRECT SILENCE  
The document has no unordered lists. Correct.

#### `Symmetry.OrderedListImperatives` — CORRECT SILENCE  
No ordered lists. Correct.

---

### 2.4 Rhetoric

#### `Rhetoric.ComplexitySpike` — CORRECT SILENCE  
Paragraphs are short and simple. Correct.

#### `Rhetoric.ThroatClearing` — CORRECT SILENCE  
Opening paragraphs are direct ("MkDocs requires...", "Install the `mkdocs` package..."). Correct.

---

### 2.5 Attention

#### `attention.long_sentence` (L9) — ✅ TRUE POSITIVE

**LLM assessment (line 71):** The offending sentence is:
> "For a more permanent solution, you may need to edit your `PATH` environment variable to include the `Scripts` directory of your Python installation."  
> + continuation: "Recent versions of Python include a script to do this for you. Navigate to your Python installation directory (for example `C:\Python38\`), open the `Tools`, then `Scripts` folder, and run the `win_add2path.py` file by double clicking on it."

The sentence is inside a blockquote and spans a Windows PATH explanation. At 66 tokens it is genuinely long and could be split. **True positive** — splitting into "Edit your PATH variable to include Scripts. Navigate to your Python directory..." would improve readability.

**Note:** The line number (71) points to the blockquote paragraph, which is correct.

---

### 2.6 Cohesion

#### `Cohesion.Break` (L10, L11) — ⚠️ FALSE POSITIVES

**LLM assessment (lines 59 and 61):**  
These lines are inside the "Installing MkDocs" section. Lines 59-61 correspond to:  
- (59) "You should now have the `mkdocs` command installed on your system."
- (60-61): Then a code block with `$ mkdocs --version` output.
- The "next sentence" is likely inside a NOTE blockquote: "If you would like manpages installed for MkDocs..."

The cohesion break is a **false positive caused by code block / blockquote boundary crossing**. The rule is measuring sentence-to-sentence overlap across a code fence boundary, which introduces a structural interruption that is not a rhetorical cohesion break. The NOTE block is a separate discourse unit (conditional aside), not a topic shift in flowing prose.

Additionally, "mkdocs" in backticks may not be lemmatized as a content word, eliminating what would otherwise be obvious lexical continuity.

**Verdict:** Both false positives caused by (a) code block boundaries not being treated as discourse unit breaks and (b) backtick-formatted words being dropped from content-word sets.

---

### 2.7 Completeness

#### `Completeness.ResultVerification` — ✅ TRUE NEGATIVE (correctly silent)
The "Installing MkDocs" section includes: "Run `mkdocs --version` to check that everything worked okay." This is an explicit verification step. Correct silence.

#### `Navigation.FindabilityMap` — CORRECT SILENCE
The document has ≤5 headings (H1×1, H2×2, H3×2 = 5 total). Threshold is ">5 headings." Correct silence.

#### `Structure.WallOfText` — CORRECT SILENCE
No prose block > 500 words. Correct.

#### `Completeness.SchemaMapping` — CORRECT SILENCE  
Not an API document. Correct.

---

### 2.8 Issues the LLM Found That the Linter Missed

| # | Category | Location | Description | LLM Severity |
|---|----------|----------|-------------|--------------|
| M1 | Redundancy | H1 + H2 | "MkDocs Installation" (H1) and "Installing MkDocs" (H2) are near-duplicate headings. Document-level heading uniqueness rule is absent. | suggestion |
| M2 | Unity | Doc level | Byline "A detailed guide." immediately after H1 is non-informative throat-clearing at the document level (no content words). | suggestion |
| M3 | Completeness | §Requirements | No explicit list of requirements (Python version, pip version) — stated as prose. A numbered/bulleted requirements list would be clearer/scannable. | suggestion |
| M4 | Cohesion | §Installing pip | Typo: "lasted version" should be "latest version." Lexical error. | warning |
| M5 | Attention | §Installing Python | Long blockquote with Windows note could be a dedicated sub-section for clarity. | suggestion |
| M6 | Cohesion | §Installing MkDocs | Two consecutive NOTE blockquotes are not explicitly linked — no connective between them (e.g., "Additionally," or "Also,"). | suggestion |
| M7 | Heading | H3 structure | H3s ("Installing Python," "Installing pip") live under H2 "Requirements" but are really installation sub-steps, not requirements. The document hierarchy conflates "what you need" with "how to get it." | suggestion |

---

## 3. Comparative Summary Table

| Finding | Linter | LLM | Verdict |
|---------|--------|-----|---------|
| `Heading.InformationScent`: "Requirements" | ⚠️ warning | No issue — standard doc pattern | **False Positive** |
| `Heading.InformationScent`: "Installing MkDocs" | ⚠️ warning | No issue — shares keyword with H1 | **False Positive** |
| `Unity.HeadingTopicCoherence`: H1 (byline) | ⚠️ warning | No issue — byline is not a topic sentence | **False Positive** |
| `Unity.HeadingTopicCoherence`: "Requirements" | ⚠️ warning | No issue — topic sentence well-aligned | **False Positive** |
| `Unity.HeadingTopicCoherence`: "Installing MkDocs" | ⚠️ warning | No issue — "mkdocs" in backticks | **False Positive** |
| `Unity.TopicSectionDrift`: "Installing Python" | suggestion | Borderline — blockquote is a conditional aside | **Borderline** |
| `Structure.TaskOrientation`: "Requirements" | ⚠️ warning | No issue — code blocks carry task content | **False Positive** |
| `Structure.TaskOrientation`: "Installing MkDocs" | ⚠️ warning | No issue — code fences are the tasks | **False Positive** |
| `attention.long_sentence` line 71 | ⚠️ warning | Real issue — 66-token sentence genuinely long | **True Positive** ✅ |
| `Cohesion.Break` line 59 | ⚠️ warning | No issue — code block boundary | **False Positive** |
| `Cohesion.Break` line 61 | ⚠️ warning | No issue — NOTE blockquote is separate discourse unit | **False Positive** |
| Typo "lasted version" (line 38) | — | Lexical error | **False Negative** |
| H1/H2 near-duplicate headings | — | Near-duplicate heading pair | **False Negative** |
| Byline "A detailed guide." | — | Non-informative byline | **False Negative** |
| Prose requirements list (M3) | — | Missing structured list | **False Negative** |
| No connective between NOTE blocks | — | Cohesion gap between blockquotes | **False Negative** |
| H3 misplaced under Requirements | — | Structural hierarchy issue | **False Negative** |

### Score

| Metric | Count |
|--------|-------|
| True Positives | 1 / 11 (9%) |
| False Positives | 9 / 11 (82%) |
| Borderline | 1 / 11 (9%) |
| False Negatives (missed by linter) | 6 |
| Precision | ~9–18% |
| Recall | ~14% (1 of 7 LLM issues caught) |

---

## 4. Root Cause Analysis

### RCA-1: Code-formatted tokens excluded from content-word sets

**Affects:** `Unity.HeadingTopicCoherence` (L6), `Cohesion.Break` (L10, L11)  
Backtick-wrapped tokens (`mkdocs`, `python`) are parsed as `Code` span nodes by mistletoe. The overlap engine (`overlap.py`) processes spaCy `Token` objects from the plain-text doc but the code spans may be stripped or replaced with a placeholder before spaCy processing, causing their content words to be invisible to overlap metrics.

### RCA-2: Byline / decorative subtitle misidentified as topic sentence

**Affects:** `Unity.HeadingTopicCoherence` (L3)  
`_first_substantial_sentence()` in `rules/unity.py` uses `_alpha_token_count(span) >= 3`. "A detailed guide." has 3 alpha tokens ("A", "detailed", "guide") — just barely passes the threshold. For H1 sections, the real topic sentence is not the subtitle but the first paragraph of the first section. The fix requires either raising the threshold or excluding the H1 section from heading-topic coherence checks (since H1 sections often contain only a subtitle/abstract).

### RCA-3: Task density metric ignores code fences

**Affects:** `Structure.TaskOrientation` (L7, L8)  
The metric is `list_items / (list_items + paragraphs)`. Code blocks are not counted as task-bearing content even though in technical documentation, fenced code blocks (`\`\`\`bash ... \`\`\``) are the primary form of task instruction. This systematically over-flags any technical document that uses code blocks instead of lists.

### RCA-4: Cohesion rule crosses code/blockquote discourse boundaries

**Affects:** `Cohesion.Break` (L10, L11)  
The `Cohesion.Break` rule measures adjacent sentence pairs in paragraph order. It does not respect code fence positions as discourse boundary markers. When a sentence precedes a code block and another sentence follows a code block (or a blockquote), they are treated as a direct sentence pair, masking the structural break between them.

### RCA-5: `Heading.InformationScent` uses pure synset overlap, ignoring lexical identity

**Affects:** `Heading.InformationScent` (L1, L2)  
The rule calls `get_synsets()` and computes set intersection. "MkDocs" is a proper noun/brand name with no WordNet synsets; "Installation" has synsets but "Requirements" and "Installing MkDocs" don't closely share them. Two fixes are needed:
1. **Lexical overlap fallback:** if H1 and H2 share a keyword (case-insensitive), downgrade the warning to a suggestion
2. **Level-gated standard section name handling:** standard names like "Requirements" are structurally valid at H2 — they rely on the H1 for topic context — but the same word as an H3 or H4 provides no navigational anchor for a reader or LLM chunk boundary. The fix must be _level-aware_, not a flat whitelist (see §5a below).

### RCA-6: No heading deduplication / near-duplicate detection

**Affects:** missed M1 (H1="MkDocs Installation" vs H2="Installing MkDocs")  
No rule checks whether two headings are near-duplicates of each other. This is a common documentation quality issue.

### RCA-7: No lexical error detection

**Affects:** missed M4 ("lasted version")  
The linter has no spell-check or n-gram fluency rule. This is out of scope for a structural linter but could be added as a lightweight `Fluency.SpellingError` rule using a dictionary lookup.

---

## 5a. Calibration Design Tension: Scannability and LLM Ingestion

Before specifying P1.1 and P1.2, we need to resolve a genuine design tension raised by the calibration review.

### The Case Against Flat Whitelisting

A blanket whitelist of standard section names ("Requirements", "Overview", "Introduction") suppresses the false positives in `testdoc.md`, but it creates a different problem: **generic headings are a real quality issue at certain heading levels**, for two audiences:

**Human readers scanning for relevance (JTBD context):**  
A reader scanning a documentation site ToC is looking for the entry point specific to their job to be done. Generic H3/H4 headings like "Overview", "Notes", "Requirements" with no topic qualifier provide no navigational information scent. The reader cannot distinguish "Requirements" under "Installing MkDocs" from "Requirements" under "Deploying on AWS" without reading parent context — which is not available in a ToC list, search result, or shared navigation. At H3 level and below, this directly harms time-to-value.

**LLM ingestion (RAG / semantic indexing):**  
RAG pipelines chunk documents at heading boundaries. The chunk label — the heading text itself — is the primary semantic anchor for retrieval. A chunk titled only "Requirements" will:
- Score low on specificity in embedding space (the word is semantically common across all domains)
- Miss recall for queries like "what Python version does MkDocs need?" if the heading gives no topic anchor
- Conflate with other "Requirements" chunks from different documents in a shared vector store

Modern pipelines may prepend breadcrumb context (H1 > H2 > H3), which partially mitigates this, but the heading text itself remains the primary retrieval signal in most implementations.

### The Heading-Level Resolution

The relationship between heading level and required semantic specificity is **asymmetric**:

| Level | Reader/LLM context available | Required specificity | `InformationScent` policy |
|-------|------------------------------|---------------------|--------------------------|
| **H1** | None — is the document title | Must be fully self-identifying | Always check; no suppression |
| **H2** | H1 title is in view (ToC, page header); chunk breadcrumb includes H1 | Standard structural names are acceptable when H1 is specific | Suppress warning for standard names at H2 only, under a specific H1 |
| **H3** | H1+H2 context visible in ToC, but often stripped in raw chunk/search extraction | Should include at least a topical qualifier | **Preserve the signal** — change message to an enrichment suggestion: "consider prepending the parent topic" |
| **H4+** | Context almost always lost in chunk/search extraction | Must be self-contained | Flag with enrichment suggestion; treat as H3 case |

### Consequence for P1.1 and P1.2

Neither a flat whitelist (P1.1 as originally framed) nor a pure lexical-identity suppression (P1.2 as originally framed) is correct. The two calibrations should be **combined and level-gated**:

- At **H2**: suppress `InformationScent` if the heading is a standard section name AND H1 is specific. This eliminates the false positive without hiding a real quality gap.
- At **H3+**: never suppress for standard names. Change the message from the current generic "no semantic overlap" to an actionable enrichment suggestion: _"Consider prepending the parent topic: 'MkDocs Requirements' instead of 'Requirements'."_
- At **all levels**: the **lexical fallback** (P1.2) should downgrade from `warning` to `suggestion` rather than suppress entirely. Lexical overlap with H1 is necessary but not sufficient for standalone scannability — an H2 heading still needs to work as an isolated ToC entry or RAG chunk label.

---

## 5. Calibration Plan

### Priority 1 — High Impact / Low Effort (false positive fixes)

#### P1.1 — Level-gated standard section name handling in `Heading.InformationScent`
**File:** `rules/headings.py`, `const.py`  
**Change:** Add `STANDARD_SECTION_NAMES` constant to `const.py`:
```python
STANDARD_SECTION_NAMES = {
    "requirements", "prerequisites", "overview", "introduction", "summary",
    "getting started", "installation", "setup", "configuration", "usage",
    "examples", "faq", "troubleshooting", "changelog", "contributing",
    "license", "references", "appendix", "notes", "conclusion", "features",
}
```
In `headings.py`, apply **level-gated logic** instead of a flat skip:
```python
h1_is_specific = h1 and len([t for t in nlp(h1["text"]) if t.is_alpha and not t.is_stop]) >= 2
if level == 2 and h1_is_specific and htext.lower().strip() in standard_section_names:
    continue  # H2 can rely on H1 as topic anchor — suppress
elif level >= 3 and htext.lower().strip() in standard_section_names:
    # H3+ with generic name: emit suggestion to enrich, then continue
    h1_topic_word = next(
        (t.text for t in nlp(h1["text"]) if t.is_alpha and not t.is_stop), ""
    ) if h1 else ""
    issues.append({
        "path": path, "line": line,
        "message": (
            f"Heading '{htext}' is a generic section name at H{level} — "
            f"consider adding a topic qualifier (e.g., '{h1_topic_word} {htext}') "
            f"to improve scannability and RAG chunk retrieval"
        ),
        "severity": "suggestion",
        "check": "Heading.InformationScent",
    })
    continue
```
**Effect at H2:** Eliminates L1 false positive ("Requirements" under "MkDocs Installation").  
**Effect at H3+:** Preserves the quality signal where standalone semantic clarity matters for ToC scanning, search results, and LLM ingestion.

#### P1.2 — Lexical fallback demoted to `suggestion` in `Heading.InformationScent`
**File:** `rules/headings.py`  
**Change:** After synset comparison fails, add a lexical overlap check. If the heading shares content-word lemmas with H1, **downgrade to `suggestion`** rather than suppressing — the contextual connection is real, but standalone clarity is still worth prompting:
```python
h1_content_lemmas = {t.lemma_.lower() for t in nlp(h1["text"]) if not t.is_stop and t.is_alpha}
h2_content_lemmas = {t.lemma_.lower() for t in doc if not t.is_stop and t.is_alpha}
if h1_content_lemmas & h2_content_lemmas:
    issues.append({
        "path": path, "line": line,
        "message": (
            f"H{level} '{htext}' is topically linked to the H1 but may read ambiguously "
            f"as a standalone heading (ToC entry or RAG chunk label) — "
            f"consider whether it identifies the topic clearly without its parent"
        ),
        "severity": "suggestion",  # downgraded from warning
        "check": "Heading.InformationScent",
    })
    continue
```
**Effect:** Eliminates L2 `warning` false positive while retaining a `suggestion` that correctly surfaces the question of standalone clarity. "Installing MkDocs" as H2 is fine and dismissible, but the nudge is valid for H2 headings that could appear in search or multi-doc ToCs.

#### P1.3 — Exclude H1 section from `Unity.HeadingTopicCoherence`
**File:** `rules/unity.py`  
**Change:** Skip the check for `sec.get("level") == 1`. The H1 section often has no body of its own (just a subtitle), and the "topic sentence" resolved is always the subtitle/byline:
```python
if sec.get("level", 0) == 1:
    continue
```
**Expected effect:** Eliminates L3 false positive.

#### P1.4 — Raise minimum alpha-token threshold for topic sentence detection
**File:** `rules/unity.py`  
**Change:** Increase `_alpha_token_count(span) >= 3` to `>= 6`. This prevents a 3-word byline like "A detailed guide." from being treated as the topic sentence.  
**Expected effect:** Eliminates L3 even if P1.3 is not applied; prevents similar false positives in other short subtitle lines.

#### P1.5 — Count `BlockCode` fences as task content in `Structure.TaskOrientation`
**File:** `rules/symmetry.py` (where `Structure.TaskOrientation` lives)  
**Change:** When computing task density, include code fence blocks as task-bearing content:
```python
code_blocks = len([p for p in section.get("paragraphs", []) if p.get("type") == "code"])
task_density = (list_items + code_blocks) / max(1, list_items + code_blocks + prose_paras)
```
**Expected effect:** Eliminates L7 and L8 false positives for technical documentation sections using code fences.

#### P1.6 — Respect discourse boundaries in `Cohesion.Break`
**File:** `rules/cohesion.py`  
**Change:** When building adjacent sentence pairs, skip sentence pairs that span a code block or blockquote boundary. The engine's section/paragraph data includes paragraph type; if the paragraphs containing S1 and S2 are separated by an intervening code/blockquote paragraph, treat them as non-adjacent:
```python
# Only pair sentences within the same paragraph
for para in section.get("paragraphs", []):
    if para.get("type") in ("code", "blockquote"):
        continue  # do not pair across these boundaries
    sentences = para.get("sentences", [])
    # pair consecutive sentences within this paragraph only
```
**Expected effect:** Eliminates L10 and L11 false positives.

---

### Priority 2 — Medium Impact / Medium Effort (false negative additions)

#### P2.1 — Add `Heading.NearDuplicate` rule
**File:** `rules/headings.py`  
**Check ID:** `Heading.NearDuplicate`  
**Logic:** For each pair of headings in the document, compute token-level Jaccard similarity of their content-word lemma sets. If similarity > 0.7, flag as near-duplicate:
```python
for i, h_a in enumerate(headings):
    for h_b in headings[i+1:]:
        lemmas_a = {t.lemma_.lower() for t in nlp(h_a["text"]) if t.is_alpha and not t.is_stop}
        lemmas_b = {t.lemma_.lower() for t in nlp(h_b["text"]) if t.is_alpha and not t.is_stop}
        if lemmas_a and lemmas_b:
            jaccard = len(lemmas_a & lemmas_b) / len(lemmas_a | lemmas_b)
            if jaccard >= 0.7:
                # flag h_b
```
**Example catch:** "MkDocs Installation" (H1) vs "Installing MkDocs" (H2) — shares "mkdocs" and "install" lemmas.

#### P2.2 — Include inline code tokens in overlap computation
**File:** `engine.py` and/or `overlap.py`  
**Change:** When building spaCy docs from section text, strip backtick delimiters but keep the textual content, so `mkdocs` in `` `mkdocs` `` is processed as a regular content token by spaCy.  
Alternatively, pre-process text with `re.sub(r'\`([^\`]+)\`', r'\1', text)` before NLP processing.  
**Expected effect:** Fixes `Unity.HeadingTopicCoherence` L6 and `Cohesion.Break` L10/L11 by surface-level fix.

#### P2.3 — Add `Cohesion.BlockquoteGap` rule
**Check ID:** `Cohesion.BlockquoteGap`  
**Logic:** When two consecutive blockquotes appear without a connective sentence between them, flag as potential cohesion gap. Check that the first sentence following a blockquote (or the sentence before the second one) contains a signposting connective from `SIGNPOSTS`.

#### P2.4 — Add `Heading.HierarchyMismatch` rule
**Check ID:** `Heading.HierarchyMismatch`  
**Logic:** Flag H3 headings that semantically belong under a different H2 than their parent. For `testdoc.md`, "Installing Python" and "Installing pip" are sub-headings of "Requirements" but semantically are installation steps, not requirements. This requires checking whether the H3 topic word set overlaps more with a sibling H2 than its parent H2.

---

### Priority 3 — Low Impact / Low Effort (threshold tuning)

#### P3.1 — Tune `Unity.TopicSectionDrift` threshold for blockquote-heavy sections
Add a configurable `UNITY_MAX_BLOCKQUOTE_RATIO` threshold. If a section's non-heading content is > 50% blockquotes, reduce the drift sensitivity (raise required overlap threshold) or skip the check, because blockquotes are by nature conditional/parenthetical content and drift is expected.

#### P3.2 — Tune `Heading.InformationScent` minimum heading length
Add minimum heading length (e.g., >= 2 content words) before triggering `InformationScent`. Single-word headings like "Requirements" have inherently low synset specificity.

#### P3.3 — Add `STANDARD_SECTION_NAMES` to configurable `const.py`
Allow users to extend the whitelist via the `-c config.json` option to add project-specific standard section names.

---

### Priority 4 — New Rule: Typo/Fluency Detection

#### P4.1 — `Fluency.CommonTypo`
**Check ID:** `Fluency.CommonTypo`  
**Logic:** Maintain a dictionary of common word-pair confusions:
```python
COMMON_TYPOS = {
    "lasted": "latest",
    "recieve": "receive",
    "occured": "occurred",
    # ...
}
```
Scan each token's text against the dictionary. Low overhead, high value.  
**Catches:** "lasted version" → "latest version" (M4 in this document).

---

## 6. Summary Recommendations Table

| ID | Change | Files | Fixes | Impact |
|----|--------|-------|-------|--------|
| P1.1 | Level-gated standard section name handling | `const.py`, `rules/headings.py` | L1 FP suppressed at H2; H3+ enrichment suggestion preserved | High |
| P1.2 | Lexical fallback demoted to suggestion | `rules/headings.py` | L2 downgraded warning→suggestion; standalone clarity still prompted | High |
| P1.3 | Skip H1 in HeadingTopicCoherence | `rules/unity.py` | L3 FP | High |
| P1.4 | Raise topic sentence min alpha threshold to 6 | `rules/unity.py` | L3 FP | High |
| P1.5 | Count code fences as task content | `rules/symmetry.py`, `engine.py` | L7, L8 FP | High |
| P1.6 | Don't pair sentences across code/blockquote | `rules/cohesion.py` | L10, L11 FP | High |
| P2.1 | Add `Heading.NearDuplicate` rule | `rules/headings.py`, `const.py` | M1 FN | Medium |
| P2.2 | Include inline code tokens in NLP | `engine.py` | L4, L6, L10, L11 | Medium |
| P2.3 | Add `Cohesion.BlockquoteGap` rule | `rules/cohesion.py` | M6 FN | Medium |
| P2.4 | Add `Heading.HierarchyMismatch` rule | `rules/headings.py` | M7 FN | Medium |
| P3.1 | Tune drift threshold for blockquote sections | `rules/unity.py`, `const.py` | L5 borderline | Low |
| P3.2 | Min heading length for InformationScent | `rules/headings.py` | FP reduction | Low |
| P3.3 | Make `STANDARD_SECTION_NAMES` configurable | `const.py` | UX | Low |
| P4.1 | Add `Fluency.CommonTypo` rule | new `rules/fluency.py` | M4 FN | Low |

---

*Analysis produced by rhetor-linter + LLM cross-validation on 2026-03-11.*

---

## 7. Concrete Implementation Plan

Scope: Priority 1 changes only (all false positive fixes). P2 items are noted as follow-on work.  
Implementation order is dependency-driven: constants first, then each rule file independently.

---

### Step 1 — `const.py`: Add `STANDARD_SECTION_NAMES` and register new severity entries

**Location:** end of file, after the `RULE_SEVERITY_LEVELS` dict.

**Add constant** (before `RULE_SEVERITY_LEVELS`):
```python
# Standard section names that are structurally valid at H2 level when the H1 is specific.
# At H3+, these names still trigger an enrichment suggestion (see Heading.InformationScent).
STANDARD_SECTION_NAMES = {
    "requirements", "prerequisites", "overview", "introduction", "summary",
    "getting started", "installation", "setup", "configuration", "usage",
    "examples", "faq", "troubleshooting", "changelog", "contributing",
    "license", "references", "appendix", "notes", "conclusion", "features",
}
```

**Add to `RULE_SEVERITY_LEVELS`** (the dict already exists; add these missing entries):
```python
"Heading.InformationScent": "warning",   # base severity; lexical fallback downgrades to suggestion
"Heading.NearDuplicate": "suggestion",
```

**Guard:** `STANDARD_SECTION_NAMES` must be a `set` (O(1) lookup), not a list.

**Verifiable state after this step:** `from const import STANDARD_SECTION_NAMES` works in the REPL with no import error.

---

### Step 2 — `rules/headings.py`: Rewrite the `InformationScent` block

**Target block** (current, lines ~130–148):
```python
        # Heading.InformationScent: for H2s, compare synsets with document H1
        if level == 2 and h1:
            try:
                h2_syn = get_synsets(htext) or set()
            except Exception:
                h2_syn = set()

            if h1_syn and h2_syn and h1_syn.isdisjoint(h2_syn):
                issues.append({ ... "check": "Heading.InformationScent" })
```

**Replace with the following logic** (full replacement of the `if level == 2 and h1:` block):

```python
        # Heading.InformationScent: check H2+ headings for topic connection to H1.
        # Three-stage pipeline: standard-name gate → synset check → lexical fallback.
        if level >= 2 and h1:
            standard_names = set(getattr(const, "STANDARD_SECTION_NAMES", [])) if const else set()
            h1_is_specific = nlp and len(
                [t for t in nlp(h1["text"]) if t.is_alpha and not t.is_stop]
            ) >= 2

            # Stage 1: Standard section name gate (level-aware)
            if standard_names and htext.lower().strip() in standard_names:
                if level == 2 and h1_is_specific:
                    # H2 under a specific H1: section name is structurally valid — suppress
                    pass  # fall through to next heading
                else:
                    # H3+: generic name without guaranteed parent context in ToC/RAG —
                    # emit enrichment suggestion instead of a synset warning
                    h1_topic_word = ""
                    if h1 and nlp:
                        h1_topic_word = next(
                            (t.text for t in nlp(h1["text"]) if t.is_alpha and not t.is_stop),
                            "",
                        )
                    issues.append({
                        "path": path,
                        "line": line,
                        "message": (
                            f"Heading '{htext}' is a generic section name at H{level} — "
                            f"consider adding a topic qualifier (e.g., "
                            f"'{h1_topic_word} {htext}') to improve scannability "
                            f"and RAG chunk retrieval"
                        ),
                        "severity": "suggestion",
                        "check": "Heading.InformationScent",
                    })
                continue  # handled — skip synset/lexical stages for this heading

            # Stage 2: Synset overlap check
            try:
                h_syn = get_synsets(htext) or set()
            except Exception:
                h_syn = set()

            if h1_syn and h_syn and not h1_syn.isdisjoint(h_syn):
                continue  # synset bridge found — no issue

            # Stage 3: Lexical fallback — shared content-word lemmas downgrade to suggestion
            if nlp and doc:
                h1_content_lemmas = {
                    t.lemma_.lower() for t in nlp(h1["text"]) if not t.is_stop and t.is_alpha
                }
                h_content_lemmas = {
                    t.lemma_.lower() for t in doc if not t.is_stop and t.is_alpha
                }
                if h1_content_lemmas & h_content_lemmas:
                    issues.append({
                        "path": path,
                        "line": line,
                        "message": (
                            f"H{level} '{htext}' is topically linked to the H1 via shared "
                            f"keywords, but may read ambiguously as a standalone heading "
                            f"(ToC entry or RAG chunk label) — consider whether it "
                            f"identifies the topic clearly without its parent context"
                        ),
                        "severity": "suggestion",  # downgraded from warning
                        "check": "Heading.InformationScent",
                    })
                    continue  # lexical bridge found — suppressed as warning

            # No synset or lexical bridge — emit original warning
            issues.append({
                "path": path,
                "line": line,
                "message": (
                    f"H{level} '{htext}' has no semantic overlap with the document H1 — "
                    f"consider adding context (e.g., keywords from the H1) to improve "
                    f"findability"
                ),
                "severity": (
                    const.RULE_SEVERITY_LEVELS.get("Heading.InformationScent", "warning")
                    if const else "warning"
                ),
                "check": "Heading.InformationScent",
            })
```

**Also add `Heading.NearDuplicate` check** immediately after the `for h in headings:` loop (as a post-loop step, still inside `check()`):

```python
    # Heading.NearDuplicate: flag heading pairs with high content-word Jaccard similarity
    if nlp:
        for idx_a, h_a in enumerate(headings):
            lemmas_a = {
                t.lemma_.lower() for t in nlp(h_a["text"]) if t.is_alpha and not t.is_stop
            }
            if not lemmas_a:
                continue
            for h_b in headings[idx_a + 1:]:
                lemmas_b = {
                    t.lemma_.lower() for t in nlp(h_b["text"]) if t.is_alpha and not t.is_stop
                }
                if not lemmas_b:
                    continue
                union = lemmas_a | lemmas_b
                jaccard = len(lemmas_a & lemmas_b) / len(union) if union else 0.0
                if jaccard >= 0.7:
                    b_line = _line_from_pos(text, h_b["pos"])
                    issues.append({
                        "path": path,
                        "line": b_line,
                        "message": (
                            f"Heading '{h_b['text']}' is near-duplicate of "
                            f"'{h_a['text']}' (Jaccard {jaccard:.2f}) — "
                            f"consider differentiating to aid navigation and RAG retrieval"
                        ),
                        "severity": (
                            const.RULE_SEVERITY_LEVELS.get("Heading.NearDuplicate", "suggestion")
                            if const else "suggestion"
                        ),
                        "check": "Heading.NearDuplicate",
                    })
```

**Expected outcome on `testdoc.md`:**
- L1 (`Heading.InformationScent`, line 3, "Requirements"): **suppressed** (H2, standard name, specific H1)
- L2 (`Heading.InformationScent`, line 51, "Installing MkDocs"): **downgraded to suggestion** (lexical bridge: "install"/"mkdocs" lemmas shared with H1)
- New: `Heading.NearDuplicate` suggestion on "Installing MkDocs" vs "MkDocs Installation" (Jaccard ≈ 1.0 on content lemmas)

---

### Step 3 — `rules/unity.py`: Skip H1 sections; raise topic-sentence threshold

**Change A — skip H1 sections** (`check()` function, inside the `for sec in sections:` loop):

Target the block:
```python
    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        if not heading or nlp is None:
            continue
```
Add immediately after the `if not heading or nlp is None: continue` line:
```python
        # H1 sections have no reliable topic sentence (often just a subtitle/byline)
        if sec.get("level", 0) == 1:
            continue
```

**Change B — raise minimum alpha-token count** (`_first_substantial_sentence()` function):

Current:
```python
            if _alpha_token_count(span) >= 3:
```
Change to:
```python
            if _alpha_token_count(span) >= 6:
```

**Rationale for 6:** "A detailed guide." has 3 alpha tokens and is the exact text causing the L3 false positive. Common short subtitles ("A brief overview.", "Quick reference.") top out at 4–5 alpha tokens. Any genuine topic sentence introducing technical content will have at least 6 content-bearing words.

**Expected outcome on `testdoc.md`:**
- L3 (`Unity.HeadingTopicCoherence`, line 1): **suppressed** (H1 section skipped by change A; byline also below new threshold from change B)
- L4 (`Unity.HeadingTopicCoherence`, line 3, "Requirements"): Needs separate investigation — the false positive here may be from the topic sentence ("MkDocs requires a recent version...") having zero content overlap due to RCA-1 (code-formatted tokens). **Not fixed by this step alone** — tracked as P2.2.
- L6 (`Unity.HeadingTopicCoherence`, line 51, "Installing MkDocs"): Same RCA-1 issue — also tracked as P2.2.

---

### Step 4 — `rules/symmetry.py`: Count code fences as task content in `Structure.TaskOrientation`

**Target block** in `check()`, the `Structure.TaskOrientation` section (current, approx lines 370–390):

```python
    for title, start, end, header_pos in section_spans:
        section_text = text[start:end].strip()
        if not section_text:
            continue

        # count list items in this section
        list_items = list(list_item_re.finditer(section_text))
        list_count = len(list_items)

        # count paragraphs: blocks of text separated by blank lines ...
        paras = 0
        for block in re.split(r"\n\s*\n+", section_text):
            ...
            paras += 1

        para_count = max(1, paras)
        td = list_count / para_count
```

**Changes:**

1. After computing `list_count`, add a fenced code block count:
```python
        # count fenced code blocks — in technical docs these carry task content
        # (e.g., shell commands, installation steps)
        code_fence_re = re.compile(r"^```.*?^```", re.M | re.DOTALL)
        code_count = len(code_fence_re.findall(section_text))
```

2. Change the density formula to include code blocks as task-bearing nodes:
```python
        # task_count = list items + code fences (both carry instructional content)
        task_count = list_count + code_count
        td = task_count / max(1, task_count + paras)
```

**Note:** `para_count` in the original code was `max(1, paras)` to prevent division by zero, but was used as the sole denominator. The new denominator `max(1, task_count + paras)` normalises across all block types.  
**Important edge case:** the existing paragraph-counting loop already skips code fences with `if re.match(r"^[#>\`~\-\*]", s)`. Verify this covers fenced blocks so they are not double-counted in `paras`. The regex `r"^[#>\`~\-\*]"` matches `` ` `` which is the first character of ```` ``` ```` — confirmed safe.

**Expected outcome on `testdoc.md`:**
- L7 (`Structure.TaskOrientation`, line 7, "Requirements"): "Requirements" section has 2 fenced code blocks, 2 prose paras → `td = 2/4 = 0.5 > 0.3` → **suppressed**
- L8 (`Structure.TaskOrientation`, line 53, "Installing MkDocs"): section has 3 fenced code blocks, 2 prose paras → `td = 3/5 = 0.6 > 0.3` → **suppressed**

---

### Step 5 — `rules/cohesion.py`: Skip `Cohesion.Break` across structural and blockquote paragraph boundaries

**Background:** `sent_records` is a flat list of 6-tuples:  
`(span, start_abs, ppos, ptext, block_type, prev_para_block_type)`

- `ppos` — character offset of the **paragraph** containing this sentence (unique per paragraph)
- `block_type` — type of the paragraph containing this sentence (`"Paragraph"`, `"BlockQuote"`, etc.)
- `prev_para_block_type` — type of the paragraph immediately before this sentence's paragraph in `sections[sec]["paragraphs"]`

The existing suppression gate (`has_connective AND _is_structural_block(prev_para_block_type)`) is too narrow — it only passes when a sentence arrives after a code/list block AND it carries an explicit connective. The fix: skip cross-paragraph pairs where the boundary involves a structural block **or** a blockquote (which functions as a callout/aside, not flowing prose).

**Target location:** in the `for i in range(1, len(sent_records)):` loop, immediately after the "Skip very short sentences" guard.

Insert after:
```python
            # Skip very short sentences
            if len([t for t in cur if t.is_alpha]) < 3:
                continue
```

Add:
```python
            # Skip sentence pairs that cross a structural or blockquote paragraph boundary.
            # Sentences spanning across code blocks or NOTE callouts do not need lexical
            # continuity — the structural break is intentional.
            _prev_ppos = sent_records[i - 1][2]
            _cur_ppos = sent_records[i][2]
            if _prev_ppos != _cur_ppos:  # cross-paragraph pair
                _prev_block = sent_records[i - 1][4]  # block_type of prev sentence's para
                _cur_block = sent_records[i][4]        # block_type of cur sentence's para
                if (
                    _is_structural_block(prev_para_block_type)  # structural block between paras
                    or "BlockQuote" in (_prev_block, _cur_block)  # either side is a callout
                ):
                    continue
```

**Remove the now-redundant gate** that currently appears later in the loop (since the broader skip above supersedes it):
```python
            # OLD — to be removed/left as-is (it remains harmless but unreachable for the cases above):
            if (
                has_connective
                and _is_structural_block(prev_para_block_type)
                and not has_high_divergence
            ):
                continue
```
Leave the old gate in place (it costs nothing and provides a safety net for edge cases not covered by the new check).

**Expected outcome on `testdoc.md`:**
- L10 (`Cohesion.Break`, line 59): sentence before code-fence + NOTE blockquote — `_is_structural_block(prev_para_block_type)` = True → **suppressed**
- L11 (`Cohesion.Break`, line 61): sentence from 1st NOTE blockquote paired with sentence from 2nd NOTE blockquote — `"BlockQuote" in (_prev_block, _cur_block)` = True → **suppressed**

---

### Step 6 — Validation

Run the full linter suite and verify the expected outcome against the target state:

```bash
cd /home/rik/github/rhetor-linter
source .venv/bin/activate
PYTHONPATH=. rhetoric-lint --format json --min-severity suggestion testdoc.md
```

**Target output after all changes** (expected remaining findings):

| Finding | Expected | Reason kept |
|---------|----------|-------------|
| `Heading.InformationScent` suggestion: "Installing MkDocs" | ✅ kept as suggestion | Lexical fallback — standalone clarity nudge |
| `Heading.NearDuplicate` suggestion: "Installing MkDocs" | ✅ new | Near-duplicate of H1 |
| `Unity.HeadingTopicCoherence` warning: line 3 "Requirements" | ⚠️ may persist | RCA-1 (backtick tokens) not yet fixed |
| `Unity.HeadingTopicCoherence` warning: line 51 "Installing MkDocs" | ⚠️ may persist | RCA-1 (backtick tokens) not yet fixed |
| `Unity.TopicSectionDrift` suggestion: line 22 | ✅ kept | Borderline — genuine drift signal |
| `attention.long_sentence` warning: line 71 | ✅ kept | True positive |

**Removed by this implementation:**
L1, L3, L7, L8, L10, L11 are fully suppressed.  
L2 is downgraded from `warning` to `suggestion`.

**Persist for P2 work:** L4, L6 (`Unity.HeadingTopicCoherence`) — require P2.2 (inline code token visible to NLP) to fully resolve.

---

### Step 7 — Run existing test suite

```bash
cd /home/rik/github/rhetor-linter
source .venv/bin/activate
PYTHONPATH=. python -m pytest tests/ -v 2>&1 | tail -40
```

All existing tests should pass. Any regressions indicate an over-broad change to the boundary logic — `Cohesion.Break` tests and `Unity` tests are the most likely to be affected by Steps 3 and 5.

---

### Implementation Checklist

- [ ] **Step 1** — `const.py`: add `STANDARD_SECTION_NAMES` set; add `Heading.InformationScent` and `Heading.NearDuplicate` to `RULE_SEVERITY_LEVELS`
- [ ] **Step 2** — `rules/headings.py`: replace `InformationScent` block with 3-stage pipeline; add `NearDuplicate` post-loop check
- [ ] **Step 3** — `rules/unity.py`: skip H1 sections (`level == 1`); raise alpha threshold to 6
- [ ] **Step 4** — `rules/symmetry.py`: count fenced code blocks in task density numerator
- [x] **Step 1** — `const.py`: add `STANDARD_SECTION_NAMES` set; add `Heading.InformationScent` and `Heading.NearDuplicate` to `RULE_SEVERITY_LEVELS`
- [x] **Step 2** — `rules/headings.py`: replace `InformationScent` block with 3-stage pipeline; add `NearDuplicate` post-loop check
- [x] **Step 3** — `rules/unity.py`: skip H1 sections (`level == 1`); raise alpha threshold to 6
- [x] **Step 4** — `rules/symmetry.py`: count fenced code blocks in task density numerator
- [x] **Step 5** — `rules/cohesion.py`: add cross-paragraph boundary skip for structural blocks and blockquotes
- [x] **Step 6** — run `rhetoric-lint` on `testdoc.md`; verified 8-finding output (§8 below)
- [x] **Step 7** — run `pytest tests/`; 36/36 tests pass

---

## 8. Post-Calibration Re-Assessment (Round 2)

**Date:** after all §7 Priority 1 changes applied  
**Command:** `PYTHONPATH=. rhetoric-lint --format text --min-severity suggestion testdoc.md`  
**Test suite:** 36/36 pass

---

### 8.1 Post-Calibration Linter Output

| # | Line | Check | Severity | Message (truncated) |
|---|------|-------|----------|---------------------|
| R1 | 22 | `Heading.InformationScent` | suggestion | H3 'Installing Python' ... topically linked to H1 via shared keywords, but may read ambiguously as standalone heading |
| R2 | 31 | `Heading.InformationScent` | suggestion | H3 'Installing pip' ... topically linked to H1 via shared keywords ... |
| R3 | 51 | `Heading.InformationScent` | suggestion | H2 'Installing MkDocs' ... topically linked to H1 via shared keywords ... |
| R4 | 3  | `Unity.HeadingTopicCoherence` | warning | Section heading and topic sentence are weakly aligned (content overlap 0.00) |
| R5 | 22 | `Unity.TopicSectionDrift` | suggestion | Section topic sentence drifts from later content (content overlap 0.10) |
| R6 | 51 | `Unity.HeadingTopicCoherence` | warning | Section heading and topic sentence are weakly aligned (content overlap 0.00) |
| R7 | 71 | `attention.long_sentence` | warning | Long sentence (66 tokens) — consider splitting |
| R8 | 61 | `Cohesion.Break` | warning | Local cohesion break: sentence appears unrelated to the previous sentence |

---

### 8.2 Precision/Recall Summary Across Both Rounds

| Metric | Round 1 (pre-calibration) | Round 2 (post-calibration) | Delta |
|--------|--------------------------|---------------------------|-------|
| Total findings | 11 | 8 | −3 |
| True Positives (definitive) | 1 | 3 | +2 |
| True Positives (borderline) | 1 | 2 | +1 |
| False Positives | 9 | 3 | −6 |
| Precision (strict) | 9% | **37.5%** | +28.5 pp |
| Precision (including borderlines) | 18% | **62.5%** | +44.5 pp |
| False Negatives (LLM issues missed) | 6 of 7 | 6 of 7 | 0 |
| Recall | ~14% | **~14%** | 0 |

Precision improved markedly; recall is unchanged because all new rules (NearDuplicate) failed to fire for a secondary reason detailed in §8.5.

---

### 8.3 Per-Finding Verdict Table

| Finding | LLM Verdict | Notes |
|---------|-------------|-------|
| **R1** L22 `InformationScent` suggestion "Installing Python" H3 | ✅ **Valid suggestion** | "Installing Python" is ambiguous standalone in multi-doc RAG or cross-doc ToC; enrichment suggestion is appropriate and dismissible |
| **R2** L31 `InformationScent` suggestion "Installing pip" H3 | ✅ **Valid suggestion** | Same reasoning as R1; "Installing pip" out of context could belong to any project |
| **R3** L51 `InformationScent` suggestion "Installing MkDocs" H2 | ⚠️ **Borderline** | "Installing MkDocs" is already self-identifying standalone (names both action and subject); the suggestion technically fires but adds marginal value for this specific heading. Over-sensitivity of the lexical bridge at H2. |
| **R4** L3 `HeadingTopicCoherence` warning "Requirements" | ❌ **False Positive** | Topic sentence "MkDocs requires a recent version of Python..." is perfectly aligned. Root cause: spaCy `'requirement'` (NN) ≠ `'require'` (VBZ) — see RCA-8 |
| **R5** L22 `TopicSectionDrift` suggestion "Installing Python" | ⚠️ **Borderline → FP** | Section body is a Windows-specific PATH NOTE blockquote, which is a platform-conditional extension of the topic — not a genuine drift. See P3.1 |
| **R6** L51 `HeadingTopicCoherence` warning "Installing MkDocs" | ❌ **False Positive** | Topic is "Install the `mkdocs` package using pip:" — directly aligned with heading. Root cause: spaCy lemmatizer inconsistency — see RCA-9 |
| **R7** L71 `attention.long_sentence` warning | ✅ **True Positive** | 66-token sentence inside Windows blockquote is genuinely long and should be split |
| **R8** L61 `Cohesion.Break` warning | ❌ **False Positive** | Two consecutive mkdocs-related sentences; cross-paragraph boundary skip suppressed L59 but L61 pair crosses a different boundary. Root cause: same spaCy lemma inconsistency as RCA-9 |

**Summary:**
- 3 definitive True Positives (R1, R2, R7)  
- 2 Borderline (R3, R5) — R3 leans FP, R5 is genuinely debatable  
- 3 definitive False Positives (R4, R6, R8)

---

### 8.4 Suppressed Findings — Confirmed Correct

The following Round 1 findings were suppressed by §7 changes and are confirmed as correct suppressions (i.e., the underlying documents have no real quality issue at those locations):

| Original Finding | Suppressed by | Verdict |
|-----------------|---------------|---------|
| L1 `Heading.InformationScent` warning "Requirements" | P1.1 — standard name H2 gate | ✅ Correct suppression |
| L3 `Unity.HeadingTopicCoherence` warning line 1 (H1 byline) | P1.3 — H1 section skip | ✅ Correct suppression |
| L7 `Structure.TaskOrientation` warning "Requirements" | P1.5 — code fences as task content | ✅ Correct suppression |
| L8 `Structure.TaskOrientation` warning "Installing MkDocs" | P1.5 — code fences as task content | ✅ Correct suppression |
| L10 `Cohesion.Break` warning line 59 | P1.6 — structural boundary skip | ✅ Correct suppression |
| Round 1 L2 `Heading.InformationScent` warning "Installing MkDocs" | P1.2 — lexical fallback downgraded | ✅ Downgraded to R3 suggestion (borderline, not suppressed) |

---

### 8.5 Remaining False Positive Root Causes

#### RCA-8: Unity rule lacks morphological stem bridge  
**Affects:** R4 (`Unity.HeadingTopicCoherence` line 3, "Requirements")

spaCy lemmatizes "Requirements" (NNS) → `'requirement'` (noun form) but "requires" (VBZ) → `'require'` (verb form). The Unity overlap check computes `containment_left` on exact lemma sets — `'requirement'` is not in the topic's lemma set `{'require', 'recent', 'version', 'python', 'packagemanager', 'pip', 'instal', 'system'}`, so overlap is 0.00 despite the words sharing the same Latin etymological root.

The headings rule already has a 6-char stem fallback (`l[:6]` for `len(l) >= 5`) added in Round 1. The Unity rule does not.

**6-char stem check:** `'requirement'[:6] = 'requir'`, `'require'[:6] = 'requir'` — match. Adding the same stem bridge to the Unity rule's overlap comparison would resolve R4.

**Fix location:** `rules/unity.py`, in the `section_coherence_metrics()` call or in the `_first_substantial_sentence()` block where heading vs. topic comparisons are performed. Specifically, after computing `h_lemmas & t_lemmas`, add a stem-overlap fallback: if direct lemma intersection is empty, check whether `{l[:6] for l in h_lemmas if len(l) >= 5}` intersects `{l[:6] for l in t_lemmas if len(l) >= 5}`.

**Candidate fix (in `rules/unity.py` `check()`, before emitting `HeadingTopicCoherence`):**
```python
# Existing check:
if containment <= WEAK_COHERENCE_THRESHOLD:
    # --- NEW stem fallback ---
    h_stems = {l[:6] for l in h_content_lemmas if len(l) >= 5}
    t_stems = {l[:6] for l in t_content_lemmas if len(l) >= 5}
    if h_stems & t_stems:
        continue  # stem bridge found — no issue
    # --- end stem fallback ---
    issues.append({ ... })
```

---

#### RCA-9: spaCy lemmatizer inconsistency for proper nouns and inflected forms  
**Affects:** R6 (`Unity.HeadingTopicCoherence` line 51, "Installing MkDocs") and R8 (`Cohesion.Break` line 61)

Two sub-issues compound here:

**Sub-issue A — VBG vs. VB form:**  
`"Installing"` (VBG, gerund) → spaCy lemma `'instal'`; `"Install"` (VB, base form) → spaCy lemma `'install'`. Same word, different surface form, different lemma. 6-char stems: `'instal'[:6] = 'instal'`, `'install'[:6] = 'instal'` — match. The stem fallback resolves this.

**Sub-issue B — Proper noun case and plural 's' stripping:**  
`"MkDocs"` (PROPN in heading) → spaCy lemma `'MkDocs'` (cased, unchanged); `"mkdocs"` (lowercase in body text, NOUN) → spaCy lemma `'mkdoc'` (trailing 's' stripped as apparent plural suffix). These two forms are recognized as different tokens.  
6-char stems: `'MkDocs'[:6].lower() = 'mkdoc'`, `'mkdoc'[:6].lower() = 'mkdoc'` — match, with case-folding.

For R8 (`Cohesion.Break`): S1 content lemmas `{'mkdocs', 'command', 'instal', 'system'}` vs. S2 `{'run', 'version', 'work', 'check', 'mkdoc'}`. With case-folded 6-char stems: `'mkdoc' ∈ stems(S1)` and `'mkdoc' ∈ stems(S2)` — stem bridge exists. The cohesion rule also lacks the fallback.

**Fix location:** `rules/cohesion.py`, in the token overlap computation used for `Cohesion.Break`. After direct lemma intersection fails, add case-folded 6-char stem fallback before concluding a cohesion break.

---

#### RCA-10: NearDuplicate Jaccard threshold too high for inflected-form duplicates  
**Affects:** false negative M1 ("MkDocs Installation" vs. "Installing MkDocs")

The `Heading.NearDuplicate` rule was implemented as specified. It computes Jaccard on content-word lemma sets and fires at ≥ 0.70. For the H1/H2 pair:
- H1 "MkDocs Installation": content lemmas `{'mkdocs', 'installation'}`
- H2 "Installing MkDocs": content lemmas `{'instal', 'mkdocs'}`
- Jaccard: `|{'mkdocs'}| / |{'mkdocs', 'installation', 'instal'}|` = **0.33** — below threshold

The near-duplicate relationship is missed because `'installation'` and `'instal'` are distinct lemmas (same root but different word forms; same RCA-9). With stem-normalized comparison, `'instal'[:6] = 'instal'` and `'installat'[:6] = 'instal'` — they share a 6-char stem. Adding case-folded steam normalization to NearDuplicate (the same bridge as RCA-8/RCA-9 fix) would raise the effective Jaccard above 0.70 for this pair.

---

### 8.6 Post–Round 2 Calibration Actions

These are the concrete follow-on actions needed to resolve the 3 remaining definitive false positives:

| ID | Priority | Change | File(s) | Target FP(s) Resolved |
|----|----------|--------|---------|----------------------|
| **P2.1-ext** | High | Add 6-char case-folded stem bridge to `Unity.HeadingTopicCoherence` overlap check | `rules/unity.py` | R4 (Requirements), R6 (Installing MkDocs) |
| **P2.2-cohesion** | High | Add 6-char case-folded stem bridge to `Cohesion.Break` local overlap check | `rules/cohesion.py` | R8 (Cohesion.Break line 61) |
| **P2.1-near-dup** | Medium | Apply same stem bridge in `Heading.NearDuplicate` Jaccard computation | `rules/headings.py` | M1 false negative (H1/H2 near-duplicate) |
| **P2.2-backtick** | Medium | Strip inline backtick delimiters before spaCy NLP pass | `engine.py` | R6 (secondary), R8 (secondary) — also needed for full RCA-9 fix |
| **P3.1** | Low | Attenuate `Unity.TopicSectionDrift` for blockquote-heavy sections | `rules/unity.py`, `const.py` | R5 (borderline TopicSectionDrift) |
| **P3.2** | Low | Add H2 lexical-bridge threshold: require ≥ 2 shared stems to fire suggestion | `rules/headings.py` | R3 (borderline InformationScent H2) |

**Recommended implementation order for Round 3:**  
P2.1-ext → P2.2-cohesion (both apply the same pattern as the existing headings.py stem bridge, lowest risk) → P2.1-near-dup → P2.2-backtick (requires engine change, highest risk, highest reward).

---

### 8.7 Outstanding False Negatives

No new LLM-identified issues were caught by the Round 2 changes. The false negative set is unchanged from §2.8:

| ID | Issue | Status |
|----|-------|--------|
| M1 | H1/H2 near-duplicate ("MkDocs Installation" vs "Installing MkDocs") | `Heading.NearDuplicate` implemented but Jaccard 0.33 < 0.70 threshold due to RCA-10 — fix via P2.1-near-dup |
| M2 | Non-informative byline "A detailed guide." | H1 section now skipped by P1.3; byline not separately flagged. Outstanding. |
| M3 | Requirements stated as prose rather than structured list | No dedicated rule. Outstanding. |
| M4 | Typo "lasted version" should be "latest version" | No fluency rule. Outstanding (P4.1). |
| M5 | Long Windows blockquote could be a sub-section | Partially overlaps with R7 (long_sentence at line 71). Structure refactoring not in scope. |
| M6 | No connective between consecutive NOTE blockquotes | No `Cohesion.BlockquoteGap` rule yet (P2.3). Outstanding. |
| M7 | H3 hierarchy mismatch under "Requirements" | No `Heading.HierarchyMismatch` rule yet (P2.4). Outstanding. |

---

### 8.8 Round 2 Verdict Snapshot

```
Pre-calibration:   11 findings  —  1 TP, 9 FP, 1 borderline  —  precision ~9%
Post-calibration:   8 findings  —  3 TP, 3 FP, 2 borderline  —  precision ~37–62%

Remaining FPs:   3  (root causes: morphological lemma divergence × 3)
Remaining FNs:   6  (root causes: missing rules × 5, low Jaccard × 1)
Next action:     add 6-char stem bridge to unity.py and cohesion.py (P2.1-ext, P2.2-cohesion)
```
