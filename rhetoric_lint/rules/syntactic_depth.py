"""Attention.SyntacticDepth — overly nested clause structures."""
from typing import Any, Dict, List

GENRES = frozenset({"all"})

_NESTED_CLAUSE_DEPS = frozenset({"ccomp", "advcl", "relcl"})

# Only gate on sections where complex prose is a quality defect.
# Reference/howto/tutorial/faq sections legitimately use complex formal grammar.
_GATE_TOPIC_TYPES = frozenset({"concept", "explanation"})


def _tree_depth(token) -> int:
    depth = 0
    current = token
    while list(current.ancestors):
        current = next(current.ancestors)
        depth += 1
    return depth


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context["path"]
    text = context.get("text", "")
    sections = context.get("sections", [])
    const = context.get("const")
    issues: List[Dict[str, Any]] = []

    max_depth = getattr(const, "SYNTACTIC_DEPTH_MAX", 6) if const else 6
    max_nested = getattr(const, "NESTED_CLAUSE_MAX", 2) if const else 2
    severity = (
        const.RULE_SEVERITY_LEVELS.get("Attention.SyntacticDepth", "suggestion")
        if const else "suggestion"
    )

    for sec in sections:
        if sec.get("topic_type", "general") not in _GATE_TOPIC_TYPES:
            continue
        for para in sec.get("paragraphs", []):
            doc = para.get("doc")
            if not doc:
                continue
            para_line = para.get("line", 1)
            for sent in doc.sents:
                tokens = list(sent)
                if len(tokens) < 3:
                    continue

                # Max dependency depth
                depths = [_tree_depth(t) for t in tokens]
                sent_max_depth = max(depths) if depths else 0

                # Nested subordinate clause count
                nested = sum(1 for t in tokens if t.dep_ in _NESTED_CLAUSE_DEPS)

                if sent_max_depth > max_depth and nested > max_nested:
                    # Approximate sentence line
                    sent_start = sent.start_char
                    line = para_line + text[para.get("pos", 0):para.get("pos", 0) + sent_start].count("\n")
                    issues.append({
                        "path": path,
                        "line": line,
                        "column": 1,
                        "message": (
                            f"Sentence has high syntactic complexity "
                            f"(depth {sent_max_depth}, nested clauses {nested}) — "
                            f"consider splitting into shorter sentences."
                        ),
                        "severity": severity,
                        "check": "Attention.SyntacticDepth",
                    })
    return issues
