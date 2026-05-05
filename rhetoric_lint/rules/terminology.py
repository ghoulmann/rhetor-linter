from __future__ import annotations

from typing import Any, Dict, List, Set

from rhetoric_lint.engine import get_synsets
from rhetoric_lint.overlap import channelize_tokens

GENRES = frozenset({"all"})

# Nouns too generic to flag as terminology drift
_GENERIC_NOUNS = {
    "section", "paragraph", "example", "thing", "content", "text",
    "way", "part", "time", "point", "item", "type", "kind", "form",
    "case", "method", "result", "value", "data", "information",
}


def _section_content_lemmas(section: Dict[str, Any], pronouns: set) -> Dict[str, Set[str]]:
    """Return {lemma: {surface_forms}} for non-PROPN content tokens in a section."""
    lemma_surfaces: Dict[str, Set[str]] = {}
    for para in section.get("paragraphs", []):
        for srec in para.get("sentences", []):
            span = srec.get("span")
            if span is None:
                continue
            for tok in span:
                if not getattr(tok, "is_alpha", False):
                    continue
                if getattr(tok, "is_stop", False):
                    continue
                if getattr(tok, "pos_", "") == "PROPN":
                    continue
                surface = tok.text.lower().strip()
                if len(surface) < 4:
                    continue
                if surface in _GENERIC_NOUNS:
                    continue
                lem = (getattr(tok, "lemma_", "") or surface).lower().strip()
                if not lem or lem in _GENERIC_NOUNS:
                    continue
                lemma_surfaces.setdefault(lem, set()).add(surface)
    return lemma_surfaces


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Cohesion.TerminologyDrift — flag synonym pairs used in different sections.

    Uses WordNet synsets to detect when two different terms (e.g., 'endpoint'
    and 'route') that share a synset appear in different sections, suggesting
    inconsistent terminology.
    """
    issues: List[Dict[str, Any]] = []
    path = context.get("path", "")
    text = context.get("text", "")
    const = context.get("const")
    sections = context.get("sections", [])

    if len(sections) < 2:
        return []

    pronouns = set(getattr(const, "PRONOUNS", [])) if const else set()
    severity = (
        getattr(const, "RULE_SEVERITY_LEVELS", {}).get("Cohesion.TerminologyDrift", "suggestion")
        if const else "suggestion"
    )

    # Build per-section lemma sets (excluding shared lemmas — only unique-to-section)
    section_lemmas: List[Dict[str, Set[str]]] = []
    for sec in sections:
        section_lemmas.append(_section_content_lemmas(sec, pronouns))

    # Build document-wide lemma → set of section indices
    lemma_sections: Dict[str, Set[int]] = {}
    for idx, sl in enumerate(section_lemmas):
        for lem in sl:
            lemma_sections.setdefault(lem, set()).add(idx)

    # Find lemmas unique to each section (present in exactly one section)
    unique_by_section: Dict[int, Set[str]] = {}
    for lem, sec_idxs in lemma_sections.items():
        if len(sec_idxs) == 1:
            idx = next(iter(sec_idxs))
            unique_by_section.setdefault(idx, set()).add(lem)

    if not unique_by_section:
        return []

    # Cache synsets per lemma for performance
    synset_cache: Dict[str, set] = {}

    # Synset count band: highly polysemous words (e.g., "drop" has 40+ senses,
    # "run" has 50+) create false synonym bridges with almost anything.
    # Conversely, very narrow-sense words (≤2 synsets, e.g., "project"/"task"
    # each with 2 senses sharing 1) hit the ratio threshold on a single
    # coincidental WordNet overlap that doesn't reflect real synonymy in the
    # writing's domain. Require 3-8 senses for meaningful drift detection.
    min_synsets = 3
    max_synsets = 8

    def _get_cached_synsets(lemma: str) -> set:
        if lemma not in synset_cache:
            try:
                syns = get_synsets(lemma) or set()
                if min_synsets <= len(syns) <= max_synsets:
                    synset_cache[lemma] = syns
                else:
                    synset_cache[lemma] = set()
            except Exception:
                synset_cache[lemma] = set()
        return synset_cache[lemma]

    # Compare unique lemmas across section pairs via synset overlap
    seen_pairs: set = set()
    section_indices = sorted(unique_by_section.keys())

    for i, idx_a in enumerate(section_indices):
        for idx_b in section_indices[i + 1:]:
            for lem_a in unique_by_section[idx_a]:
                syns_a = _get_cached_synsets(lem_a)
                if not syns_a:
                    continue
                for lem_b in unique_by_section[idx_b]:
                    if lem_a == lem_b:
                        continue
                    pair_key = tuple(sorted((lem_a, lem_b)))
                    if pair_key in seen_pairs:
                        continue
                    syns_b = _get_cached_synsets(lem_b)
                    if not syns_b:
                        continue
                    shared = syns_a & syns_b
                    if not shared:
                        continue
                    # Require that the shared synsets represent a
                    # meaningful fraction of at least one word's senses.
                    # If the overlap is only 1 synset out of 5+, it is
                    # likely a polysemy coincidence (e.g., "require" and
                    # "expect" share one sense but diverge in context).
                    ratio_a = len(shared) / len(syns_a)
                    ratio_b = len(shared) / len(syns_b)
                    if max(ratio_a, ratio_b) < 0.4:
                        continue
                    if True:
                        seen_pairs.add(pair_key)
                        # Report at the start of the later section
                        later_sec = sections[idx_b]
                        sec_start = later_sec.get("start", 0)
                        line = text[:sec_start].count("\n") + 1 if sec_start else 1
                        issues.append({
                            "path": path,
                            "line": line,
                            "message": (
                                f"Terminology drift: '{lem_a}' and '{lem_b}' "
                                f"appear to be synonyms used in different sections — "
                                f"consider standardizing on one term."
                            ),
                            "severity": severity,
                            "check": "Cohesion.TerminologyDrift",
                        })

    return issues
