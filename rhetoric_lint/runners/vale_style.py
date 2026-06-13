"""SP2/SP4: Vale-compatible style runner — all supported rule types."""
from __future__ import annotations

import ast
import operator as _op
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import yaml

from rhetoric_lint.runners.base import StyleRunner
from rhetoric_lint.runners._readability import (
    preprocess_for_readability, VALE_METRIC_FN, composite_score, _TEXTSTAT_OK,
)

try:
    import textstat as _textstat  # type: ignore
except ImportError:
    _textstat = None  # type: ignore[assignment]

try:
    from spylls.hunspell import Dictionary as _HunspellDict
    _SPYLLS_AVAILABLE = True
except ImportError:
    _HunspellDict = None  # type: ignore[assignment,misc]
    _SPYLLS_AVAILABLE = False

# Cache loaded Hunspell dicts: (resolved_dicpath, dict_name) → Dictionary
_spell_cache: dict = {}

_ALL_TYPES = frozenset({
    "existence", "substitution",
    "occurrence", "metric", "capitalization", "repetition",
    "consistency", "conditional", "readability", "sequence",
    "spelling",
})

_SEVERITY_MAP = {
    "suggestion": "suggestion",
    "warning": "warning",
    "error": "error",
}

_SCOPE_PROSE = frozenset({"text", "sentence", "paragraph", "heading", "summary"})
_SCOPE_CODE = frozenset({"code", "pre"})

# Node types that correspond to non-prose scopes (skipped for prose scope rules)
_NON_PROSE_NODE_TYPES = frozenset({
    "CodeFence", "FencedCode", "Code", "BlockCode",
    "Image", "BlockQuote", "List", "ListItem",
})


@dataclass
class _Rule:
    name: str               # "{StyleDir}.{YamlStem}"
    extends: str            # "existence" | "substitution"
    message: str
    level: str              # "suggestion" | "warning" | "error"
    scope: str              # Vale scope string
    ignorecase: bool = True
    nonword: bool = False   # nonword:false → \b-wrap; nonword:true → substring
    exceptions: List[str] = field(default_factory=list)
    tokens: List[str] = field(default_factory=list)
    raw: List[str] = field(default_factory=list)
    swap: Dict[str, str] = field(default_factory=dict)  # substitution map
    capitalize: bool = False
    genre: Optional[str] = None   # rhetor extension: genre gate

    # Compiled at load time
    _patterns: List[Tuple[re.Pattern, str]] = field(default_factory=list, repr=False)
    _exception_re: Optional[re.Pattern] = field(default=None, repr=False)
    # Raw YAML data for new types (occurrence, metric, capitalization, etc.)
    _extra: Dict[str, Any] = field(default_factory=dict, repr=False)


class ValeStyleRunner(StyleRunner):
    """Runs Vale-compatible existence and substitution rules against document context."""

    def __init__(self) -> None:
        self._rules: List[_Rule] = []

    # ------------------------------------------------------------------
    # load()
    # ------------------------------------------------------------------

    def load(self, style_dirs: List[str] = (), enabled_styles: List[str] = (), **kwargs: Any) -> None:
        """Walk style_dirs, parse YAML rule files, compile patterns."""
        self._rules = []
        for style_dir in style_dirs:
            style_dir = os.path.expanduser(style_dir)
            if not os.path.isdir(style_dir):
                continue
            for entry in sorted(os.scandir(style_dir), key=lambda e: e.name):
                if not entry.is_dir():
                    continue
                style_name = entry.name
                if enabled_styles and style_name not in enabled_styles:
                    continue
                self._load_style(Path(entry.path), style_name)

    def _load_style(self, style_path: Path, style_name: str) -> None:
        # Optional per-style genre gate from meta.yml
        style_genre: Optional[str] = None
        meta_path = style_path / "meta.yml"
        if meta_path.exists():
            try:
                meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
                style_genre = meta.get("genre")
            except Exception:
                pass

        # Vocab suppression: vocabularies/{StyleName}/accept.txt
        vocab: List[str] = []
        accept_path = style_path / "vocabularies" / style_name / "accept.txt"
        if accept_path.exists():
            try:
                vocab = [
                    ln.strip()
                    for ln in accept_path.read_text(encoding="utf-8").splitlines()
                    if ln.strip() and not ln.startswith("#")
                ]
            except Exception:
                pass

        for yaml_file in sorted(style_path.glob("*.yml")):
            if yaml_file.name.lower() == "meta.yml":
                continue
            try:
                raw_data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            except Exception:
                continue

            extends = raw_data.get("extends", "")
            if extends not in _ALL_TYPES:
                continue

            rule_genre = raw_data.get("genre", style_genre)
            rule = _Rule(
                name=f"{style_name}.{yaml_file.stem}",
                extends=extends,
                message=raw_data.get("message", "%s"),
                level=_SEVERITY_MAP.get(raw_data.get("level", "warning"), "warning"),
                scope=raw_data.get("scope", "text"),
                ignorecase=raw_data.get("ignorecase", True),
                nonword=raw_data.get("nonword", False),
                exceptions=raw_data.get("exceptions", []),
                tokens=raw_data.get("tokens", []),
                raw=raw_data.get("raw", []),
                swap=raw_data.get("swap", {}),
                capitalize=raw_data.get("capitalize", False),
                genre=rule_genre,
                _patterns=[],
                _exception_re=None,
                _extra={**raw_data, "_rule_dir": str(yaml_file.parent)},
            )
            # Merge vocab into exceptions
            rule.exceptions = list(rule.exceptions) + vocab
            _compile_rule(rule)
            # New types don't use _patterns — always append them
            if rule._patterns or rule.extends not in ("existence", "substitution"):
                self._rules.append(rule)

    # ------------------------------------------------------------------
    # check()
    # ------------------------------------------------------------------

    def check(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self._rules:
            return []
        issues: List[Dict[str, Any]] = []
        genre = context.get("genre", "general")
        for rule in self._rules:
            if rule.genre:
                # genre may be a comma-separated inclusion list (e.g. "howto, tutorial")
                allowed = {g.strip() for g in rule.genre.split(",")}
                if genre not in allowed:
                    continue
            try:
                issues.extend(_apply_rule(rule, context))
            except Exception:
                pass
        return issues


# ---------------------------------------------------------------------------
# Pattern compilation
# ---------------------------------------------------------------------------

def _compile_rule(rule: _Rule) -> None:
    flags = re.IGNORECASE if rule.ignorecase else 0

    def _wrap(token: str) -> str:
        if rule.nonword:
            # nonword:true → raw regex token, no word boundaries, no escaping
            return token
        return r"\b" + re.escape(token) + r"\b"

    patterns: List[Tuple[re.Pattern, str]] = []

    if rule.extends == "existence":
        if rule.raw:
            for prefix in rule.raw:
                for tok in rule.tokens:
                    pat_str = prefix + _wrap(tok)
                    try:
                        patterns.append((re.compile(pat_str, flags), tok))
                    except re.error:
                        pass
        else:
            for tok in rule.tokens:
                try:
                    patterns.append((re.compile(_wrap(tok), flags), tok))
                except re.error:
                    pass

    elif rule.extends == "substitution":
        def _wrap_sub(token: str) -> str:
            # Swap keys are raw regex patterns in Vale; add word boundaries but don't escape.
            if rule.nonword:
                return token
            return r"\b(?:" + token + r")\b"

        for original, replacement in rule.swap.items():
            try:
                patterns.append((re.compile(_wrap_sub(original), flags), replacement))
            except re.error:
                pass

    elif rule.extends == "occurrence":
        # Compile occurrence token as a search pattern
        token = rule._extra.get("token", "")
        if token:
            try:
                patterns.append((re.compile(_wrap(token), flags), token))
            except re.error:
                pass

    elif rule.extends in ("consistency", "conditional"):
        # Compile either/first/second patterns
        either = rule._extra.get("either", {})
        if either:
            for a, b in either.items():
                for t in (a, b):
                    try:
                        patterns.append((re.compile(_wrap(t), flags), t))
                    except re.error:
                        pass
        first = rule._extra.get("first", "")
        second = rule._extra.get("second", "")
        for tok in (t for t in [first, second] if t):
            try:
                patterns.append((re.compile(tok, flags), tok))
            except re.error:
                pass

    elif rule.extends == "repetition":
        for tok in rule.tokens:
            try:
                patterns.append((re.compile(_wrap(tok), flags), tok))
            except re.error:
                pass

    # Compile exception pattern (all types)
    exc_re = None
    if rule.exceptions:
        exc_alts = "|".join(re.escape(e) for e in rule.exceptions)
        try:
            exc_re = re.compile(exc_alts, re.IGNORECASE)
        except re.error:
            pass

    rule._patterns = patterns
    rule._exception_re = exc_re


# ---------------------------------------------------------------------------
# Safe formula evaluator for metric type
# ---------------------------------------------------------------------------

_SAFE_OPS = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.Pow: _op.pow,
}


def _safe_eval(expr: str, variables: Dict[str, float]) -> float:
    def _eval(node: ast.expr) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            return float(variables[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
            return _SAFE_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -_eval(node.operand)
        raise ValueError(f"Unsupported expr node: {type(node)}")
    try:
        tree = ast.parse(expr.strip(), mode="eval")
        return _eval(tree.body)  # type: ignore[arg-type]
    except Exception:
        raise


def _check_condition(value: float, condition: str) -> bool:
    """Evaluate "> N", "< N", ">= N", "<= N" against value."""
    cond = condition.strip()
    for op_str, fn in ((">=", _op.ge), ("<=", _op.le), (">", _op.gt), ("<", _op.lt), ("==", _op.eq)):
        if cond.startswith(op_str):
            try:
                threshold = float(cond[len(op_str):].strip())
                return fn(value, threshold)
            except ValueError:
                return False
    return False


_SYLLABLE_RE = re.compile(r"[aeiouy]+", re.I)


def _count_syllables(word: str) -> int:
    return max(1, len(_SYLLABLE_RE.findall(word)))


def _text_variables(text: str) -> Dict[str, float]:
    words = re.findall(r"\b\w+\b", text)
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    syllables = sum(_count_syllables(w) for w in words)
    characters = sum(len(w) for w in words)
    long_words = sum(1 for w in words if len(w) > 6)
    paragraphs = max(1, text.count("\n\n") + 1)
    return {
        "words": float(len(words)),
        "sentences": float(sentences),
        "syllables": float(syllables),
        "characters": float(characters),
        "long_words": float(long_words),
        "paragraphs": float(paragraphs),
    }


# ---------------------------------------------------------------------------
# Scope extraction
# ---------------------------------------------------------------------------

def _extract_scope(scope: str, context: Dict[str, Any]) -> Iterator[Tuple[str, int]]:
    """Yield (text_chunk, start_line) pairs for the given Vale scope."""
    text: str = context.get("text", "")
    sections = context.get("sections", [])

    if scope in ("text", "summary"):
        # whole document — yield by line to preserve line numbers
        for i, line in enumerate(text.splitlines(), start=1):
            if line.strip():
                yield line, i
        return

    if scope == "heading":
        for sec in sections:
            heading = sec.get("heading", "")
            # Heading line: find it in the text
            start = sec.get("start", 0)
            line_no = text[:start].count("\n") + 1 if start else 1
            if heading:
                yield heading, line_no
        return

    if scope in ("sentence", "paragraph"):
        for sec in sections:
            for para in sec.get("paragraphs", []):
                nodes = para.get("nodes", [])
                # Skip non-prose nodes
                if nodes and any(n.get("type") in _NON_PROSE_NODE_TYPES for n in nodes):
                    continue
                if scope == "paragraph":
                    para_text = para.get("text", "")
                    para_line = para.get("line", 1)
                    if para_text:
                        yield para_text, para_line
                else:  # sentence
                    for sent in para.get("sentences", []):
                        span = sent.get("span")
                        sent_line = sent.get("line", para.get("line", 1))
                        sent_text = span.text if span is not None else ""
                        if sent_text.strip():
                            yield sent_text, sent_line
        return

    if scope == "raw":
        # Raw document text — scan every line including blank ones
        for i, line in enumerate(text.splitlines(), start=1):
            yield line, i
        return

    if scope in _SCOPE_CODE:
        for sec in sections:
            for para in sec.get("paragraphs", []):
                for node in para.get("nodes", []):
                    if node.get("type") in ("CodeFence", "FencedCode", "Code", "BlockCode"):
                        node_text = node.get("text", "")
                        node_line = para.get("line", 1)
                        if node_text:
                            yield node_text, node_line
        return

    # Default fallback: whole doc line-by-line
    for i, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            yield line, i


# ---------------------------------------------------------------------------
# Rule application — dispatcher
# ---------------------------------------------------------------------------

def _apply_rule(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    dispatch = {
        "existence":     _apply_existence,
        "substitution":  _apply_substitution,
        "occurrence":    _apply_occurrence,
        "metric":        _apply_metric,
        "capitalization":_apply_capitalization,
        "repetition":    _apply_repetition,
        "consistency":   _apply_consistency,
        "conditional":   _apply_conditional,
        "readability":   _apply_readability,
        "sequence":      _apply_sequence,
        "spelling":      _apply_spelling,
    }
    fn = dispatch.get(rule.extends)
    return fn(rule, context) if fn else []


def _make_issue(rule: _Rule, path: str, line: int, col: int, msg: str,
                fix: Any = None) -> Dict[str, Any]:
    issue: Dict[str, Any] = {
        "path": path, "line": line, "column": col,
        "message": msg, "severity": rule.level, "check": rule.name,
    }
    if fix is not None:
        issue["fix"] = fix
    return issue


def _apply_existence(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    path = context.get("path", "")
    for chunk, start_line in _extract_scope(rule.scope, context):
        for line_offset, line_text in enumerate(chunk.split("\n")):
            line_no = start_line + line_offset
            for pattern, token in rule._patterns:
                for m in pattern.finditer(line_text):
                    matched = m.group(0)
                    if rule._exception_re and rule._exception_re.search(line_text):
                        continue
                    msg = rule.message.replace("%s", matched) if "%s" in rule.message else rule.message
                    issues.append(_make_issue(rule, path, line_no, m.start() + 1, msg))
    return issues


def _apply_substitution(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    path = context.get("path", "")
    for chunk, start_line in _extract_scope(rule.scope, context):
        for line_offset, line_text in enumerate(chunk.split("\n")):
            line_no = start_line + line_offset
            for pattern, replacement in rule._patterns:
                for m in pattern.finditer(line_text):
                    matched = m.group(0)
                    if rule._exception_re and rule._exception_re.search(line_text):
                        continue
                    rep = replacement
                    if rule.capitalize and matched and matched[0].isupper():
                        rep = rep[0].upper() + rep[1:] if rep else rep
                    msg = rule.message.replace("%s", matched)
                    if "→" not in msg and "->" not in msg:
                        msg = f"{msg} → '{rep}'"
                    fix = rep if " " not in matched else None
                    issues.append(_make_issue(rule, path, line_no, m.start() + 1, msg, fix))
    return issues


def _apply_occurrence(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    path = context.get("path", "")
    max_count: Optional[int] = rule._extra.get("max")
    min_count: Optional[int] = rule._extra.get("min")
    if not rule._patterns:
        return []
    pat, token = rule._patterns[0]
    for chunk, start_line in _extract_scope(rule.scope, context):
        matches = pat.findall(chunk)
        count = len(matches)
        msg = rule.message.replace("%s", token) if "%s" in rule.message else rule.message
        if max_count is not None and count > max_count:
            issues.append(_make_issue(rule, path, start_line, 1,
                f"{msg} (found {count}, max {max_count})"))
        elif min_count is not None and count < min_count:
            issues.append(_make_issue(rule, path, start_line, 1,
                f"{msg} (found {count}, min {min_count})"))
    return issues


def _apply_metric(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    path = context.get("path", "")
    formula: str = rule._extra.get("formula", "")
    condition: str = rule._extra.get("condition", "")
    if not formula or not condition:
        return []
    # Collect text from summary scope
    text_chunks = [c for c, _ in _extract_scope("summary", context)]
    combined = " ".join(text_chunks)
    if not combined.strip():
        return []
    try:
        variables = _text_variables(combined)
        value = _safe_eval(formula, variables)
        if _check_condition(value, condition):
            msg = rule.message.replace("%s", f"{value:.2f}") if "%s" in rule.message else rule.message
            return [_make_issue(rule, path, 1, 1, msg)]
    except Exception:
        pass
    return []


_SENTENCE_INITIAL_RE = re.compile(r"(?:^|[.!?]\s+)([A-Za-z])")
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "but", "or", "nor", "for", "yet", "so",
    "at", "by", "in", "of", "on", "to", "up", "as", "is", "it",
})


def _apply_capitalization(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    path = context.get("path", "")
    match_style: str = rule._extra.get("match", "$sentence")
    threshold: float = float(rule._extra.get("threshold", 0.8))
    exceptions: List[str] = rule.exceptions

    for chunk, start_line in _extract_scope(rule.scope, context):
        for line_offset, line_text in enumerate(chunk.split("\n")):
            line_no = start_line + line_offset
            stripped = line_text.strip()
            if not stripped:
                continue

            words = re.findall(r"\b[A-Za-z]+\b", stripped)
            if not words:
                continue

            if match_style == "$sentence":
                # First word of each sentence must be capitalized
                if words and words[0][0].islower() and words[0] not in exceptions:
                    msg = rule.message.replace("%s", words[0]) if "%s" in rule.message else rule.message
                    issues.append(_make_issue(rule, path, line_no, 1, msg,
                        fix=words[0][0].upper() + words[0][1:]))

            elif match_style == "$title":
                errors = [w for w in words if w.lower() not in _STOP_WORDS
                          and not w[0].isupper() and w not in exceptions]
                ratio = len(errors) / len(words) if words else 0
                if ratio >= (1 - threshold):
                    msg = rule.message.replace("%s", ", ".join(errors)) if "%s" in rule.message else rule.message
                    issues.append(_make_issue(rule, path, line_no, 1, msg))

            else:
                # Treat match_style as a regex
                try:
                    pat = re.compile(match_style)
                    if not pat.search(stripped):
                        if words[0] not in exceptions:
                            msg = rule.message.replace("%s", stripped) if "%s" in rule.message else rule.message
                            issues.append(_make_issue(rule, path, line_no, 1, msg))
                except re.error:
                    pass

    return issues


def _apply_repetition(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    path = context.get("path", "")
    alpha_only: bool = rule._extra.get("alpha", False)
    max_rep: int = int(rule._extra.get("max", 1))

    for chunk, start_line in _extract_scope(rule.scope, context):
        for line_offset, line_text in enumerate(chunk.split("\n")):
            line_no = start_line + line_offset
            tokens = re.findall(r"\S+", line_text)
            for i in range(len(tokens) - 1):
                t1 = tokens[i].lower().strip(".,;:!?")
                t2 = tokens[i + 1].lower().strip(".,;:!?")
                if not t1 or not t2:
                    continue
                if alpha_only and not (t1.isalpha() and t2.isalpha()):
                    continue
                if t1 == t2:
                    if rule._exception_re and rule._exception_re.search(t1):
                        continue
                    msg = rule.message.replace("%s", tokens[i]) if "%s" in rule.message else rule.message
                    col = line_text.lower().find(t1 + " " + t2) + 1
                    issues.append(_make_issue(rule, path, line_no, max(1, col), msg, fix=tokens[i]))
    return issues


def _apply_consistency(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fire if both alternative forms appear in the document."""
    path = context.get("path", "")
    either: Dict[str, str] = rule._extra.get("either", {})
    if not either:
        return []

    # Collect full document text from scope
    all_text = " ".join(c for c, _ in _extract_scope(rule.scope, context))
    flags = re.IGNORECASE if rule.ignorecase else 0
    issues: List[Dict[str, Any]] = []

    for form_a, form_b in either.items():
        try:
            pat_a = re.compile(r"\b" + re.escape(form_a) + r"\b", flags)
            pat_b = re.compile(r"\b" + re.escape(form_b) + r"\b", flags)
        except re.error:
            continue
        found_a = pat_a.search(all_text)
        found_b = pat_b.search(all_text)
        if found_a and found_b:
            # Flag all occurrences of both forms
            for chunk, start_line in _extract_scope(rule.scope, context):
                for line_offset, line_text in enumerate(chunk.split("\n")):
                    line_no = start_line + line_offset
                    for m in pat_a.finditer(line_text):
                        msg = rule.message.replace("%s", m.group(0)) if "%s" in rule.message else rule.message
                        issues.append(_make_issue(rule, path, line_no, m.start() + 1, msg))
                    for m in pat_b.finditer(line_text):
                        msg = rule.message.replace("%s", m.group(0)) if "%s" in rule.message else rule.message
                        issues.append(_make_issue(rule, path, line_no, m.start() + 1, msg))
    return issues


def _apply_conditional(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fire if first matches but second is absent in the same scope chunk."""
    path = context.get("path", "")
    first: str = rule._extra.get("first", "")
    second: str = rule._extra.get("second", "")
    if not first or not second:
        return []
    flags = re.IGNORECASE if rule.ignorecase else 0
    try:
        pat_first = re.compile(first, flags)
        pat_second = re.compile(second, flags)
    except re.error:
        return []

    issues: List[Dict[str, Any]] = []
    for chunk, start_line in _extract_scope(rule.scope, context):
        if pat_first.search(chunk) and not pat_second.search(chunk):
            msg = rule.message.replace("%s", first) if "%s" in rule.message else rule.message
            issues.append(_make_issue(rule, path, start_line, 1, msg))
    return issues


def _apply_readability(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not _TEXTSTAT_OK or _textstat is None:
        return []
    path = context.get("path", "")
    grade_max: Optional[float] = rule._extra.get("grade")
    metrics: List[str] = rule._extra.get("metrics", ["Flesch-Kincaid"])

    sections = context.get("sections", [])
    prose = preprocess_for_readability(sections)
    if not prose.strip() or len(prose.split()) < 30:
        return []

    issues: List[Dict[str, Any]] = []
    for metric_name in metrics:
        fn = VALE_METRIC_FN.get(metric_name)
        if not fn:
            continue
        try:
            value = fn(prose)
        except Exception:
            continue
        if grade_max is not None and value > grade_max:
            msg = rule.message.replace("%s", f"{value:.1f}") if "%s" in rule.message else rule.message
            issues.append(_make_issue(rule, path, 1, 1, msg))
    return issues


def _apply_sequence(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Match token sequences by text/POS tag using spaCy."""
    nlp = context.get("nlp")
    if nlp is None:
        return []
    path = context.get("path", "")
    seq_tokens: List[Dict[str, Any]] = rule._extra.get("tokens", [])
    if not seq_tokens:
        return []

    issues: List[Dict[str, Any]] = []
    sections = context.get("sections", [])

    for sec in sections:
        for para in sec.get("paragraphs", []):
            doc = para.get("doc")
            if not doc:
                continue
            para_line = para.get("line", 1)
            for sent in doc.sents:
                sent_toks = list(sent)
                if _match_sequence(sent_toks, seq_tokens):
                    msg = rule.message
                    issues.append(_make_issue(rule, path, para_line, 1, msg))
    return issues


def _match_sequence(tokens: list, descriptors: List[Dict[str, Any]]) -> bool:
    """Try to match all descriptors in order against tokens, respecting skip."""
    if not descriptors:
        return False
    desc_idx = 0
    tok_idx = 0
    desc = descriptors[desc_idx]
    skip = int(desc.get("skip", 0))
    gap = 0

    while tok_idx < len(tokens) and desc_idx < len(descriptors):
        tok = tokens[tok_idx]
        desc = descriptors[desc_idx]
        pattern = desc.get("pattern", "")
        tag = desc.get("tag", "")
        negate = desc.get("negate", False)
        skip = int(desc.get("skip", 0))

        text_match = not pattern or bool(re.search(pattern, tok.text, re.I))
        tag_match = not tag or tok.tag_ == tag
        matched = text_match and tag_match
        if negate:
            matched = not matched

        if matched:
            desc_idx += 1
            gap = 0
            if desc_idx >= len(descriptors):
                return True
        else:
            gap += 1
            if desc_idx > 0 and gap > skip:
                return False
        tok_idx += 1

    return desc_idx >= len(descriptors)


# ---------------------------------------------------------------------------
# SP_SPELL — extends: spelling
# ---------------------------------------------------------------------------

def _load_hunspell_dict(rule_dir: str, dicpath: str, dict_name: str):
    """Load (and cache) a Hunspell dictionary.  Returns None on failure.

    Tries in order:
    1. spylls bundled dict (``Dictionary.DISTRIBUTED``): name like ``en_US``
    2. ``from_files`` with path resolved relative to ``rule_dir / dicpath``
    """
    if not _SPYLLS_AVAILABLE:
        return None
    key = (rule_dir, dicpath, dict_name)
    if key in _spell_cache:
        return _spell_cache[key]
    d = None
    # Try bundled first (no file-system lookup needed)
    if hasattr(_HunspellDict, "DISTRIBUTED") and dict_name in _HunspellDict.DISTRIBUTED:
        try:
            d = _HunspellDict.from_system(dict_name)
        except Exception:
            d = None
    # Fall back to explicit path
    if d is None:
        if dicpath:
            resolved = os.path.join(rule_dir, dicpath, dict_name)
        else:
            resolved = os.path.join(rule_dir, dict_name)
        if os.path.isfile(resolved + ".aff"):
            try:
                d = _HunspellDict.from_files(resolved)
            except Exception:
                d = None
    if d is not None:
        _spell_cache[key] = d
    return d


def _apply_spelling(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """SP_SPELL: checks prose tokens against Hunspell dictionaries via spylls."""
    path = context.get("path", "")
    issues: List[Dict[str, Any]] = []

    if not _SPYLLS_AVAILABLE:
        # Emit one meta-finding per file instructing user to install the extra
        issues.append({
            "path": path,
            "line": 1,
            "column": 1,
            "message": (
                f"Spell check rule '{rule.name}' requires spylls — "
                "install with: pip install 'rhetoric-lint[spell]'"
            ),
            "severity": "suggestion",
            "check": rule.name,
        })
        return issues

    extra = rule._extra
    # Resolve rule file location from rule.name: "{StyleName}.{Stem}"
    # We store the rule_dir in _extra["_rule_dir"] at load time (see load()).
    rule_dir = extra.get("_rule_dir", "")
    dicpath = extra.get("dicpath", "")
    dict_names: List[str] = extra.get("dictionaries", [])
    if not dict_names:
        return []

    # Load dictionaries
    dicts = []
    for name in dict_names:
        d = _load_hunspell_dict(rule_dir, dicpath, name)
        if d is not None:
            dicts.append(d)
    if not dicts:
        return []

    # Build ignore set: words listed in ignore files
    ignore: set = set()
    for ignore_path in (extra.get("ignore") or []):
        resolved_ignore = os.path.join(rule_dir, ignore_path) if not os.path.isabs(ignore_path) else ignore_path
        try:
            with open(resolved_ignore, encoding="utf-8") as fh:
                for line in fh:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        ignore.add(word.lower())
        except Exception:
            pass
    # vocab exceptions merged at load time into rule.exceptions
    for exc in rule.exceptions:
        ignore.add(exc.lower())

    # Build filter patterns (skip tokens matching these)
    filter_res = [re.compile(p) for p in (extra.get("filters") or [])]

    want_suggestions = (extra.get("action") or {}).get("name") == "suggest"

    _WORD_RE = re.compile(r"[a-zA-Z''’\-]+")

    for chunk, start_line in _extract_scope(rule.scope, context):
        for line_offset, line_text in enumerate(chunk.split("\n")):
            line_no = start_line + line_offset
            for m in _WORD_RE.finditer(line_text):
                word = m.group(0).strip("'-’")
                if not word or len(word) < 2:
                    continue
                if word.lower() in ignore:
                    continue
                if any(f.search(word) for f in filter_res):
                    continue
                # Check all dicts — word is OK if any dict accepts it
                if any(d.lookup(word) for d in dicts):
                    continue
                msg = rule.message.replace("%s", word) if "%s" in rule.message else rule.message
                issue = _make_issue(rule, path, line_no, m.start() + 1, msg)
                if want_suggestions:
                    suggestions: List[str] = []
                    for d in dicts:
                        suggestions.extend(d.suggest(word))
                        if len(suggestions) >= 3:
                            break
                    issue["suggestions"] = suggestions[:3]
                issues.append(issue)

    return issues
