# Roadmap

Future rule candidates and infrastructure improvements, roughly ordered by feasibility.

## Entity Grid Coherence

Track how key entities (proper nouns, technical terms) transition across sentences: Subject, Object, Absent, Reintroduced. Patterns like Subject-Subject-Subject indicate strong coherence; Subject-Absent-Absent signals topic abandonment. This is a more principled model than lexical overlap for measuring coherence and would complement the current overlap-based rules.

**Depends on:** spaCy dependency parsing (already available).

## Topic Type Validation (Diataxis)

Once the genre classifier is ungated (target: F1 >= 0.78), validate that documents match their declared type through expected rhetorical moves. Tutorials should have sequential imperatives, explanations should use causal connectives, reference sections should follow definition patterns. This bridges genre classification with structural validation.

**Depends on:** Genre gate lifted, SIGNPOSTS relation types (already in const.py).

## Propositional Density Scoring

Calculate (nouns + verbs) / total tokens per paragraph. High density (above 0.6) in paragraphs over 30 words signals cognitive overload -- the reader encounters too many new concepts per sentence. This extends the existing Attention rules (long sentence, complexity spike) with a paragraph-level metric. When density is high, suggest visual aids (diagrams, tables) or decomposition.

**Depends on:** spaCy POS tagging (already available).

## Context Window Optimization

Flag sections that require excessive prior context to be understood as standalone units. Measurable via: does a section's first paragraph contain enough content lemmas to be self-explanatory, or does it rely heavily on pronouns and deictics referencing earlier sections? Directly serves the pre-AI-ingestion quality gate use case, since RAG systems retrieve individual chunks without surrounding context.

**Depends on:** channelize_tokens pronoun/content channels (already in overlap.py), deictic detection (already in rules/deictic.py).
