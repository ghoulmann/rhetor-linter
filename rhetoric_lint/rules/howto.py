"""How-To topic-type checks for rhetor-linter.

Checks
------
HowTo.NonImperativeStep
    An ordered step in a How-To section does not begin with an imperative verb
    (spaCy VB tag on the first non-whitespace token).
HowTo.UnorderedSteps
    A How-To section uses an unordered list where a required sequence exists.
"""

import re
from typing import Any, Dict, List

GENRES = frozenset({"all"})

# Minimum ol items before checking for imperative verbs
_MIN_OL_FOR_CHECK = 2
# Minimum ul items before flagging unordered steps
_MIN_UL_FOR_FLAG = 2

# Common imperative-looking words that are tagged NN by spaCy due to OOV
# — these should be treated as imperatives even if spaCy doesn't VB-tag them.
_IMPERATIVE_OVERRIDES = frozenset({
    "add", "run", "set", "get", "use", "open", "go", "click",
    "type", "enter", "select", "check", "copy", "paste", "save",
    "start", "stop", "restart", "create", "delete", "update",
    "install", "download", "upload", "configure", "deploy",
    "enable", "disable", "navigate", "log", "export", "import",
    "verify", "confirm", "note", "ensure",
})

# Strip markdown formatting before tokenising the first word
_MD_STRIP_RE = re.compile(r"^[*_`#>\-\d\.\)\s]+")


def _first_word(text: str) -> str:
    """Return the first substantive word of *text* after stripping markdown."""
    cleaned = _MD_STRIP_RE.sub("", text).strip()
    return cleaned.split()[0].lower() if cleaned.split() else ""


def _is_imperative(token_text: str, doc_token) -> bool:
    """Return True if token is an imperative verb."""
    if token_text.lower() in _IMPERATIVE_OVERRIDES:
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
        if sec.get("topic_type") != "howto":
            continue

        start = sec.get("start", 0)
        sec_line = text[:start].count("\n") + 1 if text else 1
        heading = (sec.get("heading") or "this section").strip()

        ol_items: List[Dict[str, Any]] = []
        ul_count = 0

        for para in sec.get("paragraphs", []):
            for node in para.get("nodes", []):
                if node.get("type") != "ListItem":
                    continue
                if node.get("list_type") == "ol":
                    ol_items.append({"node": node, "para_line": para.get("line", sec_line)})
                else:
                    ul_count += 1

        # UnorderedSteps: How-To has no ol but has ul
        if len(ol_items) < _MIN_OL_FOR_CHECK and ul_count >= _MIN_UL_FOR_FLAG:
            issues.append({
                "path": path,
                "line": sec_line,
                "column": 1,
                "message": (
                    f"How-To section '{heading}' uses an unordered list — "
                    "steps with a required sequence should be numbered."
                ),
                "severity": "warning",
                "check": "HowTo.UnorderedSteps",
            })
            continue

        # NonImperativeStep: check first word of each ol item
        if len(ol_items) < _MIN_OL_FOR_CHECK:
            continue

        for item_info in ol_items:
            node = item_info["node"]
            item_text = (node.get("text") or "").strip()
            if not item_text:
                continue
            word = _first_word(item_text)
            if not word:
                continue

            # Use spaCy to get the tag of the first real token
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

            if not _is_imperative(word, spacy_token):
                item_line = item_info["para_line"]
                issues.append({
                    "path": path,
                    "line": item_line,
                    "column": 1,
                    "message": (
                        f"How-To step does not begin with an imperative verb: "
                        f"'{item_text[:60]}'"
                    ),
                    "severity": "suggestion",
                    "check": "HowTo.NonImperativeStep",
                })

    return issues
