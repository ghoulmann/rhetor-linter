# API Interface: Minimal Scope, Hosting, and Auth Deferral

**Date:** 2026-07-16
**Issue:** Should rhetor-linter expose an HTTP API alongside the CLI, and if so — what shape, where hosted, and does it need accounts/API keys from day one?

**Context:** A CI failure investigation (`pip install rhetoric-lint` — package never published to PyPI) surfaced that the linter has no distribution path for external adopters. Separately, a hosting-suite exploration (Netlify vs. Render vs. Fly.io vs. Railway vs. Cloudflare Workers, for the already-planned enterprise server in `plan-enterprise-platform.md`) settled on Render. This session extended that into: could a *minimal* version of the same API exist now, ahead of the full enterprise platform (auth, scheduler, dashboard, Backstage)?

---

## Decisions

1. **Build the minimal API now, as an early slice of the existing plan — not a new direction.** `score.py::score_file()` is already designed as the linter/server boundary (`plan-enterprise-platform.md`). A thin wrapper exposing `POST /lint` and `POST /score` needs no auth, database, or scheduler — `RhetoricEngine.lint_files()` only accepts file paths (not raw text), so the one adapter piece is writing the POST body to a temp file before calling it.

2. **Host on Render free tier** — the same target already chosen for the eventual full enterprise server (see `plan-enterprise-platform.md:87`). This makes the minimal API step one of that same deployment rather than a separate service to maintain. Netlify and Cloudflare Workers were both ruled out for this: Netlify's free-tier function timeout (10s) is a real risk against spaCy pipeline cold-start, and Cloudflare Workers' Python runtime (Pyodide/WASM) cannot run spaCy at all (it's a compiled C-extension package, not in Pyodide's package index). spaCy's `en_core_web_sm` model was confirmed small (15MB installed) — no package-size barrier to Render.

3. **Add a paste/drag/upload playground UI, served as static files from the same Render app** (not a separate Netlify/GitHub Pages deploy). Paste, drag-and-drop, and file upload all reduce to the same client-side flow (get text into the browser → `fetch()` to `/lint`) — no extra backend surface. Same-origin hosting avoids needing CORS. A separately-hosted static playground (Netlify/GH Pages would genuinely fit well for *this* piece specifically, unlike the stateful server) remains an option later if a separate branded URL is wanted, but isn't the default.

4. **No accounts or API keys for this minimal layer.** Requiring signup before someone can paste markdown and see results directly undercuts the "try before you install" purpose this was built for. It would also reintroduce real scope (user storage, auth flow, key issuance) that the minimal API was specifically designed to avoid, and risks building a *second* auth system alongside the one already planned for the full server (GitHub OAuth via `authlib`, scoped for a genuinely different use case — dashboard, repo polling, per-org settings — not an anonymous paste box).

5. **Abuse protection is a body-size cap + IP-based rate limit, deferred as a fast-follow** — not blocking the initial deploy. No accounts needed for this; it's a guard against scripted abuse of free-tier compute, not a user-management feature.

## Why this matters for future sessions

- This is explicitly **not** the full enterprise platform (Phases 1-5 in `plan-enterprise-platform.md`: auth, scheduler, SQLite store, dashboard, Backstage). It's a stateless subset that should compose into that plan later, not be rebuilt when the full platform lands — the FastAPI app and Render deployment target are meant to be reused, not replaced.
- If real auth is eventually needed for this API (traffic-driven, or once the full server's GitHub OAuth exists), reuse that system rather than retrofitting a separate API-key mechanism here.
- The rate limit is tracked as a known fast-follow, not an oversight — do not treat its absence as a bug if picked up by a future session; it was a deliberate sequencing choice.
- This work has not yet been added as a numbered SP in the master plan or scoped into concrete files/tests — it is a design decision, not an implementation plan. See the new backlog row in `plan-support-for-markdownlint-joyful-teacup.md` for tracking.
