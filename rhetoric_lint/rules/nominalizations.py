"""Rhetoric.Nominalization — nominalized verb forms obscuring action."""
import re
from typing import Any, Dict, List

GENRES = frozenset({"all"})

_SKIP_NODE_TYPES = frozenset({
    "Code", "CodeFence", "FencedCode", "BlockCode",
    "Image", "BlockQuote", "List", "ListItem",
})

# Regex for detecting noun-of-verb pattern ("the implementation of")
_PREP_OF_RE = re.compile(r"\bthe\s+\w+(?:tion|ment|ance|ity|ness)\s+of\b", re.I)

# Gate: only flag in orientation/discussion sections (not reference/howto/tutorial)
_GATE_TOPIC_TYPES = frozenset({"concept", "explanation"})


def _has_verb_root(lemma: str, nlp) -> bool:
    """Check if stripping a nominalization suffix yields a plausible verb root."""
    # -tion/-ation and -ment are almost always deverbal in technical English
    for suffix in ("ation", "tion", "ment"):
        if lemma.endswith(suffix) and len(lemma) > len(suffix) + 3:
            return True
    # -ance/-ence/-ity/-ness: verify stem exists in vocab
    for suffix in ("ance", "ence", "ity", "ness"):
        if lemma.endswith(suffix) and len(lemma) > len(suffix) + 3:
            stem = lemma[: -len(suffix)]
            if len(stem) < 4:
                continue
            lex = nlp.vocab[stem]
            if lex.is_alpha and lex.prob > -25:
                return True
    return False


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context["path"]
    text = context.get("text", "")
    sections = context.get("sections", [])
    nlp = context.get("nlp")
    const = context.get("const")
    issues: List[Dict[str, Any]] = []

    if not nlp:
        return []

    suffixes = tuple(getattr(const, "NOMINALIZATION_SUFFIXES", (
        "-tion", "-ment", "-ance", "-ity", "-ness",
    )) if const else ("-tion", "-ment", "-ance", "-ity", "-ness"))
    # Strip leading dash for endswith check
    bare_suffixes = tuple(s.lstrip("-") for s in suffixes)

    exceptions = set(getattr(const, "NOMINALIZATION_EXCEPTIONS", []) if const else [])

    severity = (
        const.RULE_SEVERITY_LEVELS.get("Rhetoric.Nominalization", "suggestion")
        if const else "suggestion"
    )

    for sec in sections:
        if sec.get("topic_type", "general") not in _GATE_TOPIC_TYPES:
            continue
        for para in sec.get("paragraphs", []):
            nodes = para.get("nodes", [])
            if nodes and any(n.get("type") in _SKIP_NODE_TYPES for n in nodes):
                continue
            doc = para.get("doc")
            if not doc:
                continue

            para_text = para.get("text", "")
            para_pos = para.get("pos", 0)
            para_line = para.get("line", 1)

            for token in doc:
                if token.pos_ != "NOUN":
                    continue
                if token.ent_type_:  # skip named entities (proper nouns)
                    continue
                lemma = token.lemma_.lower()
                if not lemma.endswith(bare_suffixes):
                    continue
                if lemma in exceptions:
                    continue
                if len(lemma) < 6:
                    continue

                # Highest signal: "the <nominalization> of" prep+pobj pattern
                is_prep_pattern = (
                    token.dep_ == "pobj"
                    and token.head.lemma_ == "of"
                    and token.head.dep_ == "prep"
                )

                # Also flag prep-of in raw text (catches cases the dep tree misses)
                span_start = token.idx
                window = para_text[max(0, span_start - 20): span_start + len(token.text) + 20]
                is_prep_text = bool(_PREP_OF_RE.search(window))

                if not (is_prep_pattern or is_prep_text):
                    continue

                if not _has_verb_root(lemma, nlp):
                    continue

                abs_pos = para_pos + token.idx
                line = para_line + text[para_pos: abs_pos].count("\n")
                issues.append({
                    "path": path,
                    "line": line,
                    "column": 1,
                    "message": (
                        f"Nominalized verb form '{token.text}' in prepositional phrase — "
                        f"consider rewriting with an active verb."
                    ),
                    "severity": severity,
                    "check": "Rhetoric.Nominalization",
                })
                break  # one finding per paragraph

    return issues
