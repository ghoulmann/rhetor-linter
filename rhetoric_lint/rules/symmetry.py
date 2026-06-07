import re
from typing import Any, Dict, List, Optional, Tuple

from rhetoric_lint.rules._list_utils import group_contiguous_lists

# Structure.TaskOrientation and Symmetry.* are meaningful only for task-oriented
# (technical / how-to) documentation.  For other genres these checks produce
# systematic false positives (e.g. scholarly prose, syllabi).
GENRES = frozenset({"technical", "general"})

# Common action verbs used in task lists (for capitalization fallback)
_ACTION_VERBS = {
    "add", "apply", "build", "check", "choose", "click", "clone",
    "configure", "connect", "create", "delete", "deploy", "disable",
    "download", "enable", "enter", "export", "generate", "import",
    "install", "navigate", "open", "package", "press", "pull", "push",
    "remove", "restart", "run", "save", "select", "set", "start",
    "stop", "test", "trigger", "type", "update", "upgrade", "upload",
    "use", "verify", "view", "write",
}


def _line_from_pos(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def _get_first_token_pos(text: str, nlp) -> Optional[Tuple[Any, str, str]]:
    """Extract first non-punctuation token from text and return (token, pos, tag).
    
    Strips inline code before parsing.
    """
    # Strip inline code/backticks (e.g., `code`) to avoid false positives
    text_clean = re.sub(r"`+.*?`+", "", text).strip()
    if not text_clean:
        return None
    
    try:
        doc = nlp(text_clean)
    except Exception:
        return None
    
    for t in doc:
        if not t.is_space and not t.is_punct:
            pos = t.pos_
            tag = t.tag_
            
            # Fallback: spaCy sometimes tags capitalized verbs as proper nouns (NNP)
            # If it's tagged as NNP but lowercase form is a known action verb, treat as VB
            if tag == "NNP" and t.text.lower() in _ACTION_VERBS:
                pos = "VERB"
                tag = "VB"
            
            return (t, pos, tag)
    
    return None


def _is_task_list(sections: List[Dict], list_start_pos: int, text: str, nlp, const) -> bool:
    """Determine if a list at the given position is a task list.
    
    A list is considered a task list if:
    - The section heading starts with a gerund (VBG) or imperative (VB), OR
    - The section heading contains task keywords, OR
    - Text immediately before the list indicates steps/instructions
    
    UNLESS it matches descriptive/explanatory patterns (checked first).
    """
    # Find which section this list belongs to
    current_section = None
    for sec in sections:
        if sec.get("start", 0) <= list_start_pos < sec.get("end", float("inf")):
            current_section = sec
            break
    
    if not current_section:
        return False
    
    heading = current_section.get("heading", "").strip()
    if not heading:
        return False
    
    heading_lower = heading.lower()
    
    # FIRST: Check for descriptive/explanatory patterns (exclusions take priority)
    # Look at text before the list and the heading
    before_start = max(0, list_start_pos - 200)
    before_text = text[before_start:list_start_pos].lower()
    
    descriptive_patterns = getattr(const, "DESCRIPTIVE_LIST_PATTERNS", [])
    for pattern in descriptive_patterns:
        if pattern in before_text or pattern in heading_lower:
            return False
    
    # Check if heading contains task keywords
    task_keywords = getattr(const, "TASK_LIST_KEYWORDS", [])
    for keyword in task_keywords:
        if keyword in heading_lower:
            return True
    
    # Check if heading starts with gerund or imperative
    heading_token_info = _get_first_token_pos(heading, nlp)
    if heading_token_info:
        _, pos, tag = heading_token_info
        if tag in ("VB", "VBG"):  # Imperative or gerund
            return True
    
    # Check for task intro patterns in text before list
    task_intro_patterns = getattr(const, "TASK_INTRO_PATTERNS", [])
    for pattern in task_intro_patterns:
        if pattern in before_text:
            return True
    
    return False


def _construction_shape(pos: str, tag: str) -> str:
    """Return a normalized first-token construction shape for parallelism checks."""
    if pos == "VERB":
        if tag == "VBG":
            return "VERB_GERUND"
        if tag == "VB":
            return "VERB_BASE"
        return f"VERB_{tag or 'OTHER'}"
    return pos or "UNKNOWN"


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Symmetry-related checks.

    - Symmetry.Parallelism: ensure list items maintain parallel construction.
    - Symmetry.OrderedListImperatives: ensure task list ol items start with imperatives.
    - Structure.TaskOrientation: per-H2 section task density (list items / paragraphs).
    """
    path = context["path"]
    text = context["text"]
    nlp = context.get("nlp")
    const = context.get("const")
    issues: List[Dict[str, Any]] = []

    if not text:
        return []

    # Find all list item lines (simple Markdown list heuristic)
    list_item_re = re.compile(r"^[ \t]*([-*]|\d+\.)\s+(.*)$", re.M)

    # Prefer AST-backed list items when available in context['sections']
    ast_list_items = []
    sections = context.get("sections") or []
    for sec in sections:
        for para in sec.get("paragraphs", []):
            for node in para.get("nodes", []):
                if node.get("type") == "ListItem":
                    ast_list_items.append(
                        {
                            "text": node.get("text") or "",
                            "start": node.get("start") if node.get("start") is not None else para.get("pos", 0),
                            "end": node.get("end") if node.get("end") is not None else para.get("pos", 0),
                            "list_type": node.get("list_type", "ul"),
                        }
                    )

    # identify fenced code spans to ignore list-like lines inside them
    fenced_re = re.compile(r"^```.*$", re.M)
    fenced_spans = []
    for fm in fenced_re.finditer(text):
        # find matching closing fence
        fm2 = fenced_re.search(text, fm.end())
        start = fm.start()
        end = fm2.end() if fm2 else len(text)
        fenced_spans.append((start, end))

    def _in_fenced(pos: int) -> bool:
        for a, b in fenced_spans:
            if a <= pos < b:
                return True
        return False

    # Convert AST list items into pseudo-match objects compatible with grouping logic
    if ast_list_items:
        class _M:
            def __init__(self, text, start, list_type="ul"):
                self._text = text
                self._start = start
                self._list_type = list_type

            def start(self):
                return self._start

            def end(self):
                return self._start + len(self._text)

            def group(self, idx):
                if idx == 2:
                    return self._text
                return None
            
            @property
            def list_type(self):
                return self._list_type

        items = [_M(i["text"], i["start"], i.get("list_type", "ul")) for i in ast_list_items]
    else:
        # Fallback to regex-based detection if AST is not available
        class _M:
            def __init__(self, match_obj):
                self._match = match_obj
                # Detect list type from marker
                marker = match_obj.group(1)
                self._list_type = "ol" if re.match(r"\d+\.", marker) else "ul"

            def start(self):
                return self._match.start()

            def end(self):
                return self._match.end()

            def group(self, idx):
                return self._match.group(idx)
            
            @property
            def list_type(self):
                return self._list_type
        
        items = [_M(m) for m in list_item_re.finditer(text)]
    
    # Filter out items in fenced code blocks
    items = [m for m in items if not _in_fenced(m.start())]
    
    # Group contiguous list items into lists
    lists = group_contiguous_lists(items, text)

    # Symmetry.Parallelism: check for parallel construction in all lists
    min_list_size = getattr(const, "MIN_LIST_SIZE_FOR_PARALLELISM", 4)
    for lst in lists:
        if nlp is None or len(lst) < min_list_size:
            continue
        
        first_tokens = []
        for m in lst:
            item_text = m.group(2).strip()
            if not item_text or item_text.lstrip().startswith("#"):
                continue
            
            token_info = _get_first_token_pos(item_text, nlp)
            if token_info:
                token, pos, tag = token_info
                shape = _construction_shape(pos, tag)
                first_tokens.append((m, token.text, shape))
        
        if not first_tokens or len(first_tokens) < min_list_size:
            continue
        
        # Build frequency map of coarse POS for first tokens
        freq = {}
        for _, _, shape in first_tokens:
            freq[shape] = freq.get(shape, 0) + 1
        
        # Determine dominant POS
        dominant_pos = max(freq.items(), key=lambda x: x[1])[0]
        dominant_count = freq[dominant_pos]
        
        # If at least 3 items follow the dominant pattern, flag outliers
        if dominant_count >= 3:
            for m, tok_text, shape in first_tokens:
                if shape != dominant_pos:
                    line_no = _line_from_pos(text, m.start())
                    issues.append(
                        {
                            "path": path,
                            "line": line_no,
                            "message": f"List item starts with {shape} ('{tok_text}') while most list items start with {dominant_pos} — maintain parallelism",
                            "severity": const.RULE_SEVERITY_LEVELS.get(
                                "Symmetry.Parallelism", "warning"
                            ),
                            "check": "Symmetry.Parallelism",
                        }
                    )
    
    # Symmetry.OrderedListImperatives: check that task list ol items start with imperatives
    for lst in lists:
        if not lst:
            continue
        
        # Check if this is an ordered list
        first_item = lst[0]
        if not hasattr(first_item, 'list_type') or first_item.list_type != "ol":
            continue
        
        # Check if this is a task list
        if not _is_task_list(sections, first_item.start(), text, nlp, const):
            continue
        
        # Check each item starts with an imperative
        for m in lst:
            item_text = m.group(2).strip()
            if not item_text or item_text.lstrip().startswith("#"):
                continue
            
            token_info = _get_first_token_pos(item_text, nlp)
            if not token_info:
                continue
            
            token, pos, tag = token_info
            line_no = _line_from_pos(text, m.start())
            
            # spaCy's detailed tag for imperative base form is 'VB'
            if tag != "VB":
                issues.append(
                    {
                        "path": path,
                        "line": line_no,
                        "message": f"Task list item must start with an imperative verb ('{token.text}' tagged {tag})",
                        "severity": const.RULE_SEVERITY_LEVELS.get(
                            "Symmetry.OrderedListImperatives", "warning"
                        ),
                        "check": "Symmetry.OrderedListImperatives",
                    }
                )

    # Structure.TaskOrientation: compute per-H2 section task density
    # Split document into H2 sections (include content until next H2 or EOF)
    # -------------------------------------------------------------------------
    # Symmetry.TabVariantBalance
    # -------------------------------------------------------------------------
    _tab_variant_balance(issues, sections, path, text, const)

    # Structure.TaskOrientation: compute per-H2 section task density
    # Split document into H2 sections (include content until next H2 or EOF)
    h2_re = re.compile(r"^##\s+(.*)$", re.M)
    h2_matches = list(h2_re.finditer(text))
    section_spans = []
    if not h2_matches:
        # nothing to check
        return issues

    for i, m in enumerate(h2_matches):
        start = m.end()
        end = h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(text)
        title = m.group(1).strip()
        section_spans.append((title, start, end, m.start()))

    # Reference-style heading patterns that should not be evaluated for task density.
    # These sections are informational by nature (tables, exit codes, changelogs).
    _REFERENCE_HEADINGS = re.compile(
        r"^(cli\b|exit\s+code|rule|reference|changelog|license|contributing|"
        r"development|appendix|glossary|faq|feature|comparison|output\s+format|"
        r"supported|compatibility|version|status|credit|acknowledgement|"
        r"summary|recap|overview|introduction|conclusion|background|about|"
        r"devise|strategy|strategies|approach(?:es)?|consideration(?:s)?|"
        r"principle(?:s)?|philosophy|design|concept(?:s)?|rationale|"
        r"theory|framework|architecture|terminology|definitions?)",
        re.I,
    )

    for title, start, end, header_pos in section_spans:
        section_text = text[start:end].strip()
        if not section_text:
            continue

        # Skip reference-style sections: heading matches known patterns, or
        # the section body is dominated by tables (pipe-delimited rows).
        # Strip inline Markdown formatting (**, *, __) before matching so that
        # headings like "**Recap and summary**" still hit the exemption list.
        _clean_title = re.sub(r"^[\*_]+|[\*_]+$", "", title.strip()).strip()
        if _REFERENCE_HEADINGS.match(_clean_title):
            continue
        table_lines = sum(
            1 for ln in section_text.splitlines() if ln.strip().startswith("|")
        )
        total_lines = max(1, len(section_text.splitlines()))
        if table_lines / total_lines > 0.5:
            continue

        # count list items in this section
        list_items = list(list_item_re.finditer(section_text))
        list_count = len(list_items)

        # count fenced code blocks — in technical docs these carry task content
        # (e.g., shell commands, installation steps) just as much as list items do
        code_fence_re = re.compile(r"^```.*?^```", re.M | re.DOTALL)
        code_count = len(code_fence_re.findall(section_text))

        # count admonition leads — the engine rewrites MyST/MkDocs/GFM admonition
        # syntax to blockquotes prefixed with "> **Kind:**". These carry the same
        # instructional content (warnings, notes, tips) as the original fences and
        # should count toward task density.
        admonition_re = re.compile(
            r"^[ \t]*>[ \t]*\*\*"
            r"(?:Note|Warning|Tip|Caution|Important|Danger|Attention|Hint|Seealso)"
            r":\*\*",
            re.M,
        )
        admonition_count = len(admonition_re.findall(section_text))

        # count paragraphs: blocks of text separated by blank lines that are not lists/headings/code
        paras = 0
        for block in re.split(r"\n\s*\n+", section_text):
            s = block.strip()
            if not s:
                continue
            # skip lists and headings and code fences
            if re.match(r"^[#>`~\-\*]", s) or re.match(r"^([-*]|\d+\.)\s+", s):
                continue
            # treat as a paragraph
            paras += 1

        # task_count = list items + code fences + admonitions
        task_count = list_count + code_count + admonition_count
        td = task_count / max(1, task_count + paras)

        if td < const.THRESHOLDS.get("TASK_DENSITY_RATIO", 0.3):
            issues.append(
                {
                    "path": path,
                    "line": _line_from_pos(text, header_pos),
                    "message": f"Section '{title}' appears feature-oriented (task density {td:.2f} < {const.THRESHOLDS.get('TASK_DENSITY_RATIO',0.3):.2f}) — consider adding a task-based list or code examples",
                    "severity": const.RULE_SEVERITY_LEVELS.get(
                        "Structure.TaskOrientation", "warning"
                    ),
                    "check": "Structure.TaskOrientation",
                }
            )

    # -------------------------------------------------------------------------
    # Symmetry.TabVariantBalance
    # -------------------------------------------------------------------------
    _tab_variant_balance(issues, sections, path, text, const)

    return issues


# Tab title pattern: blockquote bold produced by the pymdownx `///` rewriter
# e.g. "> **Tab title**\n> ...\n"
_TAB_TITLE_RE = re.compile(r"^>\s+\*\*(.+?)\*\*\s*$", re.M)


def _tab_variant_balance(
    issues: List[Dict],
    sections: List[Dict],
    path: str,
    text: str,
    const,
) -> None:
    """Symmetry.TabVariantBalance: content-tab variants should have equal step counts."""
    tolerance = getattr(const, "TAB_VARIANT_STEP_TOLERANCE", 1) if const else 1
    severity = (
        const.RULE_SEVERITY_LEVELS.get("Symmetry.TabVariantBalance", "warning")
        if const else "warning"
    )

    for sec in sections:
        if sec.get("topic_type") == "reference":
            continue

        # Collect paragraphs that start with a tab-title blockquote bold pattern
        # and group them into variant clusters
        variants: List[Dict] = []  # list of {title, ol_count, line}
        current_title: Optional[str] = None
        current_ol = 0
        current_line = 0
        # Track whether we're inside a tab-group (consecutive blockquote sections)
        in_tab_group = False

        for para in sec.get("paragraphs", []):
            para_text = para.get("text", "")
            para_line = para.get("line", 1)
            nodes = para.get("nodes", [])

            # Detect tab title: blockquote paragraph whose first line is bold-title
            m = _TAB_TITLE_RE.match(para_text)
            if m:
                # Save previous variant before starting new one
                if current_title is not None:
                    variants.append({
                        "title": current_title,
                        "ol_count": current_ol,
                        "line": current_line,
                    })
                current_title = m.group(1)
                # Count OL items in the title paragraph itself (engine may merge them)
                current_ol = sum(
                    1 for n in nodes
                    if n.get("type") == "ListItem" and n.get("list_type") == "ol"
                )
                current_line = para_line
                in_tab_group = True
            elif in_tab_group and current_title:
                # Accumulate OL items from subsequent paragraphs within this variant
                ol_items = sum(
                    1 for n in nodes
                    if n.get("type") == "ListItem" and n.get("list_type") == "ol"
                )
                current_ol += ol_items

        # Flush last variant
        if current_title is not None and in_tab_group:
            variants.append({
                "title": current_title,
                "ol_count": current_ol,
                "line": current_line,
            })

        if len(variants) < 2:
            continue

        counts = [v["ol_count"] for v in variants]
        # Skip if all variants are code-only (zero steps)
        if max(counts) == 0:
            continue

        step_spread = max(counts) - min(counts)
        if step_spread > tolerance:
            first_line = variants[0]["line"]
            issues.append({
                "path": path,
                "line": first_line,
                "column": 1,
                "message": (
                    f"Content-tab variants have unequal step counts "
                    f"({', '.join(str(c) for c in counts)}) — "
                    f"readers following one variant will have a different experience."
                ),
                "severity": severity,
                "check": "Symmetry.TabVariantBalance",
            })
