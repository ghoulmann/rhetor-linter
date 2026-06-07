"""Rhetoric.PassiveVoiceActorGap — passive constructions without an explicit by-agent."""
from typing import Any, Dict, List

GENRES = frozenset({"all"})

_SKIP_NODE_TYPES = frozenset({
    "Code", "CodeFence", "FencedCode", "BlockCode", "Image",
})

_BE_LEMMAS = frozenset({"be", "is", "are", "was", "were", "been", "being", "get", "got"})


def _has_actor(token) -> bool:
    """Return True if the passive verb has an explicit by-agent in its clause."""
    for t in token.sent:
        if t.dep_ == "agent" and t.head == token:
            return True
        if t.dep_ == "pobj" and t.head.dep_ == "agent":
            ancestor = t.head.head
            if ancestor == token or ancestor.head == token:
                return True
    return False


def _is_passive(token) -> bool:
    """Return True if token is the main verb of a passive construction."""
    if token.dep_ in ("nsubjpass", "auxpass"):
        return False
    if token.pos_ not in ("VERB",):
        return False
    # Check for auxiliary passive: aux/auxpass with a be-lemma before a past participle
    has_be_aux = any(
        c.dep_ in ("auxpass", "aux") and c.lemma_.lower() in _BE_LEMMAS
        for c in token.children
    )
    if not has_be_aux:
        return False
    # Token itself should be past participle (VBN) or have nsubjpass child
    tag_ok = token.tag_ == "VBN"
    nsubjpass_ok = any(c.dep_ == "nsubjpass" for c in token.children)
    return tag_ok or nsubjpass_ok


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context["path"]
    sections = context.get("sections", [])
    const = context.get("const")
    issues: List[Dict[str, Any]] = []

    severity = (
        const.RULE_SEVERITY_LEVELS.get("Rhetoric.PassiveVoiceActorGap", "suggestion")
        if const else "suggestion"
    )

    for sec in sections:
        genre = context.get("genre", "general")
        # Escalate in instructional genres
        sec_severity = severity
        if genre in ("howto", "tutorial") and sec_severity == "suggestion":
            sec_severity = "warning"

        for para in sec.get("paragraphs", []):
            nodes = para.get("nodes", [])
            if nodes and any(n.get("type") in _SKIP_NODE_TYPES for n in nodes):
                continue
            doc = para.get("doc")
            if not doc:
                continue
            para_line = para.get("line", 1)

            for sent in doc.sents:
                for token in sent:
                    if _is_passive(token) and not _has_actor(token):
                        issues.append({
                            "path": path,
                            "line": para_line,
                            "column": 1,
                            "message": (
                                f"Passive voice without actor: '{token.text}' — "
                                "add a 'by <agent>' phrase or rewrite as active voice."
                            ),
                            "severity": sec_severity,
                            "check": "Rhetoric.PassiveVoiceActorGap",
                        })
    return issues
