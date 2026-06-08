"""Terminology.PreferredForm — flag incorrect casing/form of proper nouns and brand names."""
import json
import re
from typing import Any, Dict, List

GENRES = frozenset({"all"})

_SKIP_NODE_TYPES = frozenset({
    "Code", "CodeFence", "FencedCode", "BlockCode", "Image",
})

_URL_RE = re.compile(r"https?://\S+|`[^`]+`|\[.*?\]\(.*?\)")


def _load_terms(terminology_file: str) -> List[Dict]:
    """Load terms from JSON file.

    Accepts either a list of strings, a list of dicts with `required_form` + optional
    `aliases`, or a dict mapping required_form → [aliases].
    """
    try:
        with open(terminology_file, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    terms = []
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, str):
                terms.append({"required_form": entry, "aliases": []})
            elif isinstance(entry, dict) and "required_form" in entry:
                terms.append({
                    "required_form": entry["required_form"],
                    "aliases": entry.get("aliases", []),
                })
    elif isinstance(data, dict):
        for form, aliases in data.items():
            terms.append({"required_form": form, "aliases": aliases if isinstance(aliases, list) else []})
    return terms


def _build_pattern(required_form: str, aliases: List[str]) -> re.Pattern:
    variants = [required_form] + aliases
    alts = "|".join(re.escape(v) for v in sorted(variants, key=len, reverse=True))
    return re.compile(r"(?<!\w)(?:" + alts + r")(?!\w)", re.IGNORECASE)


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context["path"]
    text = context.get("text", "")
    sections = context.get("sections", [])
    const = context.get("const")
    issues: List[Dict[str, Any]] = []

    terminology_file = getattr(const, "TERMINOLOGY_FILE", "") if const else ""
    if not terminology_file:
        return []

    terms = _load_terms(terminology_file)
    if not terms:
        return []

    severity = (
        const.RULE_SEVERITY_LEVELS.get("Terminology.PreferredForm", "warning")
        if const else "warning"
    )

    compiled = [
        (entry["required_form"], _build_pattern(entry["required_form"], entry["aliases"]))
        for entry in terms
    ]

    for sec in sections:
        for para in sec.get("paragraphs", []):
            nodes = para.get("nodes", [])
            if nodes and any(n.get("type") in _SKIP_NODE_TYPES for n in nodes):
                continue

            para_text = para.get("text", "")
            if not para_text:
                continue
            para_line = para.get("line", 1)
            para_pos = para.get("pos", 0)

            # Blank out URLs and inline code to avoid false positives on those spans
            clean_text = _URL_RE.sub(lambda m: " " * len(m.group()), para_text)

            for required_form, pattern in compiled:
                for m in pattern.finditer(clean_text):
                    matched = m.group(0)
                    if matched == required_form:
                        continue
                    abs_pos = para_pos + m.start()
                    line = para_line + text[para_pos:abs_pos].count("\n")
                    issues.append({
                        "path": path,
                        "line": line,
                        "column": m.start() + 1,
                        "message": f"Incorrect form '{matched}' — use '{required_form}'.",
                        "severity": severity,
                        "check": "Terminology.PreferredForm",
                        "fix": required_form,
                    })

    return issues
