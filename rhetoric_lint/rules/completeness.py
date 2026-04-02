import re
from typing import Any, Dict, List, Optional

from rhetoric_lint.engine import get_synsets

# Completeness checks (ResultVerification, SchemaMapping, ActionableHeadings)
# are meaningful only for task-oriented / API documentation.
GENRES = frozenset({"technical", "general"})


def _line_from_pos(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def _slugify(text: str) -> str:
    s = re.sub(r"[^\w\-\s]", "", text.lower())
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "section"


def _is_task_heading(text: str) -> bool:
    return (
        re.match(
            r"^(how to\b|deploy|deploying|install|setup|configure)",
            text.strip().lower(),
        )
        is not None
    )


def _is_api_section(text: str) -> bool:
    low = text.strip().lower()
    return any(
        k in low for k in ("api", "reference", "endpoint", "response", "payload")
    )


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Completeness checks described in the project task.

    Implements:
    - Completeness.ResultVerification
    - Completeness.SchemaMapping
    - Structure.WallOfText
    - Navigation.FindabilityMap
    - Structure.ActionableHeadings
    """
    path = context.get("path")
    text = context.get("text", "")
    nlp = context.get("nlp")
    const = context.get("const")
    issues: List[Dict[str, Any]] = []

    if not text:
        return []

    # Build nodes from AST-backed `sections` provided by the engine.
    nodes: List[Dict[str, Any]] = []
    sections = context.get("sections", []) or []
    for s in sections:
        # heading node for the section (if present)
        if s.get("heading"):
            hnode: Dict[str, Any] = {
                "type": "Heading",
                "level": s.get("level", 0),
                "heading_text": s.get("heading"),
                "pos": s.get("start", 0),
                "text": s.get("heading"),
                "line": _line_from_pos(text, s.get("start", 0)),
                "id": _slugify(s.get("heading", "")),
            }
            nodes.append(hnode)

        # append paragraphs / blocks inside the section
        for p in s.get("paragraphs", []):
            # if paragraph has explicit nodes produced by the AST parser, prefer those
            pnodes = p.get("nodes") or []
            if pnodes:
                for pn in pnodes:
                    ntype = pn.get("type", "Paragraph")
                    node = {
                        "type": ntype,
                        "pos": pn.get("start", p.get("pos", 0)),
                        "text": pn.get("text", p.get("text", "")),
                        "line": p.get("line", _line_from_pos(text, p.get("pos", 0))),
                    }
                    # carry through language / id / level when available
                    if pn.get("language"):
                        node["language"] = pn.get("language")
                    if pn.get("type") == "ListItem":
                        node["type"] = "List"
                    nodes.append(node)
            else:
                # generic paragraph
                nodes.append(
                    {
                        "type": "Paragraph",
                        "pos": p.get("pos", 0),
                        "text": p.get("text", ""),
                        "line": p.get("line", _line_from_pos(text, p.get("pos", 0))),
                    }
                )

    # Collect heading ids for internal link checks
    heading_ids = [n["id"] for n in nodes if n.get("type") == "Heading"]

    # Navigation.FindabilityMap: check first two paragraphs for internal links
    intro_paras = [n for n in nodes if n["type"] == "Paragraph"][:2]
    internal_links = 0
    for para in intro_paras:
        # find markdown links pointing to heading ids e.g. [x](#some-id)
        for m in re.finditer(r"\[[^\]]+\]\(#([^\)]+)\)", para["text"]):
            target = m.group(1).strip().lower()
            if target in heading_ids:
                internal_links += 1

    if len(heading_ids) > 5 and internal_links < 2:
        issues.append(
            {
                "path": path,
                "line": 1,
                "message": "Poor Findability: document has many headings but the intro lacks sufficient internal navigation links. Add an 'In this article' section with links to major sections.",
                "severity": (
                    const.RULE_SEVERITY_LEVELS.get(
                        "Navigation.FindabilityMap", "warning"
                    )
                    if const
                    else "warning"
                ),
                "check": "Navigation.FindabilityMap",
            }
        )

    # Iterate nodes for other checks
    # Helper: find previous heading text for a node index
    def _prev_heading(idx: int) -> Optional[Dict[str, Any]]:
        for j in range(idx - 1, -1, -1):
            if nodes[j]["type"] == "Heading":
                return nodes[j]
        return None

    # For Structure.WallOfText: find sequences of Heading/Paragraph without list/blockquote/code/table
    seq_start = None
    seq_words = 0
    for i, n in enumerate(nodes):
        if n["type"] in ("Paragraph", "Heading"):
            # count words
            words = re.findall(r"\w+", n["text"]) or []
            if seq_start is None:
                seq_start = i
                seq_words = 0
            seq_words += len(words)
            if seq_words > 500:
                issues.append(
                    {
                        "path": path,
                        "line": nodes[seq_start]["line"],
                        "message": "Cognitive Overload: long run of paragraphs/headings (>500 words) without lists, notes, or code — consider breaking into sections or adding lists/examples",
                        "severity": (
                            const.RULE_SEVERITY_LEVELS.get(
                                "Structure.WallOfText", "warning"
                            )
                            if const
                            else "warning"
                        ),
                        "check": "Structure.WallOfText",
                    }
                )
                # reset after flagging to avoid duplicate flags for the same long run
                seq_start = None
                seq_words = 0
        else:
            seq_start = None
            seq_words = 0

    # Completeness.ResultVerification & SchemaMapping & ActionableHeadings
    for i, n in enumerate(nodes):
        # ResultVerification: List under a task heading
        if n["type"] == "List":
            prev_h = _prev_heading(i)
            if prev_h and _is_task_heading(prev_h.get("heading_text", "")):
                # next sibling
                next_n = nodes[i + 1] if i + 1 < len(nodes) else None
                ok = False
                if next_n and next_n["type"] == "Code":
                    ok = True
                if next_n and next_n["type"] == "Paragraph":
                    if re.match(
                        r"^(you should see|expected result)",
                        next_n["text"].strip(),
                        re.I,
                    ):
                        ok = True
                if not ok:
                    issues.append(
                        {
                            "path": path,
                            "line": n["line"],
                            "message": "Result Verification Gap: task list is not followed by an expected output or explanatory paragraph starting with 'You should see' or 'Expected result'",
                            "severity": (
                                const.RULE_SEVERITY_LEVELS.get(
                                    "Completeness.ResultVerification", "warning"
                                )
                                if const
                                else "warning"
                            ),
                            "check": "Completeness.ResultVerification",
                        }
                    )

        # SchemaMapping: inside API reference sections (H2/H3)
        if (
            n["type"] == "Heading"
            and n.get("level") in (2, 3)
            and _is_api_section(n.get("heading_text", ""))
        ):
            # collect nodes until next heading of same or higher level
            code_count = 0
            table_count = 0
            j = i + 1
            while j < len(nodes):
                nn = nodes[j]
                if nn["type"] == "Heading" and nn.get("level", 10) <= n.get("level"):
                    break
                if nn["type"] == "Code":
                    # heuristics: json code fences or code block starting with '{'
                    lang = (nn.get("language") or "").lower()
                    body = nn["text"].strip().splitlines()[1:]
                    body_text = "\n".join(body).strip()
                    if lang == "json" or body_text.startswith("{"):
                        code_count += 1
                if nn["type"] == "Table":
                    table_count += 1
                j += 1

            if code_count > 0 and table_count == 0:
                issues.append(
                    {
                        "path": path,
                        "line": n["line"],
                        "message": "Schema Gap: JSON response examples found in API section but no corresponding table documenting response fields",
                        "severity": (
                            const.RULE_SEVERITY_LEVELS.get(
                                "Completeness.SchemaMapping", "warning"
                            )
                            if const
                            else "warning"
                        ),
                        "check": "Completeness.SchemaMapping",
                    }
                )

        # Structure.ActionableHeadings: for H2 nodes, ensure noun/verb presence
        if n["type"] == "Heading" and n.get("level") == 2:
            htext = n.get("heading_text", "")
            doc = None
            has_nv = False
            if nlp:
                try:
                    doc = nlp(htext)
                    has_nv = any(
                        t.pos_ in ("NOUN", "PROPN", "VERB") for t in doc if t.is_alpha
                    )
                except Exception:
                    doc = None

            # fallback: simple heuristic
            if not doc:
                words = [w for w in re.findall(r"\w+", htext) if len(w) > 2]
                has_nv = len(words) > 0

            # detect >80% stop-words
            stop_ratio = 0.0
            if doc and len([t for t in doc if t.is_alpha]) > 0:
                alpha = [t for t in doc if t.is_alpha]
                stop_ratio = sum(1 for t in alpha if t.is_stop) / len(alpha)

            generic_tokens = (
                set(getattr(const, "GENERIC_HEADINGS", [])) if const else set()
            )
            low = htext.strip().lower()
            generic_flag = low in generic_tokens or stop_ratio > 0.8 or not has_nv

            if generic_flag:
                # try to suggest alternatives via synsets if available
                suggestion = "Use a concrete noun or an action-oriented verb (e.g., 'Deploy service', 'Configure SSO')."
                try:
                    syns = get_synsets(htext)
                    if syns:
                        suggestion = "Make the heading specific and include domain nouns or verbs (e.g., 'Call API', 'Parse response fields')."
                except Exception:
                    pass

                issues.append(
                    {
                        "path": path,
                        "line": n["line"],
                        "message": "Vague Heading: H2 is generic or mostly stop-words — consider a concrete, actionable heading.",
                        "detail": suggestion,
                        "severity": (
                            const.RULE_SEVERITY_LEVELS.get(
                                "Structure.ActionableHeadings", "suggestion"
                            )
                            if const
                            else "suggestion"
                        ),
                        "check": "Structure.ActionableHeadings",
                    }
                )

    # Completeness.ConceptOverload: flag sections with too much prose before action
    max_prose_before_action = (
        int(getattr(const, "COMPLETENESS_MAX_PROSE_BEFORE_ACTION", 3)) if const else 3
    )
    max_prose_only = (
        int(getattr(const, "COMPLETENESS_MAX_PROSE_ONLY_PARAGRAPHS", 5)) if const else 5
    )
    action_types = {"ListItem", "List", "Code", "CodeFence", "FencedCode", "BlockCode"}

    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        paras = sec.get("paragraphs", [])
        if not paras:
            continue

        sec_line = _line_from_pos(text, sec.get("start", 0))

        # Count consecutive prose paragraphs before first action element
        prose_before_action = 0
        has_action = False
        for para in paras:
            nodes = para.get("nodes") or []
            node_type = str(nodes[0].get("type", "Paragraph")) if nodes else "Paragraph"
            if node_type in action_types:
                has_action = True
                break
            if node_type in ("Paragraph", "BlockQuote", "RawText"):
                prose_before_action += 1

        is_task = _is_task_heading(heading)

        if is_task and has_action and prose_before_action > max_prose_before_action:
            issues.append(
                {
                    "path": path,
                    "line": sec_line,
                    "message": (
                        f"This task section has {prose_before_action} paragraphs of explanation "
                        f"before the first actionable step. "
                        f"Consider moving background information after the steps or into a separate section."
                    ),
                    "severity": (
                        const.RULE_SEVERITY_LEVELS.get(
                            "Completeness.ConceptOverload", "suggestion"
                        )
                        if const
                        else "suggestion"
                    ),
                    "check": "Completeness.ConceptOverload",
                }
            )
        elif not is_task and not has_action:
            # Non-task section: flag if all paragraphs are prose with no structural variety
            total_prose = sum(
                1 for p in paras
                if (str((p.get("nodes") or [{}])[0].get("type", "Paragraph"))
                    if p.get("nodes") else "Paragraph")
                in ("Paragraph", "BlockQuote", "RawText")
            )
            if total_prose > max_prose_only:
                issues.append(
                    {
                        "path": path,
                        "line": sec_line,
                        "message": (
                            f"This section has {total_prose} consecutive paragraphs "
                            f"with no lists, code examples, or other structural elements. "
                            f"Consider breaking it up to improve readability."
                        ),
                        "severity": (
                            const.RULE_SEVERITY_LEVELS.get(
                                "Completeness.ConceptOverload", "suggestion"
                            )
                            if const
                            else "suggestion"
                        ),
                        "check": "Completeness.ConceptOverload",
                    }
                )

    # Completeness.StructureLead: heading immediately followed by structure without a lead sentence
    min_list_items_for_lead = (
        int(getattr(const, "COMPLETENESS_STRUCT_LEAD_MIN_LIST_ITEMS", 3)) if const else 3
    )

    # Self-describing reference headings that don't require a lead sentence —
    # the heading itself is the introduction (e.g., "Exit codes" → table of exit codes).
    _STRUCT_LEAD_EXEMPT_RE = re.compile(
        r"^(cli\b|api\b|exit\s+code|changelog|license|contributing|"
        r"appendix|glossary|credits?|acknowledgements?|column|field|"
        r"parameter|option|flag|attribute)",
        re.I,
    )

    _STRUCTURAL_TYPES = frozenset(
        {"ListItem", "List", "Code", "CodeFence", "FencedCode", "BlockCode"}
    )

    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        if not heading or sec.get("level", 0) == 1:
            continue

        # Strip inline Markdown formatting before exemption matching
        clean_heading = re.sub(r"[\*_`]+", "", heading).strip()

        if _STRUCT_LEAD_EXEMPT_RE.match(clean_heading):
            continue

        # Heading ending with ':' already forms a complete stem sentence
        if clean_heading.rstrip().endswith(":"):
            continue

        paras = sec.get("paragraphs", [])
        if not paras:
            continue

        first_para = paras[0]
        first_nodes = first_para.get("nodes") or []
        if not first_nodes:
            continue
        first_type = first_nodes[0].get("type", "Paragraph")

        if first_type not in _STRUCTURAL_TYPES:
            continue  # starts with prose — fine

        is_code = first_type in ("Code", "CodeFence", "FencedCode", "BlockCode")
        if not is_code:
            list_item_count = sum(
                1 for p in paras
                if ((p.get("nodes") or [{}])[0].get("type") in ("ListItem", "List"))
            )
            if list_item_count < min_list_items_for_lead:
                continue

        struct_line = _line_from_pos(text, first_para.get("pos", sec.get("start", 0)))
        content_type = "code block" if is_code else "list"
        issues.append(
            {
                "path": path,
                "line": struct_line,
                "message": (
                    f"Section '{heading}' opens directly with a {content_type} without a lead "
                    f"sentence — add a sentence explaining what this {content_type} contains "
                    f"and why it matters"
                ),
                "severity": (
                    const.RULE_SEVERITY_LEVELS.get("Completeness.StructureLead", "suggestion")
                    if const
                    else "suggestion"
                ),
                "check": "Completeness.StructureLead",
            }
        )

    return issues
