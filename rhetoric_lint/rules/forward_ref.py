import re
from typing import Any, Dict, List

GENRES = frozenset({"all"})

_SKIP_NODE_TYPES = frozenset({
    "Code", "CodeFence", "FencedCode", "BlockCode", "ListItem", "List", "Image",
})

_DEFAULT_PHRASES = [
    "as described above",
    "as mentioned above",
    "as shown above",
    "as outlined above",
    "in the previous section",
    "from the previous section",
    "the previous step",
    "from the earlier",
    "as we saw",
    "as we discussed",
    "per the above",
]


def _line_from_pos(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Cohesion.ForwardReference: flag backward-reference phrases that create linear
    dependencies, preventing sections from functioning as standalone entry points."""
    path = context.get("path")
    text = context.get("text", "")
    sections = context.get("sections", [])
    const = context.get("const")

    phrases = getattr(const, "FORWARD_REFERENCE_PHRASES", _DEFAULT_PHRASES) if const else _DEFAULT_PHRASES
    severity = (
        const.RULE_SEVERITY_LEVELS.get("Cohesion.ForwardReference", "suggestion")
        if const else "suggestion"
    )

    patterns = [(p, re.compile(re.escape(p), re.IGNORECASE)) for p in phrases]

    issues: List[Dict[str, Any]] = []
    seen: set = set()

    for sec in sections:
        for para in sec.get("paragraphs", []):
            nodes = para.get("nodes", [])
            if nodes:
                node_type = nodes[0].get("type", "Paragraph")
                if node_type in _SKIP_NODE_TYPES:
                    continue

            para_text = para.get("text", "")
            if not para_text:
                continue
            para_pos = para.get("pos", 0)

            for phrase, pat in patterns:
                for m in pat.finditer(para_text):
                    abs_pos = para_pos + m.start()
                    line = _line_from_pos(text, abs_pos)
                    key = (line, phrase)
                    if key in seen:
                        continue
                    seen.add(key)
                    issues.append({
                        "path": path,
                        "line": line,
                        "column": 1,
                        "message": (
                            f"Forward reference: '{phrase}' creates a linear dependency "
                            f"— this section may not function as a standalone entry point."
                        ),
                        "severity": severity,
                        "check": "Cohesion.ForwardReference",
                    })

    return issues
