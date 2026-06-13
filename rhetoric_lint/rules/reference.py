"""Reference topic-type checks for rhetor-linter.

Checks
------
Reference.ContainsInstructions
    A Reference section contains an ordered list with imperative-verb first tokens
    — procedural steps belong in a How-To section.

Reference.MissingAuth (SP22)
    API reference document has no authentication section and no auth-related vocabulary.

Reference.MissingRateLimit (SP22)
    API reference document has no rate-limiting section and no rate-limit vocabulary.

Reference.MissingVersioning (SP22)
    API reference document has no versioning/changelog section and no version vocabulary.

Reference.MissingRequestExample (SP22)
    API reference document has no examples section and no HTTP method/curl vocabulary.

Reference.MissingParameterTable (SP22)
    API reference document has no parameters section and no parameter-table vocabulary.
"""

import re
from typing import Any, Dict, List, Optional

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

    # SP22 — Reference genre completeness checks
    issues.extend(_check_reference_completeness(context))

    return issues


# ---------------------------------------------------------------------------
# SP22 — Reference genre completeness (absence detection)
# ---------------------------------------------------------------------------

_API_INDICATORS = frozenset({"api", "endpoint", "route", "request", "response"})

_COMPLETENESS_CHECKS = [
    {
        "check": "Reference.MissingAuth",
        "heading_variants": frozenset({"authentication", "authorization", "oauth", "api key", "api keys", "auth"}),
        "marker_vocab": frozenset({"oauth", "token", "bearer", "api key", "credential", "credentials", "authorization"}),
        "severity": "warning",
        "message": "API reference document has no authentication section and no auth-related vocabulary — document how callers authenticate.",
    },
    {
        "check": "Reference.MissingRateLimit",
        "heading_variants": frozenset({"rate limit", "rate limits", "rate limiting", "throttling", "quota", "quotas"}),
        "marker_vocab": frozenset({"rate limit", "rate-limit", "throttle", "quota", "requests per", "per second", "per minute", "retry-after"}),
        "severity": "warning",
        "message": "API reference document has no rate-limiting section and no rate-limit vocabulary — document request limits.",
    },
    {
        "check": "Reference.MissingVersioning",
        "heading_variants": frozenset({"versioning", "changelog", "breaking changes", "deprecation", "migration", "api versions"}),
        "marker_vocab": frozenset({"deprecated", "deprecation", "semver", "breaking change", "migration guide", "api version"}),
        "severity": "suggestion",
        "message": "API reference document has no versioning or changelog section — document how API versions and breaking changes are communicated.",
    },
    {
        "check": "Reference.MissingRequestExample",
        "heading_variants": frozenset({"example", "examples", "sample", "request", "response", "usage"}),
        "marker_vocab": frozenset({"curl", "post ", "get ", "put ", "patch ", "delete ", "http ", "https://", "application/json"}),
        "severity": "warning",
        "message": "API reference document has no examples section and no HTTP method/curl vocabulary — add a request/response example.",
    },
    {
        "check": "Reference.MissingParameterTable",
        "heading_variants": frozenset({"parameter", "parameters", "field", "fields", "property", "properties", "argument", "arguments"}),
        "marker_vocab": frozenset({"required", "optional", "type", "default", "description", "string", "integer", "boolean"}),
        "severity": "suggestion",
        "message": "API reference document has no parameters section and no parameter-table vocabulary — document the request/response fields.",
    },
]


def _is_api_reference_doc(context: Dict[str, Any]) -> bool:
    """Return True if this document is an API reference (by genre or heading constellation)."""
    if context.get("genre") == "reference":
        return True
    sections = context.get("sections") or []
    for sec in sections:
        heading = (sec.get("heading") or "").lower()
        if any(ind in heading for ind in _API_INDICATORS):
            return True
    return False


def _has_heading_match(sections: list, variants: frozenset) -> bool:
    for sec in sections:
        heading = (sec.get("heading") or "").lower()
        if any(v in heading for v in variants):
            return True
    return False


def _has_marker_vocab(text: str, vocab: frozenset) -> bool:
    text_lower = text.lower()
    return any(v in text_lower for v in vocab)


def _doc_line_one(sections: list, text: str) -> int:
    """Return line 1 — completeness issues anchor to the top of the document."""
    return 1


def _check_reference_completeness(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not _is_api_reference_doc(context):
        return []

    path = context.get("path", "")
    text = context.get("text", "")
    sections = context.get("sections") or []

    # Minimum document size: don't flag stubs
    word_count = len(text.split()) if text else 0
    if word_count < 150:
        return []

    issues: List[Dict[str, Any]] = []
    for spec in _COMPLETENESS_CHECKS:
        if _has_heading_match(sections, spec["heading_variants"]):
            continue
        if _has_marker_vocab(text, spec["marker_vocab"]):
            continue
        issues.append({
            "path": path,
            "line": 1,
            "column": 1,
            "message": spec["message"],
            "severity": spec["severity"],
            "check": spec["check"],
        })
    return issues
