"""Reference topic-type checks for rhetor-linter.

Checks
------
Reference.ContainsInstructions
    A Reference section contains an ordered list with imperative-verb first tokens
    — procedural steps belong in a How-To section.
"""

import re
from typing import Any, Dict, List

GENRES = frozenset({"all"})

_MIN_OL_ITEMS = 2

_IMPERATIVE_OVERRIDES = frozenset({
    "add", "run", "set", "get", "use", "open", "go", "click",
    "type", "enter", "select", "check", "copy", "paste", "save",
    "start", "stop", "restart", "create", "delete", "update",
    "install", "download", "upload", "configure", "deploy",
    "enable", "disable", "navigate", "log", "export", "import",
    "verify", "confirm", "note", "ensure",
})

_MD_STRIP_RE = re.compile(r"^[*_`#>\-\d\.\)\s]+")


def _first_word(text: str) -> str:
    cleaned = _MD_STRIP_RE.sub("", text).strip()
    return cleaned.split()[0].lower() if cleaned.split() else ""


def _is_imperative(word: str, doc_token) -> bool:
    if word in _IMPERATIVE_OVERRIDES:
        return True
    if doc_token is not None and doc_token.tag_ == "VB":
        return True
    return False


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context.get("path", "")
    text = context.get("text", "")
    sections = context.get("sections") or []
    nlp = context.get("nlp")
    issues: List[Dict[str, Any]] = []

    for sec in sections:
        if sec.get("topic_type") != "reference":
            continue

        start = sec.get("start", 0)
        line = text[:start].count("\n") + 1 if text else 1
        heading = (sec.get("heading") or "this section").strip()

        imperative_ol_count = 0
        for para in sec.get("paragraphs", []):
            for node in para.get("nodes", []):
                if node.get("type") != "ListItem" or node.get("list_type") != "ol":
                    continue
                item_text = (node.get("text") or "").strip()
                if not item_text:
                    continue
                word = _first_word(item_text)
                if not word:
                    continue

                spacy_token = None
                if nlp is not None:
                    try:
                        mini_doc = nlp(item_text[:80])
                        for tok in mini_doc:
                            if not tok.is_space and not tok.is_punct:
                                spacy_token = tok
                                break
                    except Exception:
                        pass

                if _is_imperative(word, spacy_token):
                    imperative_ol_count += 1

        if imperative_ol_count >= _MIN_OL_ITEMS:
            issues.append({
                "path": path,
                "line": line,
                "column": 1,
                "message": (
                    f"Reference section '{heading}' contains {imperative_ol_count} "
                    "procedural steps — move instructions to a How-To section."
                ),
                "severity": "warning",
                "check": "Reference.ContainsInstructions",
            })

    return issues
