"""SP2: Vale-compatible style runner — existence and substitution rule types."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import yaml

from rhetoric_lint.runners.base import StyleRunner

_SEVERITY_MAP = {
    "suggestion": "suggestion",
    "warning": "warning",
    "error": "error",
}

_SCOPE_PROSE = frozenset({"text", "sentence", "paragraph", "heading", "summary"})
_SCOPE_CODE = frozenset({"code", "raw", "pre"})

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
            if extends not in ("existence", "substitution"):
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
            )
            # Merge vocab into exceptions
            rule.exceptions = list(rule.exceptions) + vocab
            _compile_rule(rule)
            if rule._patterns:
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
            if rule.genre and rule.genre != genre:
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
            return re.escape(token)
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
        # swap dict: original → replacement
        for original, replacement in rule.swap.items():
            try:
                patterns.append((re.compile(_wrap(original), flags), replacement))
            except re.error:
                pass

    # Compile exception pattern
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
# Rule application
# ---------------------------------------------------------------------------

def _apply_rule(rule: _Rule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    path = context.get("path", "")

    for chunk, start_line in _extract_scope(rule.scope, context):
        # Track line offset within multi-line chunks
        chunk_lines = chunk.split("\n")
        for line_offset, line_text in enumerate(chunk_lines):
            line_no = start_line + line_offset
            for pattern, replacement_or_token in rule._patterns:
                for m in pattern.finditer(line_text):
                    matched = m.group(0)

                    # Exception suppression
                    if rule._exception_re and rule._exception_re.search(matched):
                        continue

                    # Build message
                    if rule.extends == "existence":
                        msg = rule.message.replace("%s", matched) if "%s" in rule.message else rule.message
                        fix = None
                    else:  # substitution
                        replacement = replacement_or_token
                        if rule.capitalize and matched[0].isupper():
                            replacement = replacement[0].upper() + replacement[1:]
                        msg = rule.message.replace("%s", matched)
                        if "→" in msg or "->" in msg:
                            pass  # message already encodes the swap
                        else:
                            msg = f"{msg} → '{replacement}'"
                        # Only emit fix for single-token (no internal whitespace) matches
                        fix = replacement if " " not in matched else None

                    issue: Dict[str, Any] = {
                        "path": path,
                        "line": line_no,
                        "column": m.start() + 1,
                        "message": msg,
                        "severity": rule.level,
                        "check": rule.name,
                    }
                    if fix is not None:
                        issue["fix"] = fix
                    issues.append(issue)

    return issues
