# rhetoric_lint/server — CLAUDE.md

## Import constraint (hard rule)

Never import from `engine.py`, `rules/`, or `runners/`.

The only public surface of the linter this package may use is:

```python
from rhetoric_lint.score import score_file, ScoreResult
```

Everything else — RhetoricEngine, spaCy, rule modules, Vale runner — is off-limits.
This constraint exists so the server sub-package can graduate to a standalone repo
without surgery on import graphs.

## Graduation condition

Extract `rhetoric_lint/server/` to a standalone `shela-server` repo when any of:
- The server needs a different deploy cadence or version than the linter
- A second analysis backend is added
- A dedicated contributor works server-only

Until then, the server lives here as an `[server]` extras group in pyproject.toml.

## What goes here

- FastAPI app and route handlers
- Auth, rate limiting, persistence
- Pydantic request/response models (distinct from linter models in score.py)
- Background task wiring

## What does NOT go here

- Any rule logic
- Any runner logic
- Any spaCy model access
- The `score_file()` implementation (that stays in `score.py`)
