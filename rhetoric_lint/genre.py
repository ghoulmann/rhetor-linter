"""Genre classifier for rhetor-linter.

Document-level classifier producing a Layer-1 genre label that the rule
dispatcher uses to enable distinctive rule sets for ADR and postmortem
artifacts. The classifier itself runs a structural fingerprint over the
parsed sections (block-type inventory, list and table density,
code-fence density) plus a small set of distinctive heading-vocabulary
checks.

Recognized genres
-----------------
  adr         — Architecture Decision Records (Status: field + section
                conventions)
  postmortem  — incident postmortems (timeline, action items, root cause)
  technical   — generic software documentation (≥ 8% code-fence density
                or other strong technical signals)
  general     — software documents that did not trip a stronger signal

Layers 2 (section topic_type) and 3 (doc template) are independent.

Usage
-----
  genre = classify_genre(sections, doc, text, const=None)
"""

import re
from typing import Any, Dict, List

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


def _structural_features(sections: List[Dict[str, Any]], text: str) -> Dict[str, float]:
    total_blocks = 0
    code_fence_count = 0

    for sec in sections:
        for para in sec.get("paragraphs", []):
            total_blocks += 1
            for node in para.get("nodes", []):
                if node.get("type", "") == "Code":
                    code_fence_count += 1

    denom = max(total_blocks, 1)
    return {
        "code_fence_density": code_fence_count / denom,
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
        Document-level spaCy Doc object.  Currently unused; retained for
        signature stability with callers and for future linguistic-feature
        extensions.
    text : str
        Raw document text.
    const : module, optional
        The ``const`` module (used to read threshold constants).

    Returns
    -------
    str
        One of: ``"adr"``, ``"postmortem"``, ``"technical"``, ``"general"``.
    """

    def _t(name, default):
        if const and hasattr(const, name):
            return getattr(const, name)
        return default

    adr_section_min   = _t("GENRE_ADR_SECTION_MIN_MATCHES",        2)
    postmortem_min    = _t("GENRE_POSTMORTEM_HEADING_MIN_MATCHES", 3)
    code_fence_thresh = _t("GENRE_CODE_FENCE_THRESHOLD",           0.08)

    sf = _structural_features(sections, text)

    # ------------------------------------------------------------------
    # Decision tree — ordered by specificity (most distinctive first)
    # ------------------------------------------------------------------

    # 1. ADR: Status: field + ≥ adr_section_min ADR section headings.
    #    Checked before technical because ADRs may contain code.
    adr_has_status, adr_section_count = _count_adr_matches(sections, text)
    if adr_has_status and adr_section_count >= adr_section_min:
        return "adr"

    # 2. Postmortem: ≥ postmortem_min distinctive incident-report headings.
    if _count_postmortem_matches(sections) >= postmortem_min:
        return "postmortem"

    # 3. Technical: meaningful code-fence density.
    if sf["code_fence_density"] >= code_fence_thresh:
        return "technical"

    # 4. General fallback for software docs that didn't trip a stronger signal.
    return "general"
