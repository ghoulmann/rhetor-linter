import re
from importlib import import_module
from typing import Any, Dict, List, Optional

import spacy

try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _yaml = None  # type: ignore[assignment]
    _YAML_AVAILABLE = False

import rhetoric_lint.const as const
from rhetoric_lint.genre import classify_genre
from rhetoric_lint.topic_type import classify_section_topic
from rhetoric_lint.template_type import classify_doc_template
from rhetoric_lint.runners.base import StyleRunner

# Pre-processing: link reference definition lines (e.g. "[img1]: data:image/png;base64,...")
# These are blanked out (content replaced, newline kept) before parsing so they don't
# appear as Paragraph nodes and trigger false positives in ComplexitySpike and other rules.
# Link reference definitions are always single-line: "[label]: <url> [optional title]".
# The original \s+ matched newlines too, which made the pattern greedily swallow the
# next non-blank line — silently consuming code-fence openers and other adjacent
# content in any doc that uses reference-style links.
_LINK_REF_DEF_RE = re.compile(r"^\[.*?\]:[ \t]+\S[^\n]*", re.M)

# Image-only paragraph detection (single-line image references with no surrounding prose)
_IMAGE_ONLY_RE = re.compile(r"^!\[.*?\](?:\[.*?\]|\(.*?\))$", re.DOTALL)

# Inline Markdown link stripping for NLP token counts — replaces [text](url) / [text][ref]
# with just `text` so URL path segments don't inflate sentence token counts.
_MD_INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_MD_REF_LINK_RE = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")

# HTML comments are non-prose annotations that mistletoe surfaces as RawHTML
# inside paragraphs. Without stripping, the comment text is fed to the NLP
# pipeline and cohesion/topic rules treat it as adjacent prose.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Inline HTML tags (<div>, </div>, <span style="...">, <br>, <font color=...>)
# appear in many docs as structural decoration. Without stripping, mistletoe
# may parse a bare "</div>" as a Paragraph containing only that tag — which
# enters sentence-pair walks and produces zero-content "sentences" that look
# like cohesion breaks against any real prose. The replacement is whitespace
# of equal length so line/column offsets are preserved.
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^<>\n]*>")
# Code-fence boundary: everything between matched ``` lines is left alone, so
# HTML used as a code example doesn't get corrupted.
_FENCE_LINE_RE = re.compile(r"^```.*$", re.M)

# MyST role directives like {code}`Site`, {py:class}`...`, {ref}`label <target>`
# leak the role name and angle-bracket target into the token stream. Strip the
# role prefix and (for {ref}-style) the `<target>` portion, keeping the visible
# label text only.
_MYST_REF_LABEL_RE = re.compile(r"\{[a-zA-Z][\w:.-]*\}`([^`<]+?)\s*<[^`>]*>`")
_MYST_ROLE_RE = re.compile(r"\{[a-zA-Z][\w:.-]*\}`([^`]+)`")

# MyST admonition fences: ```{warning} ... ``` blocks. Mistletoe parses them
# as opaque code blocks, hiding the prose inside from rules that check for
# failure guidance, topic continuity, etc. Rewrite the fence to a blockquote
# carrying the admonition kind as a Markdown bold lead so the body becomes
# visible prose. Line counts are preserved (open/close fences become blank
# lines; body lines become "> " prefixed).
_MYST_ADMONITION_RE = re.compile(
    r"^(?P<indent>[ \t]*)```\{(?P<kind>note|warning|tip|caution|important|danger|attention|hint|seealso)\}[ \t]*\n(?P<body>.*?)\n(?P=indent)```[ \t]*$",
    re.DOTALL | re.M,
)


def _rewrite_myst_admonitions(text: str) -> str:
    """Rewrite ```{kind} ... ``` fences to blockquotes, preserving line counts."""
    def _rewrite(m: "re.Match[str]") -> str:
        kind = m.group("kind").capitalize()
        body_lines = m.group("body").split("\n")
        # Original span covers: open-fence line, len(body_lines) body lines,
        # close-fence line — total len(body_lines)+2 lines.
        out_lines = [f"> **{kind}:**"]
        out_lines.extend(f"> {line}" for line in body_lines)
        out_lines.append("")  # was close fence
        return "\n".join(out_lines)
    return _MYST_ADMONITION_RE.sub(_rewrite, text)


# pymdownx.blocks.admonition syntax (used in FastAPI docs and some other
# projects):
#   /// kind | Title text
#   Body content at column 0.
#   ///
# Closed by a line containing only "///". Differs from MkDocs Material
# !!!-style admonitions in that the body is NOT indented. Rewrite the open
# line to "> **Kind:** [title]", body lines to "> body", and the close line
# to blank — same line count.
_PYMDOWNX_BLOCK_RE = re.compile(
    r"^(?P<indent>[ \t]*)/// "
    r"(?P<kind>[a-zA-Z][\w-]*)"
    r"(?:[ \t]*\|[ \t]*(?P<title>[^\n]+?))?[ \t]*\n"
    r"(?P<body>.*?)\n"
    r"(?P=indent)///[ \t]*$",
    re.DOTALL | re.M,
)


def _rewrite_pymdownx_block_admonitions(text: str) -> str:
    """Rewrite "/// kind | Title ... ///" blocks to blockquotes."""
    def _rewrite(m: "re.Match[str]") -> str:
        indent = m.group("indent")
        kind = m.group("kind").capitalize()
        title = m.group("title")
        body_lines = m.group("body").split("\n")
        lead = f"{indent}> **{kind}:**"
        if title:
            lead = f"{lead} {title.strip()}"
        out_lines = [lead]
        out_lines.extend(f"{indent}> {line}" for line in body_lines)
        out_lines.append("")  # was close line
        return "\n".join(out_lines)
    return _PYMDOWNX_BLOCK_RE.sub(_rewrite, text)


# MkDocs Material admonitions: "!!! kind [\"title\"]" or "??? kind" / "???+ kind"
# (collapsible) followed by indented body lines. Mistletoe does not understand
# this syntax — the marker line is a plain paragraph and the indented body is
# parsed as either a continuation paragraph or a nested code block depending on
# indent depth, neither of which surfaces the admonition kind to keyword-based
# rules. Rewrite line-by-line into a blockquote so the kind is visible prose.
_MKDOCS_MARKER_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<marker>!!!|\?\?\?\+?)[ \t]+"
    r"(?P<kind>[A-Za-z][A-Za-z0-9-]*)"
    r"(?:[ \t]+\"(?P<title>[^\"]*)\")?[ \t]*$"
)


def _rewrite_mkdocs_admonitions(text: str) -> str:
    """Rewrite MkDocs Material admonitions to blockquotes, preserving line counts.

    The marker line is replaced with `> **Kind:** [title]` and each body line
    (any line indented past the marker, or blank) has its leading indent
    replaced with `> `. Body ends at the first non-blank line not indented past
    the marker.
    """
    lines = text.split("\n")
    out: list = []
    i = 0
    while i < len(lines):
        m = _MKDOCS_MARKER_RE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        base_indent = m.group("indent")
        kind = m.group("kind").capitalize()
        title = m.group("title")
        lead = f"{base_indent}> **{kind}:**"
        if title:
            lead = f"{lead} {title}"
        out.append(lead)
        i += 1
        # Walk body: continue while line is blank or indented past base_indent.
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                out.append(line)
                i += 1
                continue
            stripped_len = len(line) - len(line.lstrip())
            if stripped_len > len(base_indent):
                # Body line — strip extra indent past the marker, prefix with "> ".
                body_text = line[len(base_indent):].lstrip()
                out.append(f"{base_indent}> {body_text}")
                i += 1
                continue
            break
    return "\n".join(out)


# MkDocs Material content tabs (pymdownx.tabbed): consecutive `=== "Title"`
# markers each followed by indented body. Sibling tabs typically present
# alternative-but-equivalent content (e.g. Python 3.10 vs 3.12). Rewrite the
# marker to a bolded blockquote lead and de-indent the body — body content
# becomes visible to lemma/cohesion analysis without the marker line being a
# zero-content sentence.
_MKDOCS_TAB_MARKER_RE = re.compile(
    r"^(?P<indent>[ \t]*)===\+?[ \t]+\"(?P<title>[^\"]*)\"[ \t]*$"
)


def _rewrite_mkdocs_tabs(text: str) -> str:
    """Rewrite `=== \"Title\"` tab markers and their indented bodies to blockquotes."""
    lines = text.split("\n")
    out: list = []
    i = 0
    while i < len(lines):
        m = _MKDOCS_TAB_MARKER_RE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        base_indent = m.group("indent")
        title = m.group("title")
        out.append(f"{base_indent}> **{title}**")
        i += 1
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                out.append(line)
                i += 1
                continue
            stripped_len = len(line) - len(line.lstrip())
            if stripped_len > len(base_indent):
                body_text = line[len(base_indent):].lstrip()
                out.append(f"{base_indent}> {body_text}")
                i += 1
                continue
            break
    return "\n".join(out)


# GitHub Flavored Markdown alerts: a blockquote whose first line is "> [!KIND]"
# where KIND is one of NOTE, TIP, IMPORTANT, WARNING, CAUTION. Rewrite the
# first line to a bold lead inside the blockquote so the kind keyword becomes
# visible prose. Remaining body lines are already prose blockquote content.
_GFM_ALERT_RE = re.compile(
    r"^(?P<indent>[ \t]*)>[ \t]*"
    r"\[!(?P<kind>NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*$",
    re.M,
)


def _rewrite_gfm_alerts(text: str) -> str:
    """Rewrite GFM alert blockquote leads to bold prose, preserving line counts."""
    def _rewrite(m: "re.Match[str]") -> str:
        return f"{m.group('indent')}> **{m.group('kind').capitalize()}:**"
    return _GFM_ALERT_RE.sub(_rewrite, text)


# TODO: Docusaurus admonition support (future).
# Syntax: ":::note\nbody\n:::" with optional title ":::note Title\nbody\n:::".
# Mirror _rewrite_myst_admonitions with a ":::"-delimited regex. Out of scope
# for this round per user direction; track when a Docusaurus corpus appears.
# MDX imports and JSX components are a separate stripping problem and remain
# unsupported.


def _blank_html_comments(text: str) -> str:
    """Replace HTML comment bodies with blanks of equal length, preserving newlines."""
    def _blank(m: "re.Match[str]") -> str:
        return "".join("\n" if c == "\n" else " " for c in m.group(0))
    return _HTML_COMMENT_RE.sub(_blank, text)


# Section annotation blocks: <!--\n---\nkey: value\n---\n-->
# Must be parsed BEFORE _blank_html_comments() strips all HTML comments.
_ANNOTATION_BLOCK_RE = re.compile(
    r"<!--\n---\n(?P<yaml>.+?)\n---\n-->",
    re.DOTALL,
)


def _parse_frontmatter(raw_text: str) -> dict:
    """Parse YAML frontmatter into a dict, normalising field aliases.

    Returns an empty dict when frontmatter is absent, PyYAML is unavailable,
    or the frontmatter block is not valid YAML.
    """
    if not _YAML_AVAILABLE:
        return {}
    m = re.match(r"\A---\n(.*?)\n---\n?", raw_text, re.DOTALL)
    if not m:
        return {}
    try:
        parsed = _yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}

    # Normalise keys using FRONTMATTER_ALIASES
    aliases = getattr(const, "FRONTMATTER_ALIASES", {})
    normalised: dict = {}
    lowered = {k.lower(): v for k, v in parsed.items()}
    for canonical, alias_list in aliases.items():
        for alias in alias_list:
            if alias in lowered:
                normalised[canonical] = lowered[alias]
                break
    # Preserve any keys not covered by aliases
    covered = {a for aliases_for in aliases.values() for a in aliases_for}
    for k, v in lowered.items():
        if k not in covered:
            normalised[k] = v
    return normalised


def _extract_section_annotations(raw_text: str) -> dict:
    """Extract per-section annotation metadata from HTML comment blocks.

    Annotation format (must appear immediately before a heading)::

        <!--
        ---
        topic_type: reference
        audience: architect
        sdlc_phase: design
        ---
        -->
        ## Section Heading

    Returns a dict keyed by 1-based line number of the *following* heading,
    mapping to the parsed YAML dict for that section.  Line numbers are
    computed from ``raw_text`` before any blanking occurs.
    """
    if not _YAML_AVAILABLE:
        return {}
    lines = raw_text.split("\n")
    annotations: dict = {}
    for m in _ANNOTATION_BLOCK_RE.finditer(raw_text):
        try:
            meta = _yaml.safe_load(m.group("yaml")) or {}
        except Exception:
            continue
        if not isinstance(meta, dict):
            continue
        # Find line number of the block's closing "-->" then look ahead for the
        # first ATX heading line after the block.
        block_end_pos = m.end()
        block_end_line = raw_text[:block_end_pos].count("\n")  # 0-based
        for i in range(block_end_line, min(block_end_line + 5, len(lines))):
            if re.match(r"^#{1,6}\s", lines[i]):
                annotations[i + 1] = meta  # 1-based line number
                break
    return annotations


def _strip_inline_html(text: str) -> str:
    """Replace inline HTML tags with spaces, preserving line/column offsets.

    Skips content inside fenced code blocks so HTML used as a code example is
    not corrupted. The fence line itself is preserved verbatim.
    """
    def _blank(m: "re.Match[str]") -> str:
        return " " * len(m.group(0))
    out_lines = []
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            out_lines.append(line)
            in_fence = not in_fence
            continue
        if in_fence:
            out_lines.append(line)
        else:
            out_lines.append(_HTML_TAG_RE.sub(_blank, line))
    return "\n".join(out_lines)


def _strip_myst_roles(text: str) -> str:
    """Strip MyST inline role directives, keeping only the visible label text."""
    text = _MYST_REF_LABEL_RE.sub(r"\1", text)
    text = _MYST_ROLE_RE.sub(r"\1", text)
    return text


def _strip_md_links(text: str) -> str:
    """Replace [text](url) and [text][ref] with just text for NLP input."""
    text = _MYST_REF_LABEL_RE.sub(r"\1", text)
    text = _MYST_ROLE_RE.sub(r"\1", text)
    text = _MD_INLINE_LINK_RE.sub(r"\1", text)
    text = _MD_REF_LINK_RE.sub(r"\1", text)
    return text


_SYNSET_RUNTIME = None


def _get_synset_runtime():
    """Initialize and cache resources needed by `get_synsets`.

    Returns a dict with:
    - nlp: spaCy pipeline used for tokenization/POS
    - spacy_wordnet_attached: whether spacy-wordnet annotator is active
    - wn: NLTK wordnet corpus object (or None)
    """
    global _SYNSET_RUNTIME
    if _SYNSET_RUNTIME is not None:
        return _SYNSET_RUNTIME

    runtime = {"nlp": None, "spacy_wordnet_attached": False, "wn": None}

    try:
        try:
            nlp = spacy.load("en_core_web_sm")
        except Exception:
            nlp = spacy.blank("en")

        runtime["nlp"] = nlp

        try:
            from spacy_wordnet.wordnet_annotator import WordnetAnnotator

            nlp.add_pipe(
                WordnetAnnotator(nlp.vocab), after="tagger", name="spacy_wordnet"
            )
            runtime["spacy_wordnet_attached"] = True
        except Exception:
            runtime["spacy_wordnet_attached"] = False

        # Prepare optional NLTK wordnet once (without repeated download attempts)
        try:
            from nltk import download as _nltk_download
            from nltk.corpus import wordnet as wn

            try:
                wn.synsets("test")
            except Exception:
                _nltk_download("wordnet", quiet=True)
                wn.synsets("test")

            runtime["wn"] = wn
        except Exception:
            runtime["wn"] = None
    except Exception:
        runtime = {"nlp": spacy.blank("en"), "spacy_wordnet_attached": False, "wn": None}

    _SYNSET_RUNTIME = runtime
    return _SYNSET_RUNTIME


def get_synsets(text: str) -> set:
    """Return a set of synset identifiers for nouns and verbs in `text`.

    This helper uses `spacy-wordnet` when available. If the optional
    library isn't installed or the annotator isn't present, an empty set
    is returned.
    """
    synset_ids = set()
    try:
        runtime = _get_synset_runtime()
        nlp = runtime.get("nlp")
        spacy_wordnet_attached = bool(runtime.get("spacy_wordnet_attached"))
        wn = runtime.get("wn")

        if nlp is None:
            return set()

        doc = nlp(text)

        # Prefer spacy-wordnet annotations when available
        if spacy_wordnet_attached:
            for token in doc:
                if token.pos_ not in ("NOUN", "PROPN", "VERB"):
                    continue
                try:
                    wn = getattr(token._, "wordnet", None)
                    candidates = []
                    if wn is None:
                        continue
                    if hasattr(wn, "synsets"):
                        candidates = wn.synsets()
                    elif hasattr(wn, "get_synsets"):
                        candidates = wn.get_synsets()
                    elif isinstance(wn, (list, tuple)):
                        candidates = wn

                    for s in candidates:
                        try:
                            if hasattr(s, "name"):
                                synset_ids.add(s.name())
                            else:
                                synset_ids.add(str(s))
                        except Exception:
                            synset_ids.add(str(s))
                except Exception:
                    continue

        # Fallback: if spacy-wordnet wasn't available or found nothing,
        # try using NLTK's WordNet directly (if installed).
        if not synset_ids and wn is not None:
            try:
                # Use spaCy to tokenize and determine coarse POS, then query NLTK
                for token in doc:
                    if token.pos_ in ("NOUN", "PROPN"):
                        pos_tag = wn.NOUN
                    elif token.pos_ == "VERB":
                        pos_tag = wn.VERB
                    else:
                        continue

                    lemma = getattr(token, "lemma_", token.text).lower()
                    for s in wn.synsets(lemma, pos=pos_tag):
                        try:
                            synset_ids.add(s.name())
                        except Exception:
                            synset_ids.add(str(s))
            except Exception:
                # If NLTK isn't available or fails, we conservatively return
                # whatever we've collected so far (possibly empty).
                pass
    except Exception:
        return set()

    return synset_ids


class CrossFileContext:
    """Accumulates cross-file signals for rules that need document-set awareness.

    term_first_seen:    term → (file_path, section_heading) of first occurrence
    concept_definitions: term → list of paragraph texts where it is defined
    """

    def __init__(self) -> None:
        self.term_first_seen: Dict[str, tuple] = {}
        self.concept_definitions: Dict[str, List[str]] = {}

    def scan(self, paths: List[str], nlp) -> None:
        """First-pass scan: populate term_first_seen across all files."""
        for path in paths:
            try:
                text = open(path, encoding="utf-8").read()
            except OSError:
                continue
            try:
                doc = nlp(text[:50_000])
            except Exception:
                continue
            for token in doc:
                if token.is_alpha and not token.is_stop and len(token.text) >= 4:
                    key = token.lemma_.lower()
                    if key not in self.term_first_seen:
                        self.term_first_seen[key] = (path, "")


class RhetoricEngine:
    def __init__(self):
        self.nlp = self._init_spacy()
        # enable AST parsing when available; can be toggled per-instance
        self.parse_with_mistletoe = True
        # genre detected per file during the last lint_files() call
        self.last_genres: Dict[str, str] = {}
        # external style runners (Vale YAML, markdownlint, etc.)
        self._runners: List[StyleRunner] = []
        # load rule modules — attach GENRES frozenset to each check function
        self.rules = []
        for name in (
            "headings",
            "unity",
            "symmetry",
            "rhetoric",
            "attention",
            "completeness",
            "cohesion",
            "deictic",
            "resilience",
            "curriculum",
            "terminology",
            "lexical_chain",
            "adr",
            "postmortem",
            "concept",
            "troubleshooting",
            "howto",
            "faq",
            "tutorial",
            "reference",
            "explanation",
            "doc_templates",
            "forward_ref",
            "syntactic_depth",
            "nominalizations",
            "metric_density",
            "tone",
            "preferred_form",
            "passive_voice",
            "sentence_rhythm",
            "unsupported_claim",
        ):
            mod = import_module(f"rhetoric_lint.rules.{name}")
            if hasattr(mod, "check"):
                check_fn = mod.check
                check_fn.genres = getattr(mod, "GENRES", frozenset({"all"}))
                self.rules.append(check_fn)

    def _init_runners(self) -> None:
        """Instantiate and load external style runners based on const settings."""
        self._runners = []
        style_dirs = getattr(const, "STYLE_DIRS", [])
        enabled_styles = getattr(const, "ENABLED_STYLES", [])
        markdownlint_enabled = getattr(const, "MARKDOWNLINT_ENABLED", True)
        markdownlint_config = getattr(const, "MARKDOWNLINT_CONFIG", "")

        if style_dirs:
            try:
                from rhetoric_lint.runners.vale_style import ValeStyleRunner
                runner = ValeStyleRunner()
                runner.load(style_dirs=style_dirs, enabled_styles=enabled_styles)
                self._runners.append(runner)
            except ImportError:
                pass

        if markdownlint_enabled:
            try:
                from rhetoric_lint.runners.markdownlint import MarkdownlintRunner
                runner = MarkdownlintRunner()
                runner.load(config_path=markdownlint_config)
                self._runners.append(runner)
            except ImportError:
                pass

    def _parse_with_mistletoe(self, text: str):
        """Optional parser using `mistletoe` to build a section-aware structure.

        Returns a list of sections in the same shape as the fallback parser
        used in `lint_files`, or `None` if `mistletoe` is not available or
        the AST-based parser is not yet implemented.
        """
        if not self.parse_with_mistletoe:
            return None

        try:
            from mistletoe import Document
        except Exception:
            return None

        # helper: moving pointer search to find next occurrence of substring
        # prefer matches that start at a line boundary (preceded by newline or start-of-text)
        def find_next(text, sub, start):
            if not sub:
                return -1
            pos = text.find(sub, start)
            while pos != -1:
                if pos == 0 or text[pos - 1] == "\n":
                    return pos
                pos = text.find(sub, pos + 1)
            # Prefix fallback: inline markup stripping (_node_text) can produce text that
            # doesn't appear verbatim at a line boundary (e.g., "**Bold:** rest" → "Bold: rest").
            # Search for the first 30 chars of sub anywhere after start, then walk back to
            # the line start. This gives the correct line even when char offset is imprecise.
            prefix = sub[:30]
            if len(prefix) >= 8:
                pos = text.find(prefix, start)
                if pos >= 0:
                    return text.rfind("\n", 0, pos) + 1
            return -1

        sections = []
        try:
            doc = Document(text)
        except Exception:
            return None

        cur_section = {
            "level": 0,
            "heading": None,
            "start": 0,
            "end": len(text),
            "paragraphs": [],
        }
        pointer = 0

        def add_paragraph(ptext, pstart, pnodes=None):
            p = {
                "text": ptext.strip(),
                "pos": pstart,
                "end": pstart + len(ptext),
                "line": text[:pstart].count("\n") + 1,
            }
            # attach spaCy doc and sentences; strip inline Markdown link syntax
            # before NLP so [text](url) brackets/slashes don't inflate token counts.
            try:
                pdoc = self.nlp(_strip_md_links(p["text"]))
            except Exception:
                pdoc = None
            p["doc"] = pdoc
            sents = []
            if pdoc is not None:
                for s in pdoc.sents:
                    abs_start = p["pos"] + s.start_char
                    abs_end = p["pos"] + s.end_char
                    sents.append(
                        {
                            "span": s,
                            "start": abs_start,
                            "end": abs_end,
                            "line": text[:abs_start].count("\n") + 1,
                        }
                    )
            p["sentences"] = sents
            p["nodes"] = pnodes or []
            cur_section["paragraphs"].append(p)

        # helper: recursively extract textual content from a mistletoe node
        def _node_text(n):
            # Soft line breaks ("\n" inside a paragraph) are emitted as LineBreak
            # tokens with empty content. Treat them as a single space so adjacent
            # words across a wrapped line don't concatenate ("lives\nin" → "lives in",
            # not "livesin"). Without this, every multi-line paragraph silently
            # loses content overlap signal in cohesion analysis.
            if n.__class__.__name__ == "LineBreak":
                return " "
            txt = getattr(n, "content", None)
            if txt:
                return txt
            out = ""
            if hasattr(n, "children") and n.children:
                for c in n.children:
                    out += _node_text(c) or ""
            return out

        # traverse top-level block tokens
        for node in doc.children:
            # Heading
            if node.__class__.__name__ in ("Heading", "SetextHeading"):
                # flush current section
                if cur_section and (
                    cur_section["heading"] is not None or cur_section["paragraphs"]
                ):
                    cur_section["end"] = pointer
                    sections.append(cur_section)
                # heading text: apply _node_text recursively to each child (not to the
                # Heading node itself — Heading.content is a class-level attribute in
                # mistletoe 1.5.1 that is shared across instances). This handles inline
                # formatting like ***bold italic*** (Strong > Emphasis > RawText).
                heading_text = "".join(
                    _node_text(c) for c in getattr(node, "children", [])
                ).strip()
                # find in original text (prefer line-bound occurrence)
                pos = find_next(text, heading_text, pointer)
                if pos >= 0:
                    line_start = text.rfind("\n", 0, pos) + 1
                    heading_pos = line_start
                else:
                    heading_pos = pointer
                level = getattr(node, "level", 1)
                cur_section = {
                    "level": level,
                    "heading": heading_text,
                    "start": heading_pos,
                    "end": len(text),
                    "paragraphs": [],
                }
                pointer = heading_pos
                continue

            # List blocks
            # Fenced code block
            if (
                node.__class__.__name__ in ("CodeFence", "FencedCode", "BlockCode")
                or getattr(node, "language", None) is not None
            ):
                raw = getattr(node, "content", None)
                if not raw and hasattr(node, "children") and node.children:
                    raw = _node_text(node)
                block_text = raw or ""

                start_pos = find_next(text, block_text, pointer) if block_text else -1
                if start_pos >= 0:
                    block_start = start_pos
                    block_end = start_pos + len(block_text)
                else:
                    block_start = pointer
                    block_end = pointer
                lang = getattr(node, "language", None)
                add_paragraph(
                    text[block_start:block_end],
                    block_start,
                    pnodes=[
                        {
                            "type": "Code",
                            "text": text[block_start:block_end],
                            "start": block_start,
                            "end": block_end,
                            "language": lang,
                        }
                    ],
                )
                pointer = block_end
                continue

            if node.__class__.__name__ == "List":
                # Determine if this is an ordered (ol) or unordered (ul) list
                # Ordered lists in mistletoe have start attribute set to an integer
                # Unordered lists have start=None
                list_type = "ol" if (hasattr(node, "start") and node.start is not None) else "ul"
                
                for item in getattr(node, "children", []):
                    # collect item text recursively
                    item_text = _node_text(item).strip()
                    # try to find the list item as a line item (with marker)
                    pos = -1
                    if item_text:
                        # look for a list marker followed by the item text
                        import re as _re

                        pattern = _re.compile(
                            r"(^|\n)[ \t]*([-*+]|\d+\.)\s+" + _re.escape(item_text),
                            _re.M,
                        )
                        m = pattern.search(text, pointer)
                        if m:
                            pos = m.start(0) + (1 if m.group(1) else 0)
                        else:
                            pos = find_next(text, item_text, pointer)

                    if pos < 0:
                        pos = pointer
                    add_paragraph(
                        item_text,
                        pos,
                        pnodes=[
                            {
                                "type": "ListItem",
                                "text": item_text,
                                "start": pos,
                                "end": pos + len(item_text),
                                "list_type": list_type,
                            }
                        ],
                    )
                    pointer = pos + len(item_text)
                continue

            # Paragraph-like blocks
            if node.__class__.__name__ in (
                "Paragraph",
                "BlockQuote",
                "RawText",
            ) or hasattr(node, "children"):
                para_text = _node_text(node).strip()
                if not para_text:
                    continue
                pos = find_next(text, para_text, pointer)
                if pos < 0:
                    pos = pointer
                node_type = (
                    "Image"
                    if _IMAGE_ONLY_RE.match(para_text)
                    else node.__class__.__name__
                )
                add_paragraph(
                    para_text,
                    pos,
                    pnodes=[
                        {
                            "type": node_type,
                            "text": para_text,
                            "start": pos,
                            "end": pos + len(para_text),
                        }
                    ],
                )
                pointer = pos + len(para_text)
                continue

        # append last section
        if cur_section and (
            cur_section["heading"] is not None or cur_section["paragraphs"]
        ):
            cur_section["end"] = len(text)
            sections.append(cur_section)

        # if no sections found, return None to fallback
        if not sections:
            return None

        return sections

    def _init_spacy(self):
        try:
            nlp = spacy.load("en_core_web_sm")
        except Exception:
            # fallback: load blank english model
            nlp = spacy.blank("en")
        # Ensure sentence segmentation is available even for blank models
        try:
            if (
                "parser" not in nlp.pipe_names
                and "senter" not in nlp.pipe_names
                and "sentencizer" not in nlp.pipe_names
            ):
                nlp.add_pipe("sentencizer")
        except Exception:
            # older spaCy versions use 'Sentencizer' class
            try:
                from spacy.pipeline import Sentencizer

                if "sentencizer" not in nlp.pipe_names:
                    nlp.add_pipe(Sentencizer())
            except Exception:
                pass
        # try to attach spacy-wordnet if available
        try:
            from spacy_wordnet.wordnet_annotator import WordnetAnnotator

            wordnet = WordnetAnnotator(nlp.vocab)
            nlp.add_pipe(wordnet, after="tagger", name="spacy_wordnet")
        except Exception:
            pass
        return nlp

    def lint_files(
        self,
        paths: List[str],
        genre_override: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # First pass: build cross-file context for rules that need document-set awareness
        cross_file = CrossFileContext()
        cross_file.scan(paths, self.nlp)

        issues = []
        for path in paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            except FileNotFoundError:
                continue

            # F2: Parse frontmatter and section annotations from raw text BEFORE
            # any blanking occurs, so metadata is not lost.
            raw_text = text
            frontmatter = _parse_frontmatter(raw_text)
            section_annotations = _extract_section_annotations(raw_text)

            # Strip YAML frontmatter (--- delimited block at start of file).
            # Preserve the original text for line-number accuracy by replacing
            # frontmatter content with blank lines of equal count.
            _fm = re.match(r"\A---\n.*?\n---\n?", text, re.DOTALL)
            if _fm:
                fm_text = _fm.group(0)
                fm_lines = fm_text.count("\n")
                text = "\n" * fm_lines + text[_fm.end():]

            # Blank out Markdown link reference definition lines (e.g. data-URI image
            # definitions: "[img1]: data:image/png;base64,..."). The content is removed
            # but the newline is preserved so all line numbers remain accurate.
            text = _LINK_REF_DEF_RE.sub("", text)

            # Strip HTML comments (line-preserving), rewrite admonition syntax
            # for the three target markup flavors (MyST fences, MkDocs Material,
            # GFM alerts) to blockquotes, and strip MyST inline role directives.
            # All rewriters preserve line counts and are syntactically orthogonal
            # — each is a no-op on docs of the other flavors, so they all run
            # unconditionally without flavor detection.
            text = _blank_html_comments(text)
            text = _rewrite_myst_admonitions(text)
            text = _rewrite_pymdownx_block_admonitions(text)
            text = _rewrite_mkdocs_admonitions(text)
            text = _rewrite_mkdocs_tabs(text)
            text = _rewrite_gfm_alerts(text)
            text = _strip_myst_roles(text)
            # Strip inline HTML last so admonition rewrites (which never produce
            # tags) and role strips run on intact text first. Code-fence content
            # is left alone by design.
            text = _strip_inline_html(text)

            nlp_text = text
            if len(text) > const.NLP_MAX_CHARS:
                cutoff = text.rfind("\n", 0, const.NLP_MAX_CHARS)
                if cutoff == -1:
                    cutoff = const.NLP_MAX_CHARS
                nlp_text = text[:cutoff]
                issues.append({
                    "path": path,
                    "line": 1,
                    "column": 1,
                    "message": (
                        f"Document is {len(text):,} characters; full-document NLP "
                        f"analysis truncated at {const.NLP_MAX_CHARS:,} chars. "
                        f"Section-level checks run on the complete file."
                    ),
                    "severity": "suggestion",
                    "check": "Engine.OversizedDocument",
                })
            doc = self.nlp(nlp_text)

            # Build section-aware structure: headings with their following
            # content so rules can compare paragraphs against the last heading.
            # Prefer mistletoe-based AST parser when enabled and available
            headings = []
            sections = None
            # Always use the mistletoe-based AST parser for this codebase.
            # Fail fast if it is not available or parsing fails so the repository
            # behavior is deterministic and migrations rely on the AST shape.
            try:
                ast_sections = self._parse_with_mistletoe(text)
            except Exception as e:
                raise RuntimeError("mistletoe parser required but failed: %s" % e)

            if not ast_sections:
                raise RuntimeError(
                    "mistletoe parser required but returned no sections; ensure 'mistletoe' is installed and enabled"
                )

            # Use the mistletoe AST-backed sections as authoritative.
            sections = ast_sections
            # derive a simple headings list for compatibility with older rules
            headings = [s.get("heading") for s in sections if s.get("heading")]

            # Classify each section's topic type
            for sec in sections:
                sec["topic_type"] = classify_section_topic(sec, const)

            # F1: Apply section-level annotation overrides.  Annotations are
            # keyed by the 1-based line number of the heading that follows the
            # <!--\n---\n…\n---\n--> block.  topic_type from an annotation
            # takes priority over the classifier result; all other keys are
            # stored in sec["annotation"] for use by rules.
            for sec in sections:
                sec_start = sec.get("start", 0)
                sec_line = raw_text[:sec_start].count("\n") + 1
                if sec_line in section_annotations:
                    ann = section_annotations[sec_line]
                    sec["annotation"] = ann
                    if "topic_type" in ann:
                        sec["topic_type"] = ann["topic_type"]

            # F2: Apply frontmatter overrides.  topic_type in frontmatter sets
            # the first/only section's topic_type when present.
            if frontmatter.get("topic_type") and sections:
                sections[0]["topic_type"] = frontmatter["topic_type"]

            # Detect document genre (or use caller-supplied override)
            genre = genre_override or classify_genre(sections, doc, text, const, path=path)
            self.last_genres[path] = genre

            # Classify doc template (platform/product sub-types within technical)
            doc_template = classify_doc_template(sections, text, const)

            context = {
                "path": path,
                "text": text,
                "doc": doc,
                "headings": headings,
                "sections": sections,
                "nlp": self.nlp,
                "const": const,
                "genre": genre,
                "doc_template": doc_template,
                "cross_file": cross_file,
                "frontmatter": frontmatter,
                "section_annotations": section_annotations,
            }

            gate_enabled = getattr(const, "GENRE_GATE_ENABLED", False)

            for check in self.rules:
                # When the genre gate is active, skip rules whose GENRES set
                # does not include "all" or the detected genre.
                if gate_enabled:
                    rule_genres = getattr(check, "genres", frozenset({"all"}))
                    if "all" not in rule_genres and genre not in rule_genres:
                        continue
                try:
                    found = check(context)
                    if found:
                        issues.extend(found)
                except Exception:
                    # rule errors should not stop the engine
                    continue

            # Dispatch external style runners after Python rules
            for runner in self._runners:
                try:
                    found = runner.check(context)
                    if found:
                        issues.extend(found)
                except Exception:
                    continue

        return issues
