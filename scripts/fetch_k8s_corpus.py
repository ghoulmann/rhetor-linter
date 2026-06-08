#!/usr/bin/env python3
"""Fetch a stratified sample of Kubernetes docs as a Diátaxis-labeled corpus.

Sparse-checks out the kubernetes/website repo, strips Hugo shortcodes, and
writes sampled files to a staging directory alongside .label and .topic_type
files.  Files are suitable for:
  - Precision corpus (tests/fixtures/corpus/technical/) — genre label "technical"
  - topic_type classifier validation                    — topic_type label per folder

Usage
-----
  python scripts/fetch_k8s_corpus.py [--dest DIR] [--per-category N] [--seed INT]

  --dest           Output directory  (default: tests/fixtures/corpus/technical/)
  --per-category   Files to sample per Diataxis category  (default: 10)
  --seed           Random seed for reproducible sampling  (default: 42)
  --no-topic-label Skip writing .topic_type label files

The script requires git to be on PATH.  It clones into a temp directory and
removes it when done (pass --keep-workspace to inspect the raw checkout).
"""

import argparse
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Diátaxis category → (k8s folder, topic_type label)
# ---------------------------------------------------------------------------
CATEGORIES = {
    "tutorials": "tutorial",
    "tasks":     "howto",
    "concepts":  "concept",
    "reference": "reference",
}

REPO_URL = "https://github.com/kubernetes/website.git"
DOCS_ROOT = "content/en/docs"

# ---------------------------------------------------------------------------
# Hugo shortcode stripping
# ---------------------------------------------------------------------------

# Block shortcodes: {{< name ... >}} ... {{< /name >}}
# Also handles {{% name %}} ... {{% /name %}} (markdown-rendered variant)
_BLOCK_NOTE_RE = re.compile(
    r'\{\{[<%]\s*(note|warning|caution|tip)\s*[%>]\}\}'
    r'(.*?)'
    r'\{\{[<%]\s*/(?:note|warning|caution|tip)\s*[%>]\}\}',
    re.DOTALL | re.IGNORECASE,
)

_BLOCK_TABS_RE = re.compile(
    r'\{\{[<%]\s*tabs\s*[^}]*[%>]\}\}(.*?)\{\{[<%]\s*/tabs\s*[%>]\}\}',
    re.DOTALL,
)

_BLOCK_TAB_WRAPPER_RE = re.compile(
    r'\{\{[<%]\s*tab\s+name="[^"]*"\s*[%>]\}\}(.*?)\{\{[<%]\s*/tab\s*[%>]\}\}',
    re.DOTALL,
)

# Self-closing / inline shortcodes — remove entirely
_INLINE_SC_RE = re.compile(r'\{\{[<%][^}]+[%>]\}\}')

# Hugo front matter (--- ... ---) — engine strips this already, but strip here
# too so line counts are clean
_FRONTMATTER_RE = re.compile(r'\A---\n.*?\n---\n?', re.DOTALL)


def _label_for_admonition(name: str) -> str:
    return {"note": "Note", "warning": "Warning", "caution": "Caution", "tip": "Tip"}.get(
        name.lower(), name.capitalize()
    )


def _block_note_sub(m: re.Match) -> str:
    label = _label_for_admonition(m.group(1))
    body = m.group(2).strip()
    lines = body.splitlines()
    quoted = "\n".join(f"> {line}" if line.strip() else ">" for line in lines)
    return f"> **{label}:** {quoted}\n"


def strip_shortcodes(text: str) -> str:
    """Remove or convert Hugo shortcodes to plain Markdown."""
    text = _FRONTMATTER_RE.sub("", text)
    text = _BLOCK_NOTE_RE.sub(_block_note_sub, text)
    # tabs: keep inner content of all tab children, drop wrappers
    def _expand_tabs(m: re.Match) -> str:
        inner = m.group(1)
        return _BLOCK_TAB_WRAPPER_RE.sub(lambda tm: tm.group(1), inner)
    text = _BLOCK_TABS_RE.sub(_expand_tabs, text)
    text = _INLINE_SC_RE.sub("", text)
    # Collapse runs of 3+ blank lines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + "\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(args: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed: {' '.join(args)}")


def sparse_checkout(workspace: Path) -> Path:
    """Clone kubernetes/website with sparse checkout into workspace/repo."""
    repo = workspace / "repo"
    print("Initialising sparse checkout (this may take a minute)…")
    run(["git", "clone", "--filter=blob:none", "--no-checkout", "--depth=1",
         REPO_URL, str(repo)])
    run(["git", "sparse-checkout", "init", "--cone"], cwd=repo)
    paths = [f"{DOCS_ROOT}/{cat}" for cat in CATEGORIES]
    run(["git", "sparse-checkout", "set"] + paths, cwd=repo)
    run(["git", "checkout"], cwd=repo)
    print("Checkout complete.")
    return repo


def collect_files(repo: Path) -> dict[str, list[Path]]:
    """Return {category: [.md paths]} for each Diátaxis category."""
    out: dict[str, list[Path]] = {}
    for cat in CATEGORIES:
        folder = repo / DOCS_ROOT / cat
        if not folder.exists():
            print(f"  Warning: {folder} not found — skipping", file=sys.stderr)
            out[cat] = []
            continue
        files = sorted(folder.rglob("*.md"))
        # Skip index / _index.md files (nav boilerplate, not content)
        files = [f for f in files if f.stem not in ("_index", "index")]
        out[cat] = files
    return out


def sample_and_write(
    files_by_cat: dict[str, list[Path]],
    dest: Path,
    per_category: int,
    seed: int,
    write_topic_label: bool,
) -> int:
    rng = random.Random(seed)
    dest.mkdir(parents=True, exist_ok=True)
    written = 0

    for cat, files in files_by_cat.items():
        topic_type = CATEGORIES[cat]
        sample = rng.sample(files, min(per_category, len(files)))
        print(f"  {cat:12s}  {len(sample):2d} files  (topic_type={topic_type})")

        for src in sample:
            raw = src.read_text(encoding="utf-8", errors="replace")
            cleaned = strip_shortcodes(raw)

            # Skip files that are nearly empty after stripping
            if len(cleaned.split()) < 30:
                continue

            stem = f"k8s-{cat}-{src.stem}"
            (dest / f"{stem}.md").write_text(cleaned, encoding="utf-8")
            (dest / f"{stem}.label").write_text("technical\n", encoding="utf-8")
            if write_topic_label:
                (dest / f"{stem}.topic_type").write_text(f"{topic_type}\n", encoding="utf-8")
            written += 1

    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dest", default="tests/fixtures/corpus/technical/",
                        help="Output directory")
    parser.add_argument("--per-category", type=int, default=10, metavar="N",
                        help="Files to sample per Diataxis category (default 10)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default 42)")
    parser.add_argument("--no-topic-label", action="store_true",
                        help="Skip writing .topic_type label files")
    parser.add_argument("--keep-workspace", action="store_true",
                        help="Do not delete the git checkout after running")
    args = parser.parse_args()

    dest = Path(args.dest)
    workspace = Path(tempfile.mkdtemp(prefix="k8s-corpus-"))

    try:
        repo = sparse_checkout(workspace)
        files_by_cat = collect_files(repo)
        total_available = sum(len(v) for v in files_by_cat.values())
        print(f"Found {total_available} candidate files across {len(CATEGORIES)} categories.")
        written = sample_and_write(
            files_by_cat, dest,
            per_category=args.per_category,
            seed=args.seed,
            write_topic_label=not args.no_topic_label,
        )
        print(f"\nWrote {written} files to {dest}")
    finally:
        if args.keep_workspace:
            print(f"Workspace preserved at {workspace}")
        else:
            shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    main()
