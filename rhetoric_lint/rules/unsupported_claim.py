"""Completeness.UnsupportedClaim — assertion signal not followed by evidence within 2 sentences."""
import re
from typing import Any, Dict, List

GENRES = frozenset({"concept", "explanation", "technical", "general"})

_SKIP_NODE_TYPES = frozenset({
    "Code", "CodeFence", "FencedCode", "BlockCode", "Image",
})

_ASSERTION_RE = re.compile(
    r"\b(?:this means|therefore|thus|this demonstrates|this shows|"
    r"which shows|which means|which demonstrates|this confirms|"
    r"this proves|this indicates|this suggests|this implies|"
    r"as a result|consequently|it follows that)\b",
    re.IGNORECASE,
)

_EVIDENCE_RE = re.compile(
    r"\b(?:for example|for instance|see |as shown in|as illustrated|"
    r"figure|table|listing|such as)\b"
    r"|\[?\d+\]"       # citation [N]
    r"|```",           # code fence following
    re.IGNORECASE,
)


def _has_evidence(sentences: List[Any], idx: int, lookahead: int, nodes: List[Dict]) -> bool:
    """Check 2 following sentences and the section's nodes for evidence signals."""
    for j in range(idx + 1, min(idx + 1 + lookahead, len(sentences))):
        if _EVIDENCE_RE.search(sentences[j].text):
            return True
    # Code fence anywhere in the same paragraph counts as evidence
    if any(n.get("type") in ("CodeFence", "FencedCode", "BlockCode") for n in nodes):
        return True
    return False


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context["path"]
    sections = context.get("sections", [])
    const = context.get("const")
    issues: List[Dict[str, Any]] = []
    genre = context.get("genre", "general")

    if genre not in GENRES:
        return issues

    lookahead = getattr(const, "UNSUPPORTED_CLAIM_LOOKAHEAD_SENTENCES", 2) if const else 2
    max_per_para = getattr(const, "UNSUPPORTED_CLAIM_MAX_PER_PARA", 2) if const else 2
    severity = (
        const.RULE_SEVERITY_LEVELS.get("Completeness.UnsupportedClaim", "suggestion")
        if const else "suggestion"
    )

    for sec in sections:
        topic = sec.get("topic_type", "general")
        # Skip instructional and non-discursive sections
        if topic in ("howto", "tutorial", "reference", "faq"):
            continue

        for para in sec.get("paragraphs", []):
            nodes = para.get("nodes", [])
            if nodes and any(n.get("type") in _SKIP_NODE_TYPES for n in nodes):
                continue
            doc = para.get("doc")
            if not doc:
                continue
            para_line = para.get("line", 1)

            sents = list(doc.sents)
            if len(sents) < 2:
                continue

            fired_this_para = 0
            for i, sent in enumerate(sents):
                if fired_this_para >= max_per_para:
                    break
                if not _ASSERTION_RE.search(sent.text):
                    continue
                if _has_evidence(sents, i, lookahead, nodes):
                    continue
                issues.append({
                    "path": path,
                    "line": para_line,
                    "column": 1,
                    "message": (
                        f"Unsupported claim: '{sent.text[:80].strip()}' "
                        "— follow assertion signals with evidence, an example, or a code sample."
                    ),
                    "severity": severity,
                    "check": "Completeness.UnsupportedClaim",
                })
                fired_this_para += 1

    return issues
