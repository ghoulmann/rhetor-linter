# Fence Detection: Regression Tests and Future Impact

**Date:** 2026-06-13  
**Issue:** Replacing `_code_fence_lines` regex scanner with mistletoe AST-based implementation  
**Context:** SP_MDLINT_FULL — the current `_FENCE_START_RE = r"^(`{3,}|~{3,})"` anchors to column 0, missing fences inside list items, blockquotes, and 4+ backtick fences. Mistletoe AST gives correct `line_number` on `CodeFence` nodes for all cases.

---

## Regression Tests Required

`_code_fence_lines` is the shared foundation — every rule calls `if i in fence_set: continue`. Changing it is a cross-cutting change touching all 53 rules.

### New test class needed: `TestCodeFenceLines`

| Test | What it guards |
|------|---------------|
| Basic col-0 ` ``` ` and `~~~` fence | Existing behavior preserved |
| 2-space indented fence (single list item) | The fix being introduced |
| 4-space indented fence (nested list) | The fix being introduced |
| 4-backtick fence containing 3-backtick content | Extended fence nesting |
| Fence inside `> blockquote` | The fix being introduced |
| Unclosed fence (EOF) | Mistletoe graceful parse; fallback to regex fires |
| Multiple consecutive fences | No state bleed between fences |
| Rule silent inside each case | Integration: MD009 doesn't fire on trailing space inside an indented fence; MD037 doesn't fire on `* text *` inside a blockquote fence |

### Existing tests at risk

All ~90 "no-fire-in-code-block" tests depend on `fence_set` being correct. They all use col-0 fences — the new implementation must produce identical sets for those inputs. Risk: a synthetic test input that is not valid CommonMark could parse differently under mistletoe than under the regex (e.g., a test that uses an unclosed fence as a deliberate fixture).

### One non-obvious regression: MD046

MD046 detects 4-space indented code blocks. Mistletoe represents those as `BlockCode` nodes (not `CodeFence`). The new implementation must include **only** `CodeFence` nodes in `fence_set`, not `BlockCode`. If `BlockCode` lines were added to `fence_set`, MD046's target lines would be pre-filtered and it would never fire. Current regex behavior already excludes indented blocks (it only matches backtick/tilde), so this preserves current behavior — but it must be explicit in the implementation and tested.

---

## Effects on Future Planned Changes

| Item | Effect |
|------|--------|
| SP10/SP11 (DependencyReveal, ConceptReintroduction) | None — NLP rules in `rules/*.py`, not the markdownlint runner |
| CrossFileContext | None — different subsystem entirely |
| Enterprise scoring (score.py, server/) | None — scoring calls `score_file()` which calls the engine; markdownlint runner is a downstream leaf |
| Future markdownlint rules | **Positive** — any rule added later gets correct fence detection for free, including in list/blockquote contexts |
| Vale runner | None — separate runner, its own text preprocessing |

### Structural implication

`_code_fence_lines` is called before any rule functions, so the same `fence_set` is shared across all rules in a single `check()` call. After the change, the same is true — one mistletoe parse, one set, shared. But the markdownlint runner receives the **preprocessed** text from `engine.py` (HTML comments blanked, MyST admonitions converted), while the engine also runs its own mistletoe parse on the same preprocessed text. This means parsing the same text twice with mistletoe. Benign for correctness; future optimization path is for the engine to pass the already-parsed mistletoe `Document` in `context` so `_code_fence_lines` reads fence positions from it rather than re-parsing.

---

## Agent Research Summary (4 agents, 2026-06-13)

- **Agent 1 (markdownlint-cli2):** The JS reference implementation has the identical `^` anchor limitation and accepts it as a known gap for the 80% case.
- **Agent 2 (Python parser APIs):** Recommended `markdown-it-py` (new dependency). Underestimated mistletoe — direct testing showed mistletoe `CodeFence` nodes carry correct `line_number`.
- **Agent 3 (CommonMark spec):** Definitive — a regex state machine cannot be correct for nested list/blockquote contexts. Full parser required for correctness.
- **Agent 4 (pymarkdown/mdformat):** Blocked on tool permissions. No output.

**Resolution:** Use mistletoe AST (already a required dependency). `CodeFence.line_number` gives the opener; end line = `line_number + content.count('\n') + 1`. Regex scanner becomes graceful fallback on parse error.
