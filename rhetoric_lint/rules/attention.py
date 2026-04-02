from typing import Any, Dict, List

GENRES = frozenset({"all"})


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flag overly long sentences as attention/coherence issues."""
    path = context["path"]
    doc = context.get("doc")
    const = context["const"]
    issues = []
    # Node types that should not be checked for sentence length — tables and
    # code blocks are parsed by spaCy as single giant "sentences" which are not
    # real prose sentences.
    _skip_node_types = {"Code", "CodeFence", "FencedCode", "BlockCode", "Table"}

    # prefer paragraph-level sentence spans (engine attaches absolute offsets)
    sections = context.get("sections") or []
    if sections:
        for sec in sections:
            for para in sec.get("paragraphs", []):
                # Skip paragraphs whose AST node is a code block or table
                nodes = para.get("nodes") or []
                if nodes and nodes[0].get("type") in _skip_node_types:
                    continue

                para_sents = para.get("sentences")
                if not para_sents:
                    # fallback to paragraph doc if present
                    pdoc = para.get("doc")
                    if not pdoc:
                        continue
                    for s in pdoc.sents:
                        tokens = len([t for t in s if not t.is_space])
                        if tokens > const.MAX_SENTENCE_TOKENS:
                            abs_start = para.get("pos", 0) + getattr(s, "start_char", 0)
                            issues.append(
                                {
                                    "path": path,
                                    "line": (
                                        context.get("text", "")[:abs_start].count("\n")
                                        + 1
                                    ),
                                    "message": f"Long sentence ({tokens} tokens) — consider splitting",
                                    "severity": "warning",
                                    "check": "attention.long_sentence",
                                }
                            )
                    continue

                for srec in para_sents:
                    s = srec.get("span")
                    tokens = len([t for t in s if not t.is_space])
                    if tokens > const.MAX_SENTENCE_TOKENS:
                        abs_start = int(srec.get("start") or 0)
                        line = (
                            srec.get("line")
                            or context.get("text", "")[:abs_start].count("\n") + 1
                        )
                        issues.append(
                            {
                                "path": path,
                                "line": line,
                                "message": f"Long sentence ({tokens} tokens) — consider splitting",
                                "severity": "warning",
                                "check": "attention.long_sentence",
                            }
                        )
    else:
        # fallback: use document-level sentences
        if not doc:
            return issues
        for sent in doc.sents:
            tokens = len([t for t in sent if not t.is_space])
            if tokens > const.MAX_SENTENCE_TOKENS:
                abs_start = getattr(sent, "start_char", 0)
                line = doc.text[:abs_start].count("\n") + 1
                issues.append(
                    {
                        "path": path,
                        "line": line,
                        "message": f"Long sentence ({tokens} tokens) — consider splitting",
                        "severity": "warning",
                        "check": "attention.long_sentence",
                    }
                )

    return issues
