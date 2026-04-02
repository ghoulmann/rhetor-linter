"""Genre classifier for rhetor-linter.

Two-phase document-level classifier:
  Phase 1 — structural fingerprint (block-type inventory, citation patterns,
             IMRaD heading detection, list and table density)
  Phase 2 — Biber-derived linguistic features (nominalization ratio,
             passive ratio, imperative density)

Recognized genres
-----------------
  technical   — software/API/DevOps documentation
  scientific  — empirical research papers (IMRaD structure)
  academic    — essays, theses, theoretical writing
  curriculum  — syllabi, course catalogs, training materials
  legal       — contracts, policies, regulations
  general     — everything else

Usage
-----
  genre = classify_genre(sections, doc, text, const=None)
"""

import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# IMRaD heading sets  (primary signal for scientific genre)
#
# "Core" headings are distinctive to empirical research; "peripheral" ones
# (Introduction, Conclusion, References) appear widely in non-scientific
# documents and are not counted toward the IMRaD detection threshold.
# ---------------------------------------------------------------------------
_IMRAD_CORE_HEADINGS = frozenset({
    "abstract",
    "methods",
    "method",
    "methodology",
    "materials and methods",
    "experimental setup",
    "results",
    "results and discussion",
    "discussion",
    "related work",
    "related works",
    "literature review",
    "future work",
})

_IMRAD_PERIPHERAL_HEADINGS = frozenset({
    "introduction",
    "background",
    "conclusion",
    "conclusions",
    "acknowledgements",
    "acknowledgments",
    "references",
    "bibliography",
})

_IMRAD_HEADINGS = _IMRAD_CORE_HEADINGS | _IMRAD_PERIPHERAL_HEADINGS

# ---------------------------------------------------------------------------
# ADR heading sets  (primary signal for adr genre)
# ---------------------------------------------------------------------------
_ADR_SECTION_HEADINGS = frozenset({
    "context", "context and problem statement", "problem statement",
    "decision", "decision outcome", "chosen option",
    "consequences", "trade-offs", "tradeoffs", "impact", "implications",
    "options considered", "considered options", "decision drivers",
    "pros and cons", "positive consequences", "negative consequences",
})

_ADR_STATUS_RE = re.compile(r"^Status:\s*\S", re.M | re.I)

# ---------------------------------------------------------------------------
# Postmortem heading sets  (primary signal for postmortem genre)
# ---------------------------------------------------------------------------
_POSTMORTEM_HEADINGS = frozenset({
    "timeline", "incident timeline", "chronology",
    "impact", "severity", "affected systems",
    "root cause", "root cause analysis", "contributing factors", "cause",
    "action items", "corrective actions", "follow-up actions", "remediation",
    "lessons learned", "what went well", "what went wrong",
    "summary", "incident summary", "overview",
    "detection", "resolution",
})

# Nominalizing suffixes (Biber 1988 condensed)
_NOMINALIZATION_SUFFIXES = (
    "tion", "sion", "ment", "ity", "ance", "ence", "ness", "ism", "ology",
)

# Citation heuristics compiled once
_CITATION_RE = re.compile(
    r"(\([A-Z][a-z]+(?:\s+(?:et al\.?|and\s+[A-Z][a-z]+))?,?\s+\d{4}\))"  # (Author, Year)
    r"|(\[\d+\])"                                                             # [1]
    r"|(^\d+\.\s+[A-Z][a-z]+)",                                              # 1. Surname (bibliography)
    re.M,
)

# Numbered heading: "1. ", "1) ", "I. " etc.
_NUMBERED_HEADING_RE = re.compile(r"^(\d+[\.\)]\s|[IVX]+\.\s)")


def _count_adr_matches(sections: List[Dict[str, Any]], text: str):
    """Return (has_status, section_count) for ADR detection."""
    has_status = bool(_ADR_STATUS_RE.search(text))
    section_count = sum(
        1 for sec in sections
        if (sec.get("heading") or "").strip().lower() in _ADR_SECTION_HEADINGS
    )
    return has_status, section_count


def _count_postmortem_matches(sections: List[Dict[str, Any]]):
    """Return count of postmortem heading matches."""
    return sum(
        1 for sec in sections
        if (sec.get("heading") or "").strip().lower() in _POSTMORTEM_HEADINGS
    )


def _count_imrad_matches(sections: List[Dict[str, Any]]):
    """Return (core_count, total_count) for IMRaD heading matches.

    Core headings (Methods, Results, Discussion, Abstract, …) are distinctive
    to empirical research.  Peripheral headings (Introduction, References, …)
    are common in many genres and are not counted toward the scientific
    detection threshold on their own.
    """
    core = 0
    total = 0
    for sec in sections:
        h = (sec.get("heading") or "").strip().lower()
        if h in _IMRAD_HEADINGS:
            total += 1
        if h in _IMRAD_CORE_HEADINGS:
            core += 1
    return core, total


def _structural_features(sections: List[Dict[str, Any]], text: str) -> Dict[str, float]:
    total_blocks = 0
    code_fence_count = 0
    list_item_count = 0
    table_count = 0
    blockquote_count = 0
    numbered_heading_count = 0
    total_headings = 0

    for sec in sections:
        h = (sec.get("heading") or "").strip()
        if h:
            total_headings += 1
            if _NUMBERED_HEADING_RE.match(h):
                numbered_heading_count += 1
        for para in sec.get("paragraphs", []):
            total_blocks += 1
            for node in para.get("nodes", []):
                ntype = node.get("type", "")
                if ntype == "Code":
                    code_fence_count += 1
                elif ntype == "ListItem":
                    list_item_count += 1
                elif ntype == "Table":
                    table_count += 1
                elif ntype == "BlockQuote":
                    blockquote_count += 1

    citation_matches = len(_CITATION_RE.findall(text))

    denom = max(total_blocks, 1)
    text_len = max(len(text), 1)
    imrad_core, imrad_total = _count_imrad_matches(sections)

    return {
        "code_fence_density": code_fence_count / denom,
        "list_item_density": list_item_count / denom,
        "table_density": table_count / denom,
        "blockquote_density": blockquote_count / denom,
        "citation_density": citation_matches / (text_len / 1000),  # per 1 000 chars
        "numbered_heading_ratio": numbered_heading_count / max(total_headings, 1),
        "imrad_core": imrad_core,
        "imrad_total": imrad_total,
    }


def _linguistic_features(doc) -> Dict[str, float]:
    if doc is None:
        return {"nominalization_ratio": 0.0, "passive_ratio": 0.0, "imperative_density": 0.0}

    alpha_tokens = [t for t in doc if t.is_alpha]
    total_alpha = max(len(alpha_tokens), 1)
    total_sents = max(sum(1 for _ in doc.sents), 1)

    nom_count = sum(
        1 for t in alpha_tokens
        if any(t.text.lower().endswith(suf) for suf in _NOMINALIZATION_SUFFIXES)
    )

    passive_count = sum(
        1 for t in doc if t.dep_ in ("auxpass", "nsubjpass")
    )

    imp_count = 0
    for sent in doc.sents:
        for tok in sent:
            if tok.is_space or tok.is_punct:
                continue
            if tok.tag_ == "VB":
                imp_count += 1
            break

    return {
        "nominalization_ratio": nom_count / total_alpha,
        "passive_ratio": passive_count / total_alpha,
        "imperative_density": imp_count / total_sents,
    }


def classify_genre(
    sections: List[Dict[str, Any]],
    doc,
    text: str,
    const=None,
) -> str:
    """Classify the document genre.

    Parameters
    ----------
    sections : list
        Section list as produced by ``RhetoricEngine._parse_with_mistletoe``.
    doc : spaCy Doc
        Document-level spaCy Doc object.
    text : str
        Raw document text.
    const : module, optional
        The ``const`` module (used to read threshold constants).

    Returns
    -------
    str
        One of: ``"adr"``, ``"postmortem"``, ``"technical"``,
        ``"scientific"``, ``"academic"``, ``"curriculum"``, ``"legal"``,
        ``"general"``.
    """

    def _t(name, default):
        if const and hasattr(const, name):
            return getattr(const, name)
        return default

    adr_section_min       = _t("GENRE_ADR_SECTION_MIN_MATCHES",    2)
    postmortem_min        = _t("GENRE_POSTMORTEM_HEADING_MIN_MATCHES", 3)
    code_fence_thresh     = _t("GENRE_CODE_FENCE_THRESHOLD",       0.08)
    citation_thresh       = _t("GENRE_CITATION_THRESHOLD",          0.04)
    blockquote_thresh     = _t("GENRE_BLOCKQUOTE_THRESHOLD",        0.02)
    table_thresh          = _t("GENRE_TABLE_THRESHOLD",             0.03)
    numbered_hdg_thresh   = _t("GENRE_NUMBERED_HEADING_THRESHOLD",  0.30)
    list_item_thresh      = _t("GENRE_LIST_ITEM_THRESHOLD",         0.30)
    nominalization_thresh = _t("GENRE_NOMINALIZATION_THRESHOLD",    0.08)
    passive_thresh        = _t("GENRE_PASSIVE_THRESHOLD",           0.15)
    imrad_min             = _t("GENRE_IMRAD_HEADING_MIN_MATCHES",   2)

    sf = _structural_features(sections, text)
    lf = _linguistic_features(doc)

    # ------------------------------------------------------------------
    # Decision tree — ordered by specificity (most distinctive first)
    # ------------------------------------------------------------------

    # 0a. ADR: Status: field + ≥ adr_section_min ADR section headings.
    #     Checked before technical/scientific because ADRs may contain code.
    adr_has_status, adr_section_count = _count_adr_matches(sections, text)
    if adr_has_status and adr_section_count >= adr_section_min:
        return "adr"

    # 0b. Postmortem: ≥ postmortem_min distinctive incident-report headings.
    if _count_postmortem_matches(sections) >= postmortem_min:
        return "postmortem"

    # 1. Scientific: IMRaD heading structure is the strongest single signal.
    #    Require ≥ imrad_min CORE headings (Methods/Results/Discussion/…).
    #    Peripheral-only matches (Introduction + References) are not sufficient.
    if sf["imrad_core"] >= imrad_min:
        return "scientific"

    # 2. Technical: meaningful code-fence density
    if sf["code_fence_density"] >= code_fence_thresh:
        return "technical"

    # 3. Curriculum: numbered headings + tables OR numbered headings + high
    #    list density (modules/topics lists without tables)
    if sf["numbered_heading_ratio"] >= numbered_hdg_thresh and (
        sf["table_density"] >= table_thresh
        or sf["list_item_density"] >= list_item_thresh
    ):
        return "curriculum"

    # 4. Academic: citations + blockquotes (argumentative scholarly prose)
    if sf["citation_density"] >= citation_thresh and sf["blockquote_density"] >= blockquote_thresh:
        return "academic"

    # 5. Academic: citation-heavy + nominalization-heavy (no blockquotes required)
    if sf["citation_density"] >= citation_thresh and lf["nominalization_ratio"] >= nominalization_thresh:
        return "academic"

    # 6. Legal: passive + nominalization + numbered headings
    if (
        lf["passive_ratio"] >= passive_thresh
        and lf["nominalization_ratio"] >= nominalization_thresh
        and sf["numbered_heading_ratio"] >= numbered_hdg_thresh
    ):
        return "legal"

    # 7. Curriculum fallback: numbered headings alone when other signals are weak
    if sf["numbered_heading_ratio"] >= numbered_hdg_thresh:
        return "curriculum"

    # 8. General fallback
    return "general"
