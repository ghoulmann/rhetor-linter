"""Genre classifier for rhetor-linter.

Document-level classifier producing a genre label used by the rule dispatcher
to enable genre-specific rule stacks.

Recognized genres
-----------------
  howto       — task-oriented ("how to configure X")
  tutorial    — learning walkthrough ("build your first X")
  concept     — explanatory ("what is X, how does it work")
  explanation — detailed background exposition
  reference   — lookup material (API docs, CLI options, data dict)
  adr         — Architecture Decision Records
  postmortem  — incident postmortems (timeline, action items, root cause)
  changelog   — version history (Keep a Changelog, GitHub releases format)
  readme      — project README files
  general     — fallback

Layers 2 (section topic_type) and 3 (doc template) are independent.

Classification priority
-----------------------
1. Filename-based (README, CHANGELOG, CONTRIBUTING, etc.)
2. ADR heading constellation + Status: field
3. Postmortem heading constellation
4. Changelog version-heading pattern
5. Dominant section topic_type (sections already classified before this runs)
6. General fallback
"""

import os
import re
from collections import Counter
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# ADR heading sets
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
# Postmortem heading sets
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

# ---------------------------------------------------------------------------
# Changelog patterns
# ---------------------------------------------------------------------------
# Matches: ## [1.2.0], ## v1.2.3, ## 1.2.0, ## 1.2.0 (2024-01-01)
_CHANGELOG_VERSION_RE = re.compile(
    r"^#{1,3}\s+(?:\[[\d.]+\]|v\d[\d.]+|\d+\.\d[\d.]*)",
    re.M,
)

_CHANGELOG_SECTION_HEADINGS = frozenset({
    "added", "changed", "fixed", "removed", "deprecated", "security",
    "unreleased",
})

# ---------------------------------------------------------------------------
# Filename → genre map  (stem uppercased for matching)
# ---------------------------------------------------------------------------
_FILENAME_GENRE: dict[str, str] = {
    "README":       "readme",
    "CHANGELOG":    "changelog",
    "HISTORY":      "changelog",
    "RELEASES":     "changelog",
    "CONTRIBUTING": "howto",
    "SECURITY":     "howto",
}

# ---------------------------------------------------------------------------
# topic_type → genre mapping for dominant-topic inference
# ---------------------------------------------------------------------------
_TOPIC_TO_GENRE: dict[str, str] = {
    "howto":        "howto",
    "how-to":       "howto",
    "tutorial":     "tutorial",
    "concept":      "concept",
    "conceptual":   "concept",
    "explanation":  "explanation",
    "explanatory":  "explanation",
    "reference":    "reference",
    "ref":          "reference",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _count_adr_matches(sections: List[Dict[str, Any]], text: str):
    has_status = bool(_ADR_STATUS_RE.search(text))
    section_count = sum(
        1 for sec in sections
        if (sec.get("heading") or "").strip().lower() in _ADR_SECTION_HEADINGS
    )
    return has_status, section_count


def _count_postmortem_matches(sections: List[Dict[str, Any]]) -> int:
    return sum(
        1 for sec in sections
        if (sec.get("heading") or "").strip().lower() in _POSTMORTEM_HEADINGS
    )


def _count_changelog_signals(sections: List[Dict[str, Any]], text: str):
    version_hits = len(_CHANGELOG_VERSION_RE.findall(text))
    section_hits = sum(
        1 for sec in sections
        if (sec.get("heading") or "").strip().lower() in _CHANGELOG_SECTION_HEADINGS
    )
    return version_hits, section_hits


def _genre_from_filename(path: str) -> Optional[str]:
    stem = os.path.splitext(os.path.basename(path or ""))[0].upper()
    return _FILENAME_GENRE.get(stem)


def _genre_from_dominant_topic(sections: List[Dict[str, Any]]) -> Optional[str]:
    """Infer document genre from the majority topic_type across sections.

    Sections are already classified before classify_genre() runs (engine.py).
    Returns None if no clear majority (< 50%).
    """
    counts: Counter = Counter()
    for sec in sections:
        tt = (sec.get("topic_type") or "").strip().lower()
        mapped = _TOPIC_TO_GENRE.get(tt)
        if mapped:
            counts[mapped] += 1

    if not counts:
        return None

    dominant, top_count = counts.most_common(1)[0]
    total = sum(counts.values())
    if top_count / total >= 0.5:
        return dominant
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_genre(
    sections: List[Dict[str, Any]],
    doc,
    text: str,
    const=None,
    path: str = "",
) -> str:
    """Classify the document genre.

    Parameters
    ----------
    sections : list
        Section list as produced by RhetoricEngine._parse_with_mistletoe,
        with topic_type already assigned to each section.
    doc : spaCy Doc
        Document-level spaCy Doc (currently unused; retained for signature
        stability and future linguistic-feature extensions).
    text : str
        Raw document text.
    const : module, optional
        The const module (threshold constants).
    path : str, optional
        File path — used for filename-based genre detection.

    Returns
    -------
    str
        One of the recognized genre strings.
    """

    def _t(name, default):
        return getattr(const, name, default) if const else default

    adr_section_min  = _t("GENRE_ADR_SECTION_MIN_MATCHES",       2)
    postmortem_min   = _t("GENRE_POSTMORTEM_HEADING_MIN_MATCHES", 3)

    # 1. Filename-based (highest priority — unambiguous naming conventions)
    if path:
        fn_genre = _genre_from_filename(path)
        if fn_genre:
            return fn_genre

    # 2. ADR: Status: field + ≥ N ADR section headings
    adr_has_status, adr_section_count = _count_adr_matches(sections, text)
    if adr_has_status and adr_section_count >= adr_section_min:
        return "adr"

    # 3. Postmortem: ≥ N distinctive incident-report headings
    if _count_postmortem_matches(sections) >= postmortem_min:
        return "postmortem"

    # 4. Changelog: version headings + Keep-a-Changelog section names
    version_hits, changelog_section_hits = _count_changelog_signals(sections, text)
    if version_hits >= 2 or (version_hits >= 1 and changelog_section_hits >= 2):
        return "changelog"

    # 5. Dominant section topic_type
    topic_genre = _genre_from_dominant_topic(sections)
    if topic_genre:
        return topic_genre

    # 6. General fallback
    return "general"
