# MyST Corpus Fixtures: Dropped as Least Concern

**Date:** 2026-07-02
**Issue:** Commit `89af563` ("progress perhaps") deleted 5 precision-corpus fixtures alongside an unrelated SP_MDLINT_FULL landing, with no commit-message rationale and no doc updates.
**Context:** `tests/fixtures/corpus/technical/` originally seeded 10 real-world docs (commit `4edec21`) chosen for markup-flavor diversity, including several MyST/Sphinx examples. `89af563` removed `black-usage.md`, `click-commands.md`, `court-scraper-site-discovery.md`, `fastapi-first-steps.md`, and `myst-typography.md` (plus `.label` files) without updating `tests/fixtures/corpus/technical/README.md`, which still documented provenance and refresh commands for all five.

---

## Decision

- **MyST/Sphinx fixtures are intentionally dropped** from the precision corpus: `myst-typography.md`, `jupyterbook-create-content.md` (already removed earlier, in `9f45bec`), `click-commands.md`, `black-usage.md`, `court-scraper-site-discovery.md`. Validated/tested MyST coverage in the corpus is now **least concern** — we are not maintaining dedicated MyST fixtures going forward.
- **`engine.py`'s MyST preprocessing is unaffected.** This is a corpus-fixture scope decision, not a decision to drop MyST admonition/directive rewriting from the engine.
- **`fastapi-first-steps.md` was restored.** It is MkDocs Material, not MyST, and its deletion in `89af563` was not part of this decision — it was collateral damage from an undocumented bulk removal. Restored verbatim from `4edec21`.

## Why this matters for future sessions

- If a future MyST-specific false positive or crash is reported, do not expect a corpus fixture to catch it — there isn't one. Any MyST regression work should add its own targeted fixture rather than assuming corpus coverage exists.
- `tests/fixtures/corpus/technical/README.md`'s "Sources" table and "Selection rationale" section were rewritten to stop referencing the dropped MyST files as diversity examples.
- General lesson: `89af563` is an example of doc/plan/CHANGELOG drift within this project's own repo — a corpus README described files that no longer existed, the plan file still marked the landed SP_MDLINT_FULL work as backlog, and CHANGELOG had no entry for either the new rules or the fixture removal. All three were reconciled alongside this decision.
