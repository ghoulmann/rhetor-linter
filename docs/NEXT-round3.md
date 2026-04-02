

## The Recommended Round 3 Action

### What it is

Add a **6-character case-folded morphological stem bridge** as a fallback in two places:

1. **unity.py** — in `check()`, immediately before emitting a `Unity.HeadingTopicCoherence` warning  
2. **cohesion.py** — in the `Cohesion.Break` detection loop, immediately before the synset bridge step

The same pattern already exists in headings.py and was added during Round 1 to fix H3 heading regressions. Round 3 extends it to the two remaining rules that still fail for the same underlying reason.

---

### Why it is needed

The three remaining false positives all share one root cause: **spaCy's lemmatizer produces divergent output for words that are obviously the same word to a human reader.** The overlap engine in overlap.py uses exact lemma comparison (`containment_left` and `set_overlap_metrics`). When the lemmas don't match character-for-character, overlap is scored 0.00 even when the words are morphologically identical.

The specific divergences are:

**Case 1 — Noun form vs. verb form (R4: "Requirements" ↔ "requires")**

| Surface | POS | spaCy lemma |
|---------|-----|-------------|
| `"Requirements"` (in heading) | NNS | `'requirement'` |
| `"requires"` (in topic sentence "MkDocs requires…") | VBZ | `'require'` |

`'requirement'` and `'require'` are different strings. `set_overlap_metrics` returns `containment_left = 0.00`. `heading_topic_content = 0.00 < 0.20` → false positive warning emitted.

With a 6-char stem: `'requirement'[:6] = 'requir'`, `'require'[:6] = 'requir'` → stem intersection is non-empty → no issue emitted.

**Case 2 — Gerund vs. infinitive + proper noun case (R6: "Installing MkDocs" ↔ "Install the `mkdocs` package")**

| Surface | POS | spaCy lemma |
|---------|-----|-------------|
| `"Installing"` (in heading) | VBG | `'instal'` |
| `"Install"` (in topic sentence) | VB | `'install'` |
| `"MkDocs"` (in heading) | PROPN | `'MkDocs'` (cased, preserved) |
| `"mkdocs"` (in body text, no backtick) | NOUN | `'mkdoc'` (trailing 's' stripped) |

The heading channel has content lemmas `{'instal', 'MkDocs'}`. The topic channel has `{'install', 'mkdoc', 'package', 'pip'}`. The intersection is empty. `containment_left = 0.00` → false positive.

With 6-char case-folded stems: `'instal'[:6] = 'instal'`, `'install'[:6] = 'instal'` → match. `'MkDocs'.lower()[:6] = 'mkdocs'`… actually `'MkDocs'` has 6 chars so `'mkdocs'`, and `'mkdoc'[:6] = 'mkdoc'` — these don't match on stem alone, but the `'instal'/'install'` bridge is sufficient to bring overlap above zero, resolving the false positive.

**Case 3 — Cohesion pair across `mkdocs` lemma inconsistency (R8: line 61)**

`_token_lemmas()` in cohesion.py builds `filtered_prev_lemmas` and `filtered_cur_lemmas`, then checks `filtered_prev_lemmas & filtered_cur_lemmas`. Current values:
- S1 `{'mkdocs', 'command', 'instal', 'system'}` (spaCy sees `"mkdocs"` in position 1 → lemma `'mkdocs'`)
- S2 `{'run', 'version', 'work', 'check', 'mkdoc'}` (spaCy sees `"mkdocs"` in position 2 → lemma `'mkdoc'`)

The intersection is empty because the same word `mkdocs` gets two different lemmas in two positions. The stem bridge: `'mkdocs'[:6] = 'mkdocs'`, `'mkdoc'[:6] = 'mkdoc'` — these are still different. However adding case-insensitive stem comparison with 5-char minimum: `'mkdocs'[:5] = 'mkdoc'`, `'mkdoc'[:5] = 'mkdoc'` → match.

**The exact stem length matters here.** A 6-char bridge resolves cases 1 and 2. For case 3, a 5-char bridge (or case-folding to `'mkdoc'` before slicing) is needed. The correct implementation is:

```python
stems = lambda lemmas: {l.lower()[:6] for l in lemmas if len(l) >= 5}
if stems(left_lemmas) & stems(right_lemmas):
    continue  # stem bridge found
```

`'mkdocs'.lower()[:6] = 'mkdocs'` and `'mkdoc'.lower()[:6] = 'mkdoc'` still differ (6 chars vs 5). But at length 5: `'mkdocs'[:5] = 'mkdoc'` and `'mkdoc'[:5] = 'mkdoc'` — match. So the minimum stem length should be **5** for the cohesion case, or the slice should be `[:5]` for all three applications for consistency.

---

### New Risks Introduced

#### Risk 1 — Over-bridging morphologically related but semantically distinct words

The stem bridge reduces precision of the overlap signal. A 5- or 6-char prefix match is a heuristic, not etymology. It will bridge:

| Word A | Word B | Stem | Intended? |
|--------|--------|------|-----------|
| `"install"` | `"installation"` | `'instal'` | ✅ yes |
| `"require"` | `"requirement"` | `'requir'` | ✅ yes |
| `"config"` | `"conflict"` | `'config'` | ✅ yes — same prefix, different words, **false bridge** |
| `"manage"` | `"manager"` | `'manage'` | ✅ yes |
| `"process"` | `"processor"` | `'proces'` | ✅ yes — borderline |
| `"report"` | `"reporter"` | `'report'` | ✅ yes — fine |
| `"contain"` | `"contaminate"` | `'contai'` (6) or `'conta'` (5) | ❌ false bridge at 5 chars |
| `"class"` | `"classic"` | `'class'` | ❌ false bridge — genuinely unrelated in many contexts |

The risk is concentrated in **short, high-frequency prefixes** — especially at 5 chars. A 6-char minimum mitigates most of the `class/classic` and `conta/contain` class of errors, while a 5-char minimum is needed only for `'mkdoc'/'mkdocs'` (a 4-char root plus one character). 

**Mitigation:** The bridge should only apply as a fallback — i.e., only when the direct lemma intersection is already zero. It does not lower an existing positive score; it only prevents a false zero. The worst-case scenario is preventing a genuine cohesion break from being flagged when two sentences share a coincidental prefix. Given that the rule already has the `GENERIC_TOKENS` blocklist and the signpost/synset checks, this added risk is modest.

#### Risk 2 — The `Heading.NearDuplicate` Jaccard threshold may now fire spuriously

The NearDuplicate check (added in Round 1) uses the same content-word lemma sets. If the stem bridge is applied consistently, the effective Jaccard between heading pairs increases — which is the desired effect for the "MkDocs Installation" / "Installing MkDocs" pair, but could also push other heading pairs above 0.70 if their stems happen to overlap. Documentation with section headings like "Configure" and "Configuration" would now appear as near-duplicates. Whether that is a spurious finding or a genuine quality signal is debatable — "Configure" and "Configuration" as two headings in the same document are arguably a real navigation problem, so the risk here is low.

#### Risk 3 — Increased sensitivity worsens recall for test documents with deliberate lexical variation

The `Unity.TopicSectionDrift` check uses the same `section_coherence_metrics` pipeline (via `topic_channels` and `body_channels`) but does **not** currently benefit from or use the stem bridge — the fix targets only `HeadingTopicCoherence`. However, if the stem bridge is applied inside `channelize_tokens` or `set_overlap_metrics` (i.e., at the overlap.py layer rather than post-hoc in each rule), it would also affect `TopicSectionDrift` and the cohesion givenness checks.

**This is the primary architectural decision for Round 3:** the bridge can be applied:

- **Layer A — inside overlap.py**: centrally, affecting all overlap metrics everywhere. **Maximum reach, highest risk of unintended side effects** on rules that are currently well-calibrated.
- **Layer B — inside each rule's comparison site** (post `channelize_tokens`, before emitting an issue): surgical, rule-specific, no risk to other rules. **This is the correct approach for Round 3.**

If implemented at Layer B only, the risk surface is bounded to exactly the three emission sites being changed.

#### Risk 4 — Test suite coverage gap for stem-bridge scenarios

The existing 36 tests do not include a test case where the correct outcome depends on the stem bridge firing. After Round 3, a regression would be invisible to the current suite. New tests need to be added covering:
- A heading/topic pair where the heading uses a noun form and the topic uses a verb form of the same word
- A cohesion sentence pair where the same proper noun has inconsistent spaCy lemmatization across positions

Without these, a future refactor that removes or changes the stem bridge would not be caught by CI.


## COunterpoint

Weigh this

This is a rigorous and highly professional assessment. You have correctly identified the technical friction between **spaCy’s lemmatization logic** and the **deterministic requirements** of your linter.

Your logic regarding the "Stem Bridge" is sound. In documentation, we often transition from a noun-heavy heading (*Requirements*) to a verb-heavy topic sentence (*Requires...*). Relying on a standard lemmatizer to bridge that gap is risky because, as you noted, `requirement` and `require` are distinct tokens in most NLP pipelines.

### Critical Feedback on your Assessment

#### 1. The "Case 3" (MkDocs vs. MkDoc) Edge Case

Your observation that `mkdocs` lemmatizes differently based on position is a classic "stochastic ghost" in NLP.

* **The 5 vs. 6 Character Dilemma:** You noted that a 6-char stem fails case 3, but a 5-char stem increases "false bridge" risks (e.g., `conta` matching `contain` and `contaminate`).
* **The Better Fix:** Instead of lowering the global stem minimum to 5, you might consider a **Term-Specific Normalization** list or a "Custom Dictionary" for the `rhetor-linter`. If "MkDocs" is a core keyword for the project, it should likely be protected from the lemmatizer or mapped to a canonical form before the overlap check.

#### 2. Risk 3: Layer A vs. Layer B Architecture

Your decision to implement this at **Layer B (Rule-Specific)** is the correct architectural choice for this stage of development.

* **Rationale:** Moving this to Layer A (overlap.py) would essentially "blind" your linter to the subtle differences between word forms across all rules. By keeping it at Layer B, you preserve the high-fidelity signal for rules that might actually care about the difference between a noun and a verb, while solving the "false zero" problem for Unity and Cohesion.

#### 3. Risk 4: The Coverage Gap

You are spot on here. Without **Regression Tests** that specifically use "Requirement/Requires" pairings, a future update to spaCy or a change in your `stems` lambda will break this fix without warning.

---

### Refined Implementation Suggestion

To mitigate the **Stem Length Risk** while still catching the `mkdoc/mkdocs` inconsistency, you could use a "Fuzzy Stem" approach in your Layer B implementation:

```python
def has_stem_match(lemmas_a, lemmas_b, min_len=5, slice_len=6):
    # Filter for meaningful length to avoid 'the'/'then' type collisions
    stems_a = {l.lower()[:slice_len] for l in lemmas_a if len(l) >= min_len}
    stems_b = {l.lower()[:slice_len] for l in lemmas_b if len(l) >= min_len}
    return bool(stems_a & stems_b)

```

### Summary Assessment

| Factor | Rating | Note |
| --- | --- | --- |
| **Technical Depth** | High | Excellent identification of lemmatization divergence. |
| **Risk Management** | Proactive | Risk 1 (False Bridges) is the most likely "noisy" outcome. |
| **Architecture** | Solid | Layer B placement prevents global "precision rot." |

**Verdict:** Proceed with Round 3, but I strongly recommend adding the **Regression Tests** identified in Risk 4 simultaneously with the code change.


## Missed Opportunities



Based on your current architectural focus on **Semantic Quality Engineering (SQE)** and the "Normalization Hub," there are several high-value rhetorical and structural signals that your current `rhetor-linter` suite is overlooking.

While the "Stem Bridge" in Round 3 fixes technical noise, these "Missed Opportunities" represent a shift from **lexical overlap** to **functional flow**.

---

### 1. The "Dead-End" Section (Action-Result Gap)

Currently, you check if a heading and a topic sentence match. You do **not** check if a section that starts with an instruction (e.g., "Install the package") actually contains the expected outcome (e.g., a code block or a verification step).

* **The Check:** `Logic.ResultVerification`
* **The Logic:** If a section contains an imperative verb in the H2/H3 or topic sentence, the linter should look for a "Success State" (a terminal output example or a `check --version` command).
* **Value:** Prevents "The Missing Step" syndrome in technical docs.

### 2. Rhetorical "Velocity" (Sentence Complexity Gradient)

Technical documentation is most effective when it follows a "Simple-to-Complex" curve.

* **The Check:** `Flow.ComplexityGradient`
* **The Logic:** Analyze the mean dependency tree depth or token count of sentences within a section.
* *Pass:* The first two sentences (conceptual) are short; later sentences (technical nuance) are longer.
* *Fail:* A section begins with a 40-token "wall of text" and ends with 5-token fragments.


* **Value:** Measures "onboarding" quality for a human reader.

### 3. Deictic Ghosting (Referential Integrity)

As noted in your Cohesion Break false positive, your tool struggles with words like "the above," "these," or "it."

* **The Check:** `Cohesion.AnaphoraResolution`
* **The Logic:** Instead of just looking for lemma overlap, flag any sentence that starts with a demonstrative pronoun (*This*, *That*, *These*, *Those*) if there is no high-probability antecedent in the previous 2 sentences.
* **Value:** Detects "Dangling Context," which is a nightmare for **RAG chunking** where "the above" might refer to content in a completely different database chunk.

### 4. Taxonomy-to-Heading Drift

You are building a "Documentation Normalization Hub." You likely have a project taxonomy (e.g., "Installation," "Configuration," "Deployment").

* **The Check:** `Architecture.TaxonomyAlignment`
* **The Logic:** Compare H2/H3 headings against a "Controlled Vocabulary" or the directory structure.
* **Value:** If a file is in `/install/` but has no H2 containing "Install" or "Setup," it indicates a structural mismatch that complicates automated migration to Backstage TechDocs.

### 5. Code-Text Asymmetry

Your current linter treats Markdown and code blocks as somewhat separate entities for overlap.

* **The Check:** `Unity.CodeProseAlignment`
* **The Logic:** Extract variable names or CLI flags from code blocks (e.g., `mkdocs`, `win_add2path.py`) and check if they appear in the surrounding prose.
* **Value:** If a code block introduces a new tool or flag that isn't mentioned in the text, it creates a "Cognitive Jump" for the user.

---

### Comparison of Current vs. Future State

| Feature | Current `rhetor-linter` | Proposed Opportunity |
| --- | --- | --- |
| **Logic** | Lexical overlap (Lemmas) | Functional Intent (Instruction -> Result) |
| **Cohesion** | Sliding window overlap | Referential mapping (Anaphora) |
| **Structure** | Heading/Topic alignment | Global Taxonomy consistency |
| **Context** | Single-file focus | **RAG-readiness** (Chunk autonomy) |

### Strategic Recommendation: The "Chunk Autonomy" Score

Since you are migrating to **Backstage TechDocs**, the biggest missed opportunity is a metric for **Chunk Autonomy**. This would calculate how well a single H2/H3 section functions as a standalone piece of information. If a section has high "Information Scent" but high "Deictic Ghosting" (uses "this" and "above" too much), it is a **Bad Chunk** for an AI agent or a TUI dispatcher.

**Would you like me to focus on the logic for the "Deictic Ghosting" check as an alternative to the Stem Bridge for Round 3?**


### MOre exetnsion

Additional features can extend the system from **local rhetorical linting** to **document cognition engineering**—measuring whether a technical document behaves like a navigable knowledge system rather than a collection of paragraphs. The following ideas expand the current model while remaining compatible with a **Semantic Quality Engineering (SQE)** pipeline and a normalization hub architecture.

---

## 1. Intent–Artifact Closure

Many technical sections implicitly promise an artifact (file, output, environment change) but never confirm its creation.

**Check:** `Logic.IntentArtifactClosure`

**Logic**

1. Detect verbs indicating artifact creation or modification:

   * create, generate, write, build, deploy, initialize
2. Extract the expected artifact from the clause:

   * file names, directories, services, environment variables
3. Scan the remainder of the section for:

   * file paths
   * terminal output
   * verification commands
   * screenshots or expected structure

**Fail Pattern**

```
Create a configuration file for mkdocs.

[no example file or path shown]
```

**Value**

Prevents instructions that produce invisible state changes.

This check measures **procedural completeness**, which is a common failure mode in technical documentation.

---

## 2. Dependency Reveal Score

Many docs reference prerequisites without declaring them clearly.

**Check:** `Structure.DependencyReveal`

**Logic**

Detect references to tools or concepts that appear before they are introduced in the document.

Algorithm outline:

1. Extract all tool names and key nouns.
2. Track first occurrence positions.
3. Flag sentences where a dependency appears before introduction.

Example:

```
Run vale on the repository.
```

If **Vale** was never introduced earlier, the section fails.

**Value**

Improves:

* onboarding clarity
* chunk-level independence
* RAG retrieval accuracy

---

## 3. Procedural State Machine Integrity

Installation or configuration instructions usually represent a **state machine**, but documentation rarely checks whether the sequence actually forms one.

**Check:** `Procedure.StateContinuity`

**Logic**

Map procedural steps to implied system states.

Example:

```
Install package
Configure file
Restart service
Verify installation
```

Rules:

* Configuration should not occur before installation.
* Verification must follow the action being verified.
* Restart implies a running service.

Detect impossible sequences:

```
Verify installation
Install package
Restart service
```

**Value**

Prevents logically inconsistent tutorials.

---

## 4. Narrative Compression Ratio

Technical writing often oscillates between **dense theory** and **overly compressed steps**.

**Check:** `Flow.NarrativeCompression`

**Logic**

Measure the ratio of:

```
concept sentences / instruction sentences
```

Healthy ranges depend on section type.

Examples:

| Section Type | Ideal Ratio |
| ------------ | ----------- |
| Tutorial     | 0.3–0.5     |
| Explanation  | 1.5–3       |
| Reference    | <0.2        |

**Value**

Ensures a tutorial does not drift into an essay.

---

## 5. Semantic Heading Predictability

Good headings allow readers (or agents) to predict the structure of the section before reading it.

**Check:** `Structure.HeadingPredictability`

**Logic**

Compare the semantic vector of the heading to the centroid of the section text.

Fail if similarity is below threshold.

Example:

Heading:

```
Advanced Configuration
```

Section text:

```
Install mkdocs
pip install mkdocs
```

Mismatch indicates heading drift.

**Value**

Improves **information scent** in navigation systems.

---

## 6. Concept Reintroduction Penalty

Documentation frequently re-explains concepts multiple times across files.

**Check:** `Knowledge.ConceptReintroduction`

**Logic**

Across the documentation corpus:

1. Track concept definitions
2. Detect repeated definitions in later documents

Example:

```
MkDocs is a static site generator...
```

If the same definition appears in multiple files, flag redundancy.

**Value**

Encourages **reference linking instead of duplication**, improving maintainability.

---

## 7. Interface Surface Coverage

When documentation describes a tool, it should cover its interface consistently.

**Check:** `Reference.InterfaceCoverage`

**Logic**

If the text references CLI flags or parameters:

1. Extract all flags from code blocks
2. Count how many are explained in prose
3. Measure explanation coverage

Example:

```
mkdocs build --clean --strict
```

If neither `--clean` nor `--strict` are explained, coverage is low.

**Value**

Improves **reference completeness**.

---

## 8. Cognitive Jump Distance

Readers struggle when the document leaps too far between concepts.

**Check:** `Flow.ConceptDistance`

**Logic**

Track semantic similarity between consecutive paragraphs.

Large drops indicate abrupt transitions.

Example failure:

```
Paragraph 1: MkDocs installation
Paragraph 2: Kubernetes deployment
```

**Value**

Detects **topic discontinuities**.

---

## 9. Error Path Presence

Robust technical instructions include failure scenarios.

**Check:** `Resilience.ErrorPathPresence`

**Logic**

Search for indicators such as:

* error
* failed
* troubleshooting
* common issues
* if this fails

Sections with procedural steps but no failure guidance score poorly.

**Value**

Encourages resilient documentation.

---

## 10. Retrieval Anchor Density

This directly improves RAG behavior.

**Check:** `Retrieval.AnchorDensity`

**Logic**

Count high-signal tokens:

* tool names
* commands
* configuration keys
* file paths

If a section contains mostly generic language, retrieval quality degrades.

Example weak chunk:

```
Run the command above to configure the system.
```

Example strong chunk:

```
Run mkdocs serve to start the development server.
```

**Value**

Improves chunk retrievability in embedding indexes.

---

# Higher-Level Metric: Document Operationality

A new composite metric could evaluate how **operational** documentation is.

```
Operationality Score =
  ProcedureIntegrity
+ ArtifactClosure
+ InterfaceCoverage
+ ErrorPathPresence
```

High scores indicate documentation that can be **executed**, not just read.

---

# Possible Next-Layer Feature (Novel)

### "Executable Documentation Probability"

The linter estimates whether a section could be converted into a **fully automated script**.

Signals include:

* deterministic commands
* explicit file paths
* verification steps
* absence of ambiguous pronouns

High score:

```
git clone repo
cd repo
pip install -r requirements.txt
pytest
```

Low score:

```
Run the command above and configure things as needed.
```

This metric would align strongly with **documentation-as-code** and **DevEx automation pipelines**.

---

If useful, the next expansion could cover **system-level metrics** for the normalization hub, such as:

* Documentation **graph topology scoring**
* **Knowledge fragmentation detection**
* **RAG chunk entropy**

Those extend the linter from file-level analysis to **repository-scale documentation architecture analysis**, which is where SQE becomes most powerful.
