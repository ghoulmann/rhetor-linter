# Genre Labeling Guide

This guide defines the criteria for labeling documents in the
rhetor-linter genre validation corpus.

## Corpus structure

Target: 120 documents — 20 per genre, stratified across sub-domains.

```
tests/fixtures/corpus/
  technical/       20 software/API/DevOps documents
  scientific/      20 empirical research papers
  academic/        20 essays, theses, theoretical prose
  curriculum/      20 syllabi, course catalogs, training materials
  legal/           20 contracts, policies, regulations
  general/         20 miscellaneous prose (blog posts, wikis, etc.)
```

Each document lives as a `.md` file alongside a `<filename>.label` file
containing a single line: the genre name.

## Genre definitions

### technical

Primary markers (any one sufficient):
- Contains ≥ 2 fenced code blocks with shell/config/API content
- Sections organised as install → configure → use → troubleshoot
- Imperative-heavy prose ("Run", "Install", "Configure", "Deploy")
- Audience: practitioners; intent: procedure or reference

Excludes: tutorials that are primarily lecture notes without code.

### scientific

Primary markers (≥ 2 IMRaD headings):
- Abstract / Introduction / Methods / Results / Discussion /
  Conclusion / Related Work / Bibliography (any 2+)
- Cites prior work using (Author, Year) or [N] notation
- Passive / nominalized prose ("was observed", "the analysis showed")
- Audience: researchers; intent: knowledge contribution

### academic

Primary markers:
- Argumentative prose organised around a thesis
- Dense citations but no IMRaD structure
- Blockquotes from secondary sources
- Nominalization-heavy ("the conceptualization of", "an examination of")
- Audience: students/scholars; intent: argumentation or synthesis

Excludes: lab reports (→ scientific), syllabi (→ curriculum).

### curriculum

Primary markers (any combination):
- Numbered modules/units/weeks as primary heading structure (≥ 30% of headings)
- Course schedule table (dates × topics × assignments)
- Contains explicit assessment items (quiz, exam, assignment, project)
- Audience: learners / instructors; intent: learning design

Excludes: textbook chapters that lack scheduling/assessment structure.

### legal

Primary markers:
- Numbered or lettered clauses/articles as heading structure
- Dense passive and nominalized language
- Defined terms with initial capitals ("the Party", "the Agreement")
- Modal obligation language ("shall", "must", "may not")
- Audience: parties to an agreement; intent: binding specification

### general

Fallback: documents that do not meet the threshold for any specific genre.

Examples: personal blog posts, wikis without code, FAQs, meeting notes,
README files with only prose (no code fences).

## Annotation process

1. Two annotators label each document independently.
2. Disagreements are resolved by a third annotator (tie-break).
3. Record inter-annotator agreement (Cohen's κ).
4. Target: κ ≥ 0.80 before enabling GENRE_GATE_ENABLED.

## Accuracy threshold before enabling the gate

After assembling and labeling the corpus, run `tests/test_genre_accuracy.py`.
The gate should only be enabled (GENRE_GATE_ENABLED = True in const.py) when:

- Macro-averaged F1 ≥ 0.80
- Per-genre F1 ≥ 0.78 for every genre
- Inter-annotator κ ≥ 0.80
