import re
from importlib import import_module
from typing import Any, Dict, List, Optional

import spacy

import rhetoric_lint.const as const
from rhetoric_lint.genre import classify_genre
from rhetoric_lint.topic_type import classify_section_topic
from rhetoric_lint.template_type import classify_doc_template

# Pre-processing: link reference definition lines (e.g. "[img1]: data:image/png;base64,...")
# These are blanked out (content replaced, newline kept) before parsing so they don't
# appear as Paragraph nodes and trigger false positives in ComplexitySpike and other rules.
_LINK_REF_DEF_RE = re.compile(r"^\[.*?\]:\s+\S[^\n]*", re.M)

# Image-only paragraph detection (single-line image references with no surrounding prose)
_IMAGE_ONLY_RE = re.compile(r"^!\[.*?\](?:\[.*?\]|\(.*?\))$", re.DOTALL)

# Inline Markdown link stripping for NLP token counts — replaces [text](url) / [text][ref]
# with just `text` so URL path segments don't inflate sentence token counts.
_MD_INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_MD_REF_LINK_RE = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")


def _strip_md_links(text: str) -> str:
    """Replace [text](url) and [text][ref] with just text for NLP input."""
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


class RhetoricEngine:
    def __init__(self):
        self.nlp = self._init_spacy()
        # enable AST parsing when available; can be toggled per-instance
        self.parse_with_mistletoe = True
        # genre detected per file during the last lint_files() call
        self.last_genres: Dict[str, str] = {}
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
        ):
            mod = import_module(f"rhetoric_lint.rules.{name}")
            if hasattr(mod, "check"):
                check_fn = mod.check
                check_fn.genres = getattr(mod, "GENRES", frozenset({"all"}))
                self.rules.append(check_fn)

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
        issues = []
        for path in paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            except FileNotFoundError:
                continue

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

            # Detect document genre (or use caller-supplied override)
            genre = genre_override or classify_genre(sections, doc, text, const)
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

        return issues
