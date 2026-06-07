"""Accuracy scaffold for the genre classifier.

This test suite is skipped until the labeled validation corpus is assembled.
Once documents are present, it measures per-genre precision/recall/F1 and
asserts the bars required before enabling GENRE_GATE_ENABLED in const.py.

Corpus layout
-------------
tests/fixtures/corpus/<any-dir>/<filename>.md    — the document
tests/fixtures/corpus/<any-dir>/<filename>.label — single line: expected genre

The directory name is not the label; the .label file content is.
This allows the precision corpus (corpus/technical/) to hold documents of
mixed genres without renaming the directory.

Accuracy thresholds
-------------------
Macro-averaged F1 >= 0.80
Per-genre F1       >= 0.78 for every genre with ≥ 1 labeled document

These thresholds must be met (on a 20-per-genre held-out split) before
GENRE_GATE_ENABLED is set to True.
"""

from pathlib import Path

import pytest

from rhetoric_lint.engine import RhetoricEngine

CORPUS_DIR = Path(__file__).parent / "fixtures" / "corpus"

KNOWN_GENRES = (
    "howto", "tutorial", "concept", "reference",
    "adr", "postmortem", "changelog", "readme", "general",
)

_MIN_LABELED = 10  # skip if corpus is too thin to be meaningful


# ---------------------------------------------------------------------------
# Corpus collection — scan all subdirs, use .label file content
# ---------------------------------------------------------------------------

def _corpus_documents():
    """Collect (md_path, expected_genre) tuples from all corpus subdirs."""
    docs = []
    for sub in CORPUS_DIR.rglob("*.label"):
        md_file = sub.with_suffix(".md")
        if not md_file.exists():
            continue
        expected = sub.read_text(encoding="utf-8").strip()
        if expected in KNOWN_GENRES:
            docs.append((str(md_file), expected))
    return docs


_CORPUS = _corpus_documents()
_CORPUS_ASSEMBLED = len(_CORPUS) >= _MIN_LABELED


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

@pytest.mark.skipif(
    not _CORPUS_ASSEMBLED,
    reason=f"Labeled corpus too small ({len(_CORPUS)} docs, need {_MIN_LABELED})",
)
def test_genre_classifier_accuracy():
    """Classify every labeled document and report accuracy metrics.

    Thresholds (macro F1 >= 0.80, per-genre >= 0.78) are only enforced when
    const.GENRE_GATE_ENABLED is True.  Until then the test always passes but
    prints a diagnostic report — useful as a development dashboard without
    blocking CI while the classifier is being tuned.
    """
    from rhetoric_lint import const as _const
    enforce = getattr(_const, "GENRE_GATE_ENABLED", False)

    eng = RhetoricEngine()
    stats = {g: {"tp": 0, "fp": 0, "fn": 0} for g in KNOWN_GENRES}
    misclassified = []

    for md_path, expected in _CORPUS:
        try:
            eng.lint_files([md_path])
            predicted = eng.last_genres.get(md_path, "general")
        except Exception as exc:
            pytest.fail(f"Engine failed on {md_path}: {exc}")

        if predicted == expected:
            stats[expected]["tp"] += 1
        else:
            stats[expected]["fn"] += 1
            if predicted in stats:
                stats[predicted]["fp"] += 1
            misclassified.append({"path": md_path, "expected": expected, "predicted": predicted})

    active_genres = [g for g in KNOWN_GENRES if (stats[g]["tp"] + stats[g]["fn"]) > 0]
    per_genre_f1 = {g: _compute_f1(stats[g]["tp"], stats[g]["fp"], stats[g]["fn"]) for g in active_genres}
    macro_f1 = sum(per_genre_f1.values()) / max(len(per_genre_f1), 1)

    print("\n=== Genre classifier accuracy ===")
    for g, f1 in per_genre_f1.items():
        s = stats[g]
        print(f"  {g:12s}  F1={f1:.3f}  TP={s['tp']} FP={s['fp']} FN={s['fn']}")
    print(f"  {'macro':12s}  F1={macro_f1:.3f}")
    if misclassified:
        print(f"\n  Misclassified ({len(misclassified)}):")
        for m in misclassified[:20]:
            print(f"    {m['path']}  expected={m['expected']}  got={m['predicted']}")
    if not enforce:
        print("\n  (Thresholds not enforced — set GENRE_GATE_ENABLED=True to enable assertions)")
        return

    assert macro_f1 >= 0.80, f"Macro F1 {macro_f1:.3f} < 0.80"
    for g, f1 in per_genre_f1.items():
        assert f1 >= 0.78, f"Per-genre F1 for '{g}' is {f1:.3f} < 0.78"
