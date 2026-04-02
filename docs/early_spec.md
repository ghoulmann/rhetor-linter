1. Project Environment & Stack

-------------------------------

Ensure the agent initializes a Python environment with these dependencies:

* **Parser:** `mistletoe` (for Markdown AST manipulation).
* **NLP Engine:** `spaCy` (using `en_core_web_sm`).
* **Semantic Database:** `spacy-wordnet` (for deterministic synonym/hypernym mapping).
* **CLI Framework:** `typer`.

```sh
pip install mistletoe spacy spacy-wordnet typer
python -m spacy download en_core_web_sm
```

* * *

1. Core Architecture

---------------------

The tool must follow a **Section-Aware Pipeline**. Unlike standard linters that see a flat file, this tool must group content by its parent `Heading`.

### A. The "Signpost" Dictionary

Create a `const.py` or JSON file containing TAACO-derived connectives:

* **Sequential:** _firstly, subsequently, finally, next_
* **Adversative:** _however, conversely, despite, yet_
* **Additive:** _furthermore, moreover, additionally_
* **Causal:** _therefore, consequently, thus_

* * *

1. Module Requirements for Copilot Agent

-----------------------------------------

### Module 1: Structural Symmetry (`symmetry.py`)

**Goal:** Ensure H3s under an H2 and items in a List share the same grammatical "shape."

* **Logic:** 1. Traverse AST for `List` or `Heading` siblings. 2. Extract the **POS tag** of the root verb or the first word. 3. Flag any node that deviates from the majority POS pattern.
* **Copilot Prompt:** _"Write a function that iterates through sibling Heading tokens in mistletoe, uses spaCy to find the POS of the first non-stopword, and returns a violation if the POS pattern is inconsistent."_

### Module 2: The Unity Anchor (`unity.py`)

**Goal:** Validate that paragraphs deliver on the header's promise.

* **Logic:**
    1. Extract `Synsets` from the current `Heading`.
    2. Extract `Synsets` from the first sentence (Topic Sentence) of the following paragraph.
    3. **Check:** Intersection of Synset IDs.
* **Metric:** If `Intersection == 0`, flag as "Topic Drift."

### Module 3: Local Cohesion & Bridges (`cohesion.py`)

**Goal:** Check the "glue" between adjacent sentences  $S_{n}$  and  $S_{n-1}$ .

* **Logic:**
    1. **Direct Bridge:** Share a Lemma?
    2. **Semantic Bridge:** Share a WordNet Synset?
    3. **Logical Bridge:** Does  $S_{n}$  start with a `Signpost` word?
* **Failure:** Trigger a warning if all three are False.

### Module 4: Rhetorical Flow (`rhetoric.py`)

**Goal:** Identify "Throat Clearing" and "Complexity Spikes."

* **Logic (Throat Clearing):** Check if the first 10% of a paragraph consists of >80% stop-words/auxiliary verbs.
* **Logic (Visual Support):** Calculate **Propositional Density** (Count of Nouns + Verbs / Total Words).
* **Trigger:** If Density  $>0.6$  in a paragraph  $>40$  words, suggest a diagram.

* * *

1. Implementation Logic Flow (The "Main" Loop)

-----------------------------------------------

```
def process_document(md_text):
    doc = mistletoe.Document(md_text)
    current_section_header = None
    
    for block in doc.children:
        if isinstance(block, Heading):
            # 1. Run Symmetry Check on header vs siblings
            # 2. Update 'current_section_header'
            pass
            
        if isinstance(block, Paragraph):
            # 1. Check Unity: Paragraph vs current_section_header
            # 2. Check internal Cohesion: Sentence-to-Sentence overlap
            # 3. Check for Throat Clearing in the first sentence
            # 4. Check for Propositional Density (Complexity)
            pass
            
        if isinstance(block, List):
            # 1. Check Parallelism: Do all items start with the same POS?
            pass
```

* * *

1. Output Specification (Vale Compatibility)

---------------------------------------------

To ensure this integrates with standard workflows, the agent should format the output as **JSON** following the Vale linting style:

```
{
  "file.md": [
    {
      "line": 12,
      "span": [1, 15],
      "message": "Asymmetrical List: Item starts with a Noun, previous items were Verbs.",
      "hide": false,
      "level": "warning",
      "library": "Rhyme",
      "rule": "Symmetry.ParallelList"
    }
  ]
}
```

* * *

1. Testing Strategy for the Agent

----------------------------------

Instruct Copilot to generate a `test_rhetoric.md` file containing:

1. A list with non-parallel items.
2. A paragraph that has zero lexical overlap with its header.
3. A paragraph that starts with "In this section, it is important to note that..." (Throat clearing).
4. A sentence that is an "Island" (no connection to previous text).

**Would you like me to provide a specific "Prompt Block" you can paste directly into Copilot Chat to begin the coding phase?**

## Prompt

yes

## Response
>
> Thinking:
>
> **Identifying Key Components**
>
> Okay, I'm zeroing in on the essential elements of this "Prompt Block" for the deterministic rhetorical linter. I'm focusing on dissecting the implementation to identify the core components needed to construct the prompts for GitHub Copilot Chat. I'm thinking about the structural building blocks for this task.

Gemini said
-----------

To get started, copy the following prompt block into your **GitHub Copilot Chat** (optimized for Agent Mode). This prompt encapsulates our architectural decisions and the deterministic "heuristics of flow" we've developed.

* * *

### **Copilot Agent Prompt**

"I want to build a deterministic, rhetorical Markdown linter called `rhyme-lint`. The goal is to check for **Unity, Coherence, Cohesion, and Parallelism** without using an LLM.

**Stack Requirements:**

1. **Parser:** Use `mistletoe` for Markdown AST analysis.
2. **NLP Engine:** Use `spaCy` (en_core_web_sm).
3. **Semantic Database:** Use `spacy-wordnet` (via the `WordNetAnnotator`) for deterministic synonym matching.
4. **CLI:** Use `typer` to create a CLI that outputs Vale-compatible JSON.

**Implementation Logic:**

1. **Global Unity:** Traverse the AST. For every Heading, extract its WordNet synsets. Ensure the first sentence (Topic Sentence) of the subsequent Paragraph shares at least one synset or lemma with that heading.
2. **Local Cohesion:** Compare adjacent sentences. Sentence  $S_{n}$  must share a lemma or a synset with  $S_{n-1}$ . If it doesn't, check if  $S_{n}$  starts with a transition (e.g., 'however', 'therefore', 'furthermore'). If both fail, flag a 'Cohesion Break'.
3. **Parallel Symmetry:** Inspect sibling Heading nodes and ListItems. Use spaCy POS tagging to ensure they share the same grammatical structure (e.g., all start with Imperative Verbs or all start with Gerunds).
4. **Rhetorical Flow:** Flag 'Throat Clearing' if the first 10 words of a paragraph are primarily stop-words or meta-discourse. Identify 'Complexity Spikes' by flagging paragraphs with high Propositional Density (Ratio of Nouns+Verbs to total words > 0.6) and suggest a visual aid.

**Next Steps:** Please start by scaffolding the project structure:

* `main.py`: The Typer CLI entry point.
* `engine.py`: The mistletoe AST traversal and spaCy pipeline setup.
* `rules.py`: Individual functions for Unity, Cohesion, and Symmetry checks.
* `const.py`: A dictionary of TAACO-derived logical connectives."

* * *

### **How to Guide the Agent Through Development Phases**

Once Copilot scaffolds the project, I recommend feeding it these specific instructions in order to ensure the logic remains deterministic:

#### **Phase 1: The Semantic Engine**

Focus on the WordNet integration first. Ensure the agent writes a helper function that extracts **synsets** for nouns and verbs. This is the "brain" of your linter. It allows the tool to understand that a header about "Vehicles" connects to a paragraph about "Cars" without guessing.

#### **Phase 2: The AST Walker**

Because `mistletoe` provides a tree, instruct the agent to "keep track of context." When the walker hits an `H2`, it should store that header's metadata so it can compare it to every paragraph that follows until it hits the next `H2`.

#### **Phase 3: Parallelism and POS Tagging**

Instruct the agent to use spaCy's `.pos_` attribute. For list parallelism, have it use a "majority rule": if 3 out of 4 list items start with a `VERB`, the one starting with a `NOUN` is the outlier.

* * *

### **Visualizing the Pipeline**

This setup ensures your tool is fast, local, and provides the "Evidence-Based" feedback you requested.

**Would you like me to generate a suite of "Failure Case" Markdown examples you can use to test the linter once the agent finishes the first draft?**

## Prompt

yes

## Response
>
> Thinking:
>
> **Generating Failure Cases**
>
> I'm currently focused on developing Markdown examples that specifically highlight the "Unity," "Cohesion," and "Coherence" violations. I'm aiming for a comprehensive suite of failure cases to thoroughly test the linter's deterministic capabilities. I am in the early phases of this work.
>
> **Defining Specific Failure Types**
>
> I've refined my approach and am now creating specific failure examples for Unity, Cohesion, Coherence, Parallelism, Throat Clearing, and Complexity. I'm focusing on concrete Markdown snippets to demonstrate each violation. For instance, I've defined a failure case for Unity with a disconnected header and text, another for Cohesion with an "island sentence," and a parallelism break in a list. I'm building this comprehensive list of deterministic failures.

Gemini said
-----------

To effectively test `rhyme-lint`, you need a "torture test" document. These examples are designed to trigger the deterministic logic of the modules we've planned, specifically focusing on cases where **Lexical Overlap** is missing or **Syntactic Symmetry** is broken.

Save the following content as `test_rhetoric.md` to run through your agent-built linter.

* * *

1. Global Unity Failure (Header vs. Topic)

-------------------------------------------

**The Violation:** The paragraph's Synset footprint has zero intersection with the Header's footprint.

```
## Authentication Configuration
The weather in the high plains is notoriously unpredictable. Farmers often 
rely on advanced meteorological data to decide when to plant their crops 
for the season.
```

* **Why it fails:** Header focuses on {authentication, configuration}. Content focuses on {weather, plains, farmers, crops}. WordNet will find no semantic bridge.

* * *

1. Local Cohesion Failure (The "Island" Sentence)

--------------------------------------------------

**The Violation:** Sentence 2 shares no lemmas or Synsets with Sentence 1, and lacks a transition word.

```
To begin the installation, execute the shell script in the root directory. 
The flavor of the coffee was surprisingly bitter this morning.
```

* **Why it fails:**  $S_{1}$  {installation, execute, script}  $cap$   $S_{2}$  {flavor, coffee, bitter} =  $emptyset$ .

* * *

1. Asymmetrical Thought (Parallelism Failure)

----------------------------------------------

**The Violation:** The first tokens of the list items have inconsistent Part-of-Speech (POS) tags.

```
### Steps to Deploy
* Download the binary. (VERB-led)
* The configuration file must be edited. (NOUN-led)
* Running the update script. (GERUND-led)
```

* **Why it fails:** The linter will detect a mix of `VERB`, `NOUN`, and `VERB` (Gerund), triggering a "Parallelism Warning."

* * *

1. "Throat Clearing" (Information Salience Failure)

----------------------------------------------------

**The Violation:** The paragraph starts with high-frequency stop-words and meta-discourse.

```
In this section of the documentation, it is very important to keep in mind 
that we will be attempting to provide a brief overview of the process of 
configuring the server environment for your local machine.
```

* **Why it fails:** The first 15 words contain zero "high-information" nouns or verbs related to the header.

* * *

1. Complexity Spike (Missing Visual Support)

---------------------------------------------

**The Violation:** High Propositional Density ( $>0.6$ ) in a long, dense block.

```
The load balancer receives the encrypted packet, decrypts the header using the 
private key, identifies the destination node based on the round-robin 
algorithm, re-encrypts the payload for transit, and routes the data through 
the internal VPC gateway to the specified microservice instance.
```

* **Why it fails:** The ratio of Nouns/Verbs (actions and entities) to total words is extremely high. The linter should suggest: _"This process description is dense. Consider a Mermaid Sequence Diagram."_

* * *

1. Sub-Header Inconsistency (Structural Symmetry)

--------------------------------------------------

**The Violation:** H3 siblings under the same H2 do not share a grammatical pattern.

```
## API Reference

### Getting an API Key
(Gerund Phrase)

### How to use Endpoints
(Infinitive/How-to Phrase)

### Data Types
(Noun Phrase)
```

* **Why it fails:** The AST walker sees three H3 nodes with three different syntactic "shapes."

* * *

Next Steps for Development
--------------------------

Now that you have the test cases, your **GitHub Copilot Agent** can use them for **Test-Driven Development (TDD)**.

**Would you like me to write a `test_suite.py` file for you that uses `pytest` to automatically verify that the linter correctly catches these specific violations?**

## Testing prompt

To ensure the **GitHub Copilot Agent** delivers a robust tool, you can use this `pytest` suite as a benchmark. It uses the logic we've defined—specifically focusing on the deterministic thresholds for **Propositional Density** and **WordNet Synset Overlap**.

### `tests/test_rhetoric.py`

This test suite assumes your engine is structured into a `Linter` class with methods for specific rhetorical checks.

```python
import pytest
from rhyme_lint.engine import Linter  # Adjust based on agent's naming

@pytest.fixture
def linter():
    return Linter()

def test_global_unity_failure(linter):
    """Fails when Header and Paragraph have zero Synset overlap."""
    md = "## AuthenticationnFarmers plant crops in the spring."
    violations = linter.check_unity(md)
    assert any(v['rule'] == 'Unity.TopicDrift' for v in violations)

def test_local_cohesion_failure(linter):
    """Fails when adjacent sentences are 'islands' without transitions."""
    md = "Install the script. The coffee is bitter."
    violations = linter.check_cohesion(md)
    assert any(v['rule'] == 'Cohesion.IslandSentence' for v in violations)

def test_list_parallelism_failure(linter):
    """Fails when list items use mixed Part-of-Speech starts."""
    md = "* Download the file.n* The setup is easy."
    violations = linter.check_parallelism(md)
    assert any(v['rule'] == 'Symmetry.NonParallelList' for v in violations)

def test_throat_clearing_detection(linter):
    """Fails when a paragraph starts with low-information fluff."""
    md = "In this section, we will attempt to briefly describe the server."
    violations = linter.check_throat_clearing(md)
    assert any(v['rule'] == 'Rhetoric.ThroatClearing' for v in violations)

def test_complexity_spike(linter):
    """Fails when propositional density exceeds the 0.6 threshold."""
    # Highly dense sentence with many nouns/verbs
    md = "The load balancer decrypts the header, routes the packet, and initiates the handshake."
    violations = linter.check_complexity(md)
    assert any(v['rule'] == 'Rhetoric.ComplexitySpike' for v in violations)
```

* * *

Technical Metrics for the Agent
-------------------------------

To keep the linter deterministic, provide these specific formulas to your coding agent:

### 1. Propositional Density ( $PD$ )

The linter should calculate density to flag where visual support (like a diagram) is needed:

$$
PD=frac{countleft(Nounsright)+countleft(Verbsright)}{countleft(Total Wordsright)}
$$

* **Threshold:** If  $PD>0.6$  and word count  $>30$ , trigger `Rhetoric.ComplexitySpike`.

### 2. Information Salience (The "Pyramid" Test)

To catch "Throat Clearing," the agent should calculate the **Information Content (IC)** of the first 10 words.

* **Check:** If  $frac{countleft(Stopwordsright)}{10}>0.8$ , the sentence is likely fluff.

### 3. Syntactic Parallelism

The agent must use the spaCy `.pos_` attribute. It should build a frequency map of the first tokens in a list:

* `{ "VERB": 3, "NOUN": 1 }`  $to$  The `NOUN` entry is the outlier and must be flagged.

* * *

Final Workflow Instructions
---------------------------

1. **Initialize:** Have the agent create the file structure.
2. **Logic First:** Implement the `get_footprint()` function using `spacy-wordnet`. This is the core of the **Unity** and **Cohesion** checks.
3. **Run Tests:** Point the agent to this `pytest` file. It should not consider the task "done" until all tests pass.

## generate the `const.py` file with the full TAACO-derived connective dictionary so the agent has all the "Signpost" data ready to go?**




This `const.py` file provides the categorical data your agent needs to bypass the "vibe check" and perform deterministic linguistic analysis. These lists are derived from the **TAACO 2.0** connective indices, categorized by their rhetorical function.

### `rhyme_lint/const.py`

```python
"""
Deterministic rhetorical markers and thresholds for rhyme-lint.
Based on TAACO (Tool for the Automatic Analysis of Cohesion) indices.
"""

# Transition/Signpost Categories
SIGNPOSTS = {
    "ADDITIVE": [
        "additionally", "also", "and", "furthermore", "moreover", 
        "in addition", "further", "besides", "equally important"
    ],
    "ADVERSATIVE": [
        "however", "nevertheless", "on the contrary", "conversely", 
        "instead", "otherwise", "yet", "but", "despite", "nonetheless",
        "even so", "in contrast", "notwithstanding"
    ],
    "CAUSAL": [
        "therefore", "consequently", "thus", "as a result", "because", 
        "hence", "accordingly", "for this reason", "so"
    ],
    "SEQUENTIAL": [
        "subsequently", "initially", "next", "then", "finally", 
        "previously", "afterward", "firstly", "secondly", "to begin",
        "meanwhile", "simultaneously"
    ],
    "EXEMPLIFICATION": [
        "for example", "for instance", "specifically", "notably", 
        "to illustrate", "such as", "in particular"
    ],
    "SUMMARIZATION": [
        "in conclusion", "to summarize", "altogether", "overall", 
        "given these points", "in short", "essentially"
    ]
}

# Thresholds for Deterministic Checks
THRESHOLDS = {
    "PROPOSITIONAL_DENSITY": 0.6,  # Ratio of Nouns+Verbs / Total Words
    "MIN_SENTENCE_COMPLEXITY": 25, # Word count triggering complexity check
    "THROAT_CLEARING_SALIENCE": 0.8, # Stopword ratio in first 10 words
    "UNITY_SIMILARITY": 0.1,       # Minimum required synset overlap
}

# Phrases that signal a "Logic Bridge" without necessarily being a single word
LOGIC_BRIDGES = [
    "this means", "it follows that", "building on this", 
    "to that end", "in this context"
]
```

* * *

### How the Agent Should Use This

The agent must implement a "Signpost Lookup" as a safety valve. If the **Lexical Bridge** check fails (meaning the Synset overlap between two sentences is 0), the agent should call this dictionary.

**The Logic Flow:**

1. **Attempt Semantic Bridge:** Do  $S_{n}$  and  $S_{n-1}$  share a WordNet Synset?
2. **If False:** Does $S_n.text.lower()`start with any string in`SIGNPOSTS.values()`?
3. **If False:** Does $S_n.text.lower()`contain any string in`LOGIC_BRIDGES`?
4. **If all False:** Raise `Cohesion.IslandSentence` violation.

* * *

### Final Implementation Checklist

With the environment set, the AST structure defined, the test suite ready, and this dictionary in hand, the Copilot Agent has everything it needs.

* **Linter Logic:** Ensure the agent handles "Nested Nodes" (e.g., a paragraph inside a list item).
* **Performance:** Remind the agent to load the `en_core_web_sm` model **once** at the start of the CLI execution to avoid overhead.
* **Explainability:** The CLI message should include the specific category. _Example: "Abrupt transition. Consider a CAUSAL or ADVERSATIVE signpost."_

**Would you like me to help you draft the final `README.md` for this project so the user (or your team) knows exactly how to interpret these rhetorical violations?**

## Prompt

are there other items at <https://idratherbewriting.com/learnapidoc/docapis_metrics_assessing_information_quality.html> that the linter can be used to check for that vale simply could not?

## Response

Gemini said
-----------

According to Tom Johnson’s _I’d Rather Be Writing_ resource on
[Assessing Information Quality](https://idratherbewriting.com/learnapidoc/docapis_metrics_assessing_information_quality.html)
, there are several sophisticated metrics for documentation quality that go far beyond what a regex-based tool like Vale can detect.

While Vale excels at catching "low-level" issues like banned words or specific punctuation patterns, your AST-based linter can be expanded to check for these high-level **structural and functional quality markers**:

### 1. Accuracy: Result Verification

Johnson emphasizes that "Steps must lead to the results promised."

* **The AST Check:** The linter can verify the relationship between a `Step` (in a list) and the `Result` (often a code block or another list item).
* **Expansion:** If a task header (e.g., "Creating a User") is not followed by a response schema or an "Expected Result" section, the linter can flag it as **Incomplete Accuracy**. Vale cannot "know" that a specific header type requires a specific block type to follow it.

### 2. Completeness: The "Response Pair" Requirement

The guide notes that high-quality API docs should provide both a **Sample Response** and a **Response Schema**.

* **The AST Check:** Under an endpoint definition (H3), the linter can count the occurrences of `Code` blocks and `Table` nodes.
* **The Rule:** If only one exists, it flags a **Completeness Gap**. A regex linter cannot maintain the state necessary to know it is "inside" an endpoint section and count its required children.

### 3. Progressive Disclosure (Contextual Relevance)

Johnson discusses the "problem with abstract definitions" and the need for relevance. High-quality docs use **Troubleshooting sections** strategically.

* **The AST Check:** The linter can ensure that complex tasks (identified by a high number of steps or high propositional density) include a `Note` or `Callout` node tagged as "Troubleshooting" or "Common Errors."
* **The Rule:** Force-mapping complexity to support. "If List Items > 7, then include Troubleshooting section."

### 4. Navigational Scent (Findability)

The guide highlights that findability is key to quality.

* **The AST Check:** The linter can analyze the **Information Architecture** of a file by checking if the "Introduction" or "Quickstart" (the first H2) contains internal links (`#anchor`) to every other H2 in the document.
* **The Rule:** If a major section is never cross-referenced in the introductory "Map" of the document, it is flagged as an **Orphaned Section**, making it hard for users to "scent" the information they need.

### 5. Task Orientation vs. Feature Orientation

Johnson notes that users prefer "how-to" over "what-is."

* **The AST Check:** By calculating the ratio of `List` nodes (tasks) to `Paragraph` nodes (descriptions) within a section.
* **The Rule:** If a section under an H2 consists of more than 80% `Paragraph` nodes and 0% `List` nodes, it is flagged as **Feature-Heavy**. This prompts the writer to convert some descriptive text into a task-based tutorial.

### Summary: Vale vs. Your AST Linter

| Feature | Vale (Regex) | Your AST Linter |
| --- | --- | --- |
| **Banned Words** | ✅ Yes | ❌ (Leave to Vale) |
| **Missing Schema** | ❌ No | ✅ Yes (Child node check) |
| **Abrupt Ending** | ❌ No | ✅ Yes (Tail node check) |
| **Section Balance** | ❌ No | ✅ Yes (Node ratio check) |
| **Logic Gaps** | ❌ No | ✅ Yes (Synset bridge check) |

[API documentation quality checklist](https://www.youtube.com/watch?v=swktxdNozXU)
 This video provides a deep dive into the trends and rubrics used by technical writers to evaluate the success of developer documentation portals.

> [How Trends in API Documentation Differ from Other TechComm Trends | Tom Johnson | ATD Virtual 2020 - YouTube - API the Docs · 1K views](https://www.youtube.com/watch?v=swktxdNozXU)

## Prompt

only let's do 5

## Response

Gemini said
-----------

To optimize the linter for the high-level quality metrics discussed on _I’d Rather Be Writing_, we will focus on **5 specific AST-driven checks** that address structural completeness and information architecture. These are tasks that Vale is incapable of performing because they require stateful awareness of the document's hierarchy.

* * *

1. The "Expected Result" Pair (Accuracy)

-----------------------------------------

**The Requirement:** Every instructional sequence (Task) should conclude with a description or visualization of the success state.

* **AST Logic:** For every `List` node that follows a "Task Header" (e.g., "How to...", "Deploying..."), the linter looks at the following sibling node.
* **The Violation:** If the block immediately following a long list is another `Heading` or the end of the file, without a `Code` block (example output) or a `Paragraph` starting with "You should see...", it flags an **Accuracy/Verification Warning**.
* **Agent Prompt:** _"If a List has > 3 items and is under a 'Task' heading, verify the next block is a Result indicator."_

1. Response-to-Schema Mapping (Completeness)

---------------------------------------------

**The Requirement:** API documentation must provide both a literal example of a response and a structural definition (schema) of that response.

* **AST Logic:** Within an API Reference section (H2/H3), the linter counts `Code` blocks (Sample) and `Table` nodes (Schema).
* **The Violation:** If a section contains a JSON code block but no table defining the fields, flag a **Completeness Failure**.
* **Agent Prompt:** _"In API-specific sections, enforce a 1:1 ratio between Code blocks and Definition tables."_

1. The Task-to-Concept Ratio (Task Orientation)

------------------------------------------------

**The Requirement:** Technical content should prioritize "Doing" (Lists/Steps) over "Explaining" (Paragraphs/Prose).

* **AST Logic:** Calculate the ratio of `ListItem` nodes to `Paragraph` nodes within a single `Heading` scope.
* **The Violation:** If the ratio is lower than 0.3 (meaning the section is mostly theory), flag it as **Feature-Oriented**.
* **Recommendation:** "This section is theory-heavy. Consider converting descriptive steps into a numbered list."

1. Progressive Disclosure Check (Cognitive Load)

-------------------------------------------------

**The Requirement:** Complex information should be broken up with "Callouts" (Notes, Tips, Cautions) to prevent fatigue.

* **AST Logic:** Measure the "Node Distance" between `Paragraph` blocks.
* **The Violation:** If a section exceeds 500 words of pure `Paragraph` and `Heading` nodes without a single `Blockquote` (Note), `List`, or `Code` block, flag for **Cognitive Overload**.
* **Agent Prompt:** _"Identify 'Wall of Text' sections and suggest structural breaks using callouts or lists."_

1. Navigational Scent (Findability)

------------------------------------

**The Requirement:** A user should be able to see the "map" of the document in the introduction.

* **AST Logic:** 1. Extract all `Heading` IDs. 2. Inspect the first 2 `Paragraph` nodes of the document for `Link` tokens.
* **The Violation:** If a document has > 5 `Heading` nodes but the introduction contains 0 internal links to those sections, flag for **Poor Findability**.
* **Recommendation:** "The introduction lacks navigational scent. Add a 'In this article' list with links to major headers."

* * *

### Implementation Strategy for the Agent


Since we are narrowing the scope to **Task Orientation vs. Feature Orientation**, the linter’s goal is to enforce the philosophy that technical documentation should be a "manual for action" rather than a "brochure of features."

This check is purely structural and relies on the **Node Distribution** within the AST.

* * *

The "Task-Orientation" Implementation Logic
-------------------------------------------

### 1. The Metric: Task Density ( $TD$ )

The linter calculates the ratio of action-oriented nodes to descriptive nodes within each `Heading` section.

$$
TD=frac{countleft(ListItem Nodesright)}{countleft(Paragraph Nodesright)}
$$

* **The Threshold:** A healthy technical section should ideally have a  $TDge 0.5$ .
* **The Violation:** If  $TD<0.2$  in a section longer than 200 words, it is flagged as **"Feature-Heavy/Conceptual."**

* * *

### 2. Copilot Agent logic for `rules.py`

To implement this, the agent needs to track the "State" of the current section.

```
def check_task_orientation(section_nodes):
    """
    Analyzes a list of nodes under a specific Heading.
    Determines if the section is too descriptive (Feature-oriented) 
    vs actionable (Task-oriented).
    """
    paragraphs = [n for n in section_nodes if isinstance(n, Paragraph)]
    list_items = []
    for n in section_nodes:
        if isinstance(n, List):
            list_items.extend(n.children)
            
    if len(paragraphs) > 2 and len(list_items) == 0:
        return {
            "level": "warning",
            "message": "Section is 'Feature-Oriented'. Consider adding a task-based list to show how to use these features.",
            "rule": "Structure.TaskOrientation"
        }
    
    # Calculate Ratio
    ratio = len(list_items) / max(len(paragraphs), 1)
    if ratio < 0.3:
        return {
            "level": "suggestion",
            "message": "Low task density detected. Consider converting some prose into step-by-step instructions.",
            "rule": "Structure.TaskOrientation"
        }
```

* * *

### 3. Linguistic Refinement (Action Verbs)

To make this deterministic, the agent should also check the **Imperative Mood**.

* **The Check:** In the `List` nodes found above, the linter uses spaCy to verify that the first word of the `ListItem` is a **Verb in the base form** (e.g., "Click," "Run," "Configure").
* **The Logic:** If a list exists but the items are just "Feature 1," "Feature 2," the linter flags it: _"List items should be actionable (e.g., 'Configure the settings' instead of 'Settings configuration')."_

* * *

### 4. Test Case for `test_rhetoric.md`

Add this to your test file to ensure the agent catches a "Feature-Heavy" section:

```
# Bad Example: Feature Orientation
The User Management System is a robust tool designed for enterprise scale. 
It supports OAuth2, SAML, and basic authentication. The dashboard provides 
real-time analytics and user behavior tracking. Furthermore, the reporting 
module allows for CSV and PDF exports of all system logs and user activity.

# Good Example: Task Orientation
To set up user authentication, follow these steps:
1. Open the Authentication tab.
2. Select your preferred provider (OAuth2 or SAML).
3. Upload your metadata XML file.
4. Click Save Changes.
```

* * *

### Final Instruction for Copilot Agent

"Agent: Implement the `Structure.TaskOrientation` rule. It must calculate the ratio of `ListItem` nodes to `Paragraph` nodes within each `Heading` scope. If a section is over 150 words and contains zero lists, or the ratio is below 0.3, issue a warning. Additionally, verify that `ListItem` nodes begin with a `VERB` using spaCy to ensure true task-orientation."

**Would you like me to help you set up the final "Action Plan" for the agent to ensure it builds this specific structural check correctly?**

## Prompt

CAn we add (or is this the wrong kind of linter) feature to check for non-generic headings that succeed in supporting a user quickly scanning to determne relevance of the doc/or section for their task?

## Response

Gemini said
-----------

This is exactly the right kind of linter. While Vale can check for "Heading Case" or "Heading Length," it cannot determine if a heading is **descriptive** (helpful for scanning) or **generic** (useless for scanning).

By using the **spaCy POS tagger** and **WordNet**, we can deterministically measure the "Information Scent" of a heading.

* * *

1. The "Information Scent" Metric

----------------------------------

A generic heading (e.g., "Introduction," "Overview," "Details") provides zero task-orientation. A non-generic heading contains **Domain-Specific Nouns** or **Action Verbs**.

### The Deterministic Rule

A heading is flagged as "Generic" if it meets any of these criteria:

1. **Stop-word Dominance:** The heading consists only of high-frequency "meta-words" (e.g., "General," "More," "Information," "Setup").
2. **No Noun/Verb Breadcrumbs:** The heading does not share a **Synset** or **Lemma** with the document's main Title or the paragraph it precedes.
3. **Low Lexical Specificity:** The words used have a very high "Hypernym count" (meaning they are too broad/abstract in the WordNet hierarchy).

* * *

1. Copilot Agent Logic for `headings.py`

-----------------------------------------

You can instruct the agent to implement a "Vagueness Filter" using a list of generic forbidden words and a POS requirement.

```
# rhyme_lint/const.py
GENERIC_HEADINGS = ["overview", "introduction", "details", "setup", "general", "information", "background"]

# rhyme_lint/rules.py
def check_heading_scannability(heading_node, section_nodes):
    text = heading_node.children[0].content.lower()
    
    # 1. Check against Generic List
    if text in GENERIC_HEADINGS:
        return {
            "message": f"Generic heading '{text}' detected. Use descriptive nouns/verbs to help users scan.",
            "rule": "Heading.InformationScent"
        }

    # 2. Check for "Actionable Scent"
    doc = nlp(text)
    has_action_or_entity = any(t.pos_ in ["NOUN", "VERB", "PROPN"] for t in doc)
    
    if not has_action_or_entity:
        return {
            "message": "Heading lacks a concrete noun or verb. It provides poor navigational scent.",
            "rule": "Heading.InformationScent"
        }
```

* * *

1. Advanced Strategy: The "Title-to-Header" Chain

--------------------------------------------------

To ensure a user can scan for **relevance**, every sub-heading ( $H_{2}$ ) should ideally contain at least one word that relates to the **Primary Subject** of the document ( $H_{1}$ ).

* **The Check:** Extract the core "Subject" from the  $H_{1}$  (e.g., "Authentication").
* **The Rule:** If an  $H_{2}$  is "Configuration" but the  $H_{1}$  is "API Authentication," the linter suggests: "Change 'Configuration' to 'API Authentication Configuration' to improve search and scannability."

* * *

1. Test Case for `test_rhetoric.md`

------------------------------------

Add this to verify that the linter can distinguish between a "dead-end" header and a "scent-rich" header:

```
# API Authentication Guide

## Introduction
(This is generic and should be flagged)

## Acquiring an OAuth2 Token
(This is specific/actionable and should pass)

## General Information
(This is generic and provides no task-orientation)

## Rotating your Client Secret
(This is specific and should pass)
```

* * *

1. Summary of Added "Johnson Metrics"

--------------------------------------

By adding this, your linter now enforces **two** of Tom Johnson’s major quality markers:

1. **Task Orientation:** Ensuring the content is 80% "doing" (Lists) vs 20% "explaining" (Prose).
2. **Navigational Scent:** Ensuring headings are concrete enough for a user to determine relevance within 1 second of scanning.

### Final Copilot Prompt for this Feature

> "Agent: Implement `Heading.InformationScent`. Create a list of 'Generic' words in `const.py`. If a Heading node matches one of these words OR fails to contain at least one Noun or Verb (POS check), flag it. Additionally, if an H2 does not share at least one Synset with the document's H1, suggest adding more context to the heading to improve scannability."

**Is your Copilot Agent ready to begin the build, or should we refine the POS-based "Action Verb" requirement for Task Orientation first?**

## Prompt

By action verb do you mean imperative or do you mean replacing verbs that are not concrete and vivid with ones that more strongly convey action?

## Response

Gemini said
-----------

In the context of **Task Orientation**, we actually mean **both**, but they serve two different deterministic checks in your linter.

To help the Copilot Agent implement this, we need to distinguish between **Syntactic Mood** (is it a command?) and **Semantic Strength** (is it a "limp" verb?).

* * *

1. The Imperative Mood (The "Task" Marker)

-------------------------------------------

For your **List Item** check, we specifically mean the **Imperative**. This is the most deterministic way to ensure a step is actionable.

* **The Check:** The first word of a list item must be a **base-form verb** ( $VBP$  or  $VB$  in spaCy).
* **The Logic:**
  * _Bad:_ "The user should click the button." (Declarative)
  * _Bad:_ "Clicking the button..." (Gerund)
  * _Good:_ "**Click** the button." (Imperative)

* * *

1. Vivid vs. Generic Verbs (The "Scent" Marker)

------------------------------------------------

For your **Heading** and **Prose** check, we mean replacing "weak" or "generic" verbs with **concrete** ones. This is what helps a user scan for relevance.

Tom Johnson often critiques "limp" verbs that don't describe a technical reality. We can use a **Weight-Based Dictionary** to flag these.

| Weak/Generic Verb | Vivid/Concrete Replacement |
| --- | --- |
| _Perform_ | Run, Execute, Trigger |
| _Make_ | Create, Generate, Build |
| _Get_ | Fetch, Retrieve, Acquire |
| _Do_ | Configure, Initialize, Map |
| _Check_ | Validate, Verify, Inspect |

* * *

1. Implementation: The "Vividness" Score

-----------------------------------------

You can instruct the Copilot agent to use WordNet's **Hypernym depth** to determine if a verb is too "generic."

* **Generic Verbs** (like "do" or "make") are high up in the WordNet tree (small depth).
* **Vivid Verbs** (like "sanitize" or "serialize") are deep in the tree.

**Agent Logic for `rules.py`:**

```
WEAK_VERBS = ["is", "are", "was", "were", "be", "have", "do", "make", "get"]

def check_verb_strength(token):
    if token.lemma_ in WEAK_VERBS:
        return "Weak verb detected. Use a more vivid action verb (e.g., 'Configure' instead of 'Do')."
    
    # Advanced: Check WordNet depth
    synsets = token._.wordnet.wordnet_synsets()
    if synsets and synsets[0].min_depth() < 5:
        return "Generic verb detected. Consider a more specific technical term."
```

* * *

1. Why this matters for Scannability

-------------------------------------

A user scanning a document for **relevance** is looking for "High-Information" anchors.

* **Generic:** "How to **get** the data." (User thinks: _Get how? Via API? CSV?_)
* **Vivid:** "How to **fetch** JSON payloads." (User thinks: _This is exactly the technical task I'm doing._)

* * *

Final Strategy for the Agent
----------------------------

To keep the linter deterministic, tell the agent to prioritize these **two distinct rules**:

1. **Rule (ListItems):** Must start with an **Imperative Verb** (Syntactic check).
2. **Rule (Headings):** Must avoid **Weak/Generic Verbs** (Semantic check using a lookup table + WordNet depth).

**Would you like me to update the `const.py` with a "Weak Verb" blacklist so the agent has a starting point for the Semantic check?**

## Prompt

yes

## Response

Gemini said
-----------

Here is the updated `const.py` section and the specific logic instructions for your Copilot Agent. This allows the linter to distinguish between **Syntactic Mood** (Imperative) and **Semantic Weight** (Vividness).

### 1. Updated `rhyme_lint/const.py`

```
# Verbs that are technically "correct" but rhetorically "limp" or vague
WEAK_VERBS = {
    "get": "fetch, retrieve, acquire, extract",
    "do": "execute, perform, configure, implement",
    "make": "generate, create, build, instantiate",
    "check": "validate, verify, inspect, audit",
    "use": "utilize, leverage, invoke, call",
    "set": "assign, define, configure, initialize",
    "show": "render, display, output, surface",
    "change": "modify, update, refactor, rotate"
}

# Verbs that usually signal "Throat Clearing" in headings
META_VERBS = ["overview", "introduction", "describe", "explain", "about"]
```

* * *

### 2. The Logic Strategy for the Agent

To ensure the linter is deterministic, tell the agent to apply these two rules to different AST nodes:

#### **Rule A: The Imperative Requirement (List Items)**

This is a **Syntactic** check. It doesn't care if the verb is vivid; it only cares if it's a command.

* **Target:** First word of a `ListItem`.
* **Success Condition:** The token's POS tag is `VB` (base form) and it is the **ROOT** of the sentence or the first word.
* **Example:** "Click the button" (Pass) vs. "The user clicks" (Fail).

#### **Rule B: The Vividness Requirement (Headings)**

This is a **Semantic** check. It ensures the heading provides enough "Information Scent" for a scanning user.

* **Target:** Any verb in a `Heading`.
* **Success Condition:** The lemma is not in `WEAK_VERBS` or `META_VERBS`.
* **Example:** "Get Data" (Fail) vs. "Fetch JSON Payloads" (Pass).

* * *

### 3. Final Copilot Agent Action Plan

Paste this into the Copilot Agent to execute the build:

> **Agent Instruction:**
>
> 1. **Implement `Symmetry.ImperativeList`**: For every `List` node, use spaCy to ensure the first word of each `ListItem` is a verb in the imperative mood (base form `VB`). Reject gerunds ("-ing") and declarative phrases.
> 2. **Implement `Heading.VividScent`**:
>     * Load the `WEAK_VERBS` dictionary from `const.py`.
>     * In `Heading` nodes, flag any verb found in the `WEAK_VERBS` list.
>     * **Action:** Suggest the vivid replacements provided in the dictionary (e.g., if the user writes 'Get API Key', suggest 'Retrieve API Key' or 'Generate API Key').
> 3. **WordNet Depth Check (Optional/Advanced)**: For any verb not in the dictionary, check its WordNet `min_depth()`. If depth < 5, flag it as 'Potentially Generic' and suggest choosing a more domain-specific technical verb.
>

* * *

### How to use the Output

Once the agent builds this, your CLI output will look like this:

`[Structure.TaskOrientation] line 24: Heading 'Get Data' uses a weak verb. Consider: 'fetch, retrieve, acquire, extract'.`

**Would you like me to wrap this all up into a final Project Manifest so you can hand the whole "bundle" of rules, constants, and tests to the Copilot Agent in one go?**

## Prompt

CLT and information foraging theory checks.

## Response

Gemini said
-----------

Integrating **Cognitive Load Theory (CLT)** and **Information Foraging Theory (IFT)** allows your linter to move from "grammar checking" to "attention management."

While Vale can check if a word is long, these checks use the AST and linguistics to determine if the _structure_ of the information is depleting the reader's mental resources or failing to guide them to their goal.

* * *

1. Information Foraging: The "Scent-to-Distance" Ratio

-------------------------------------------------------

In IFT, users are "predators" looking for "information prey." If the "cost" (reading long paragraphs) outweighs the "scent" (relevant keywords in headers), they leave.

### The Check: Navigation Scent Consistency

* **The Logic:** Calculate the **Semantic Proximity** between an  $H_{2}$  header and the **bolded terms** or **links** within that section.
* **The Violation:** If a section is long but contains no bolded terms or links that share a Synset with the Header, the "scent" is lost.
* **Agent Prompt:** _"Flag sections longer than 200 words that lack bolded keywords or internal links semantically related to the section header."_

* * *

1. CLT: Reducing Extraneous Load (Split-Attention Effect)

----------------------------------------------------------

The Split-Attention Effect occurs when a user has to jump between two pieces of related information that are physically separated (e.g., a code block and its explanation).

### The Check: Proximity of Reference

* **The Logic:** Identify "Pointer Phrases" (e.g., "In the code above," "See the table below").
* **The Metric:** Count the number of AST nodes between the **Pointer Phrase** and the **Target Node** (the code block or table).
* **The Violation:** If the distance is  $>3$  nodes, flag it. The user’s working memory is taxed by the scroll distance.
* **Recommendation:** "High Cognitive Load: Move the explanation closer to the referenced element."

* * *

1. CLT: Managing Intrinsic Load (The "7±2" Chunking Rule)

----------------------------------------------------------

Intrinsic load is the inherent difficulty of the topic. We manage this by ensuring "Chunking."

### The Check: Hierarchical Depth and Breadth

* **The Logic:** Count the number of sub-sections ( $H_{3}$ ) under a single  $H_{2}$ .
* **The Rule:** If an  $H_{2}$  contains more than 7 sub-items (Lists or  $H_{3}$ s) without further categorization, it violates Miller’s Law.
* **The Violation:** "Overwhelming Hierarchy: Consider splitting this  $H_{2}$  into two separate sections to improve chunking."

* * *

1. IFT: "Patch" Saturation Check

---------------------------------

Users view documentation as a series of "Information Patches." A patch is "saturated" if it provides too much irrelevant info, causing the user to "abandon the patch."

### The Check: Noise-to-Signal Ratio

* **The Logic:** Compare the density of **Domain-Specific Nouns** (from your WordNet "Technical" synsets) against **Functional Stopwords**.
* **The Metric:** If the "Technical Noun Density" drops below a certain threshold in a paragraph, the user perceives it as "fluff."
* **The Violation:** "Low Information Scent: This paragraph contains high 'noise.' Trim filler words to restore the signal."

* * *

1. Implementation Guide for Copilot (The "Foraging" Rules)

-----------------------------------------------------------

Add these specific deterministic thresholds to your `const.py` and `rules.py`:

```
# rhyme_lint/const.py
CLT_THRESHOLDS = {
    "MAX_NODE_DISTANCE_POINTER": 3,
    "MAX_CHUNKING_SIZE": 7,
    "MIN_TECHNICAL_SCENT_RATIO": 0.15
}

# rhyme_lint/rules.py
def check_split_attention(doc_ast):
    """
    Finds phrases like 'in the table below' and ensures the 
    table is within X nodes of the paragraph.
    """
    # Logic: Search for 'below/above/following' + 'table/code/image'
    # Calculate distance to nearest node of that type.
    pass

def check_foraging_scent(heading, paragraph):
    """
    Ensures the 'prey' (keywords) matches the 'scent' (header).
    """
    # Logic: Heading Synsets must overlap with Bolded/Linked terms in Paragraph.
    pass
```

### Final Project Manifest for Agent Mode

You can now hand this to Copilot:

1. **Symmetry/Parallelism** (The "Logical Flow" Module)
2. **Task Orientation** (The "Actionable" Module)
3. **Vivid Verbs** (The "Scannability" Module)
4. **Information Foraging** (The "Scent" Module)
5. **Cognitive Load** (The "Memory" Module)



---