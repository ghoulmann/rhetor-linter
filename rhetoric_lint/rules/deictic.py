from typing import Any, Dict, List

from rhetoric_lint.overlap import channelize_tokens

GENRES = frozenset({"all"})

_DEICTIC = {"this", "that", "these", "those"}


def _content_lemmas(span, pronouns: set) -> set:
    return channelize_tokens(span, pronouns).get("content", set())


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Cohesion.DeicticGhost — flag demonstrative pronouns with no antecedent.

    A sentence that opens with a standalone 'this', 'that', 'these', or 'those'
    (used as a pronoun, not a determiner) but shares no content words with the
    preceding 1–2 sentences is likely a deictic ghost: the referent is absent
    or in a different chunk, which breaks RAG retrieval autonomy.
    """
    issues = []
    path = context.get("path", "")
    text = context.get("text", "")
    sections = context.get("sections", [])
    const = context.get("const")

    pronouns = set(getattr(const, "PRONOUNS", [])) if const else set()
    severity = (
        getattr(const, "RULE_SEVERITY_LEVELS", {}).get("Cohesion.DeicticGhost", "warning")
        if const else "warning"
    )

    for sec in sections:
        # Sliding window: content-lemma sets from last 2 sentences, reset per section
        prev_content: List[set] = []

        for para in sec.get("paragraphs", []):
            for srec in (para.get("sentences") or []):
                span = srec.get("span")
                if span is None:
                    continue

                sent_start = srec.get("start", 0)
                line = text[:sent_start].count("\n") + 1

                # Scan first 5 tokens for a standalone deictic pronoun
                deictic_found = False
                for i, tok in enumerate(span):
                    if i >= 5:
                        break
                    if tok.text.lower() not in _DEICTIC:
                        continue

                    pos_ = getattr(tok, "pos_", "")
                    dep_ = getattr(tok, "dep_", "")

                    # Standalone pronoun: POS is PRON or dependency is subject/root
                    if pos_ == "PRON" or dep_ in ("nsubj", "ROOT", "attr", "nsubjpass"):
                        deictic_found = True
                        break

                    # Fallback for blank spaCy model (no POS tags): flag at position 0 only
                    if not pos_ and i == 0:
                        deictic_found = True
                        break

                cur_content = _content_lemmas(span, pronouns)

                if deictic_found and prev_content:
                    prior: set = set()
                    for prev in prev_content:
                        prior |= prev
                    if not (prior & cur_content):
                        issues.append({
                            "path": path,
                            "line": line,
                            "column": 1,
                            "message": (
                                "Deictic pronoun with no antecedent: "
                                "no shared content words found in the preceding sentence(s)."
                            ),
                            "severity": severity,
                            "check": "Cohesion.DeicticGhost",
                        })

                # Update sliding window (keep last 2)
                prev_content.append(cur_content)
                if len(prev_content) > 2:
                    prev_content.pop(0)

    return issues
