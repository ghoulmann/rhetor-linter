"""Accuracy scaffold for the genre classifier.

This test suite is skipped until the labeled validation corpus is assembled
at tests/fixtures/corpus/.  Once documents are present, it measures per-genre
precision/recall/F1 and asserts the bars required before enabling
GENRE_GATE_ENABLED in const.py.

Corpus layout
-------------
tests/fixtures/corpus/<genre>/<filename>.md   — the document
tests/fixtures/corpus/<genre>/<filename>.label — single line: expected genre

Accuracy thresholds
-------------------
Macro-averaged F1 >= 0.80
Per-genre F1       >= 0.78 for every genre

These thresholds must be met (on a 20-per-genre held-out split) before
GENRE_GATE_ENABLED is set to True.
"""

import json
from pathlib import Path

import pytest

from rhetoric_lint.engine import RhetoricEngine

CORPUS_DIR = Path(__file__).parent / "fixtures" / "corpus"
KNOWN_GENRES = ("technical", "scientific", "academic", "curriculum", "legal", "general")

# ---------------------------------------------------------------------------
# Skip condition: corpus not yet assembled
# ---------------------------------------------------------------------------

def _corpus_documents():
    """Collect (md_path, expected_genre) tuples from the corpus directory."""
    docs = []
    for genre_dir in CORPUS_DIR.iterdir():
        if not genre_dir.is_dir() or genre_dir.name not in KNOWN_GENRES:
            continue
        for md_file in genre_dir.glob("*.md"):
            label_file = md_file.with_suffix(".label")
            if label_file.exists():
                expected = label_file.read_text(encoding="utf-8").strip()
                docs.append((str(md_file), expected))
    return docs


_CORPUS = _corpus_documents()
_CORPUS_ASSEMBLED = len(_CORPUS) >= len(KNOWN_GENRES) * 5  # at least 5 per genre


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_f1(tp, fp, fn):
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CORPUS_ASSEMBLED, reason="Labeled corpus not yet assembled — see tests/fixtures/corpus/LABELING_GUIDE.md")
def test_genre_classifier_accuracy():
    """Classify every labeled document and assert accuracy thresholds."""
    eng = RhetoricEngine()

    # Tally per-genre TP/FP/FN
    stats = {g: {"tp": 0, "fp": 0, "fn": 0} for g in KNOWN_GENRES}
    misclassified = []

    for md_path, expected in _CORPUS:
        try:
            text = Path(md_path).read_text(encoding="utf-8")
            issues = eng.lint_files([md_path])
            predicted = eng.last_genres.get(md_path, "general")
        except Exception as exc:
            pytest.fail(f"Engine failed on {md_path}: {exc}")

        if predicted == expected:
            stats[expected]["tp"] += 1
        else:
            stats[expected]["fn"] += 1
            if predicted in stats:
                stats[predicted]["fp"] += 1
            misclassified.append(
                {"path": md_path, "expected": expected, "predicted": predicted}
            )

    # Per-genre F1
    per_genre_f1 = {}
    for g in KNOWN_GENRES:
        s = stats[g]
        per_genre_f1[g] = _compute_f1(s["tp"], s["fp"], s["fn"])

    macro_f1 = sum(per_genre_f1.values()) / len(per_genre_f1)

    # Report
    print("\n=== Genre classifier accuracy ===")
    for g, f1 in per_genre_f1.items():
        s = stats[g]
        print(f"  {g:12s}  F1={f1:.3f}  TP={s['tp']} FP={s['fp']} FN={s['fn']}")
    print(f"  {'macro':12s}  F1={macro_f1:.3f}")
    if misclassified:
        print(f"\n  Misclassified ({len(misclassified)}):")
        for m in misclassified[:20]:
            print(f"    {m['path']}  expected={m['expected']}  got={m['predicted']}")

    # Assertions
    assert macro_f1 >= 0.80, (
        f"Macro F1 {macro_f1:.3f} < 0.80 — classifier not ready for gate enablement"
    )
    for g, f1 in per_genre_f1.items():
        assert f1 >= 0.78, (
            f"Per-genre F1 for '{g}' is {f1:.3f} < 0.78"
        )
