# Technical corpus

Real-world technical documentation pulled from public GitHub repositories,
used as a precision/recall test bed for `rhetor-linter` and as labeled
data for the genre-classification corpus described in
`tests/fixtures/corpus/LABELING_GUIDE.md`.

Each `*.md` file has a sibling `*.label` file (single line: `technical`)
so the genre-validation tooling can pick them up.

**MyST/Sphinx scope note:** MyST-flavored fixtures (`myst-typography.md`,
`jupyterbook-create-content.md`, `click-commands.md`, `black-usage.md`,
`court-scraper-site-discovery.md`) have been dropped from this corpus.
MyST preprocessing in `engine.py` is unaffected — this is a decision to
stop maintaining validated/tested MyST fixtures here, not to remove
MyST support. See `history/` for the design note.

## How to run the linter against this corpus

```bash
.venv/bin/python -m rhetoric_lint.main lint \
  --format text tests/fixtures/corpus/technical/
```

Or per-file:

```bash
.venv/bin/python -m rhetoric_lint.main lint \
  --format text tests/fixtures/corpus/technical/fastapi-first-steps.md
```

## Sources

Each entry below records the upstream repository, the branch we fetched
from, the HEAD commit SHA at fetch time, and the upstream license. The
`view` link pins to the exact commit so the file can be re-retrieved
verbatim. Files are unmodified copies; preserve attribution if the
content is reproduced anywhere outside this test corpus.

Fetched: 2026-05-05.

| Local file | Upstream | Branch | Commit (at fetch) | License | Markup flavor |
|---|---|---|---|---|---|
| `fastapi-first-steps.md` | [fastapi/fastapi](https://github.com/fastapi/fastapi) `docs/en/docs/tutorial/first-steps.md` | `master` | [`622b6356`](https://github.com/fastapi/fastapi/blob/622b6356b510/docs/en/docs/tutorial/first-steps.md) | MIT | MkDocs Material (uses `///` block admonitions, `{ #anchor }` ids, custom `{* path *}` snippet hook) |
| `pydantic-models.md` | [pydantic/pydantic](https://github.com/pydantic/pydantic) `docs/concepts/models.md` | `main` | [`14e0f2ba`](https://github.com/pydantic/pydantic/blob/14e0f2ba41ea/docs/concepts/models.md) | MIT | MkDocs Material (uses `??? api` collapsible admonitions, `!!! note`) |
| `mkdocs-material-setup.md` | [squidfunk/mkdocs-material](https://github.com/squidfunk/mkdocs-material) `docs/setup/changing-the-colors.md` | `master` | [`8d01326c`](https://github.com/squidfunk/mkdocs-material/blob/8d01326cd2e8/docs/setup/changing-the-colors.md) | MIT | MkDocs Material (canonical `!!! note` / `!!! warning` admonitions, content tabs) |
| `k8s-pod-overview.md` | [kubernetes/website](https://github.com/kubernetes/website) `content/en/docs/concepts/workloads/pods/_index.md` | `main` | [`d597d023`](https://github.com/kubernetes/website/blob/d597d02347d8/content/en/docs/concepts/workloads/pods/_index.md) | CC-BY-4.0 (docs) | Hugo GFM with `{{< caution >}}` shortcodes (linter sees these as raw text — known gap) |
| `rust-book-installation.md` | [rust-lang/book](https://github.com/rust-lang/book) `src/ch01-01-installation.md` | `main` | [`05d11428`](https://github.com/rust-lang/book/blob/05d114287b7d/src/ch01-01-installation.md) | MIT or Apache-2.0 | mdBook GFM (plain) |

MyST/Sphinx-flavored fixtures previously listed here (`myst-typography.md`,
`jupyterbook-create-content.md`, `click-commands.md`, `black-usage.md`,
`court-scraper-site-discovery.md`) were dropped — see scope note above.

## Selection rationale

The set is deliberately diverse along three axes:

- **Markup flavor** — GFM, MkDocs Material, Hugo shortcodes — to
  stress-test the engine's flavor-handling preprocessors and surface any
  new syntactic footguns. (MyST/Sphinx fixtures were dropped — see scope
  note above.)
- **Diataxis quadrant** — tutorial (FastAPI first-steps), how-to
  (rust-book installation, mkdocs setup), reference (pydantic models,
  k8s pods) — to verify the genre-aware rules fire (or stay quiet)
  appropriately.
- **Repo size and convention** — large multi-author projects (k8s,
  fastapi, pydantic) versus smaller single-author docs (rust book
  chapter) — different prose styles surface different rule behaviors.

## Refreshing the corpus

The fetch URLs above are rendered as `raw.githubusercontent.com/<repo>/<branch>/<path>`
without commit pinning, so re-running the same `curl` will pick up the
*current* upstream content. To refresh:

```bash
DEST=tests/fixtures/corpus/technical
curl -fsSL -o "$DEST/fastapi-first-steps.md" \
  https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/tutorial/first-steps.md
# ...repeat for the other entries above.
```

After refreshing, update the commit-SHA column in this README. The
short SHAs above came from `gh api repos/<owner>/<name>/branches/<branch> --jq .commit.sha`.

## Known engine limitations exposed by this corpus

Documented gaps the linter does not yet handle. Filing as future work:

- **MkDocs `///`-style block admonitions** (FastAPI). Different from
  `!!! kind`. The current rewriter does not match them.
- **Pydantic-style `??? api "Title"` collapsible admonitions with
  embedded `<a>` HTML and Material content tabs**. Body parsing works;
  the tab markup leaks into prose tokens.
- **Hugo shortcodes** (`{{< caution >}}...{{< /caution >}}`). These pass
  through as literal text and inflate cohesion / structural metrics.
- **Custom MkDocs hooks** like FastAPI's `{* path *}` snippet inserts.
  Treated as plain text; not topic-bearing.

These are good candidates for the next round of preprocessing work
once a Docusaurus corpus and similar arrives.
