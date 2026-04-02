from typing import Any, Dict, List

from rhetoric_lint.overlap import channelize_tokens, section_coherence_metrics

GENRES = frozenset({"all"})


def _line_from_pos(text: str, pos: int) -> int:
    return text[:pos].count("\n") + 1


def _alpha_token_count(span) -> int:
    return sum(1 for t in span if getattr(t, "is_alpha", False))


def _first_substantial_sentence(section: Dict[str, Any]):
    for para in section.get("paragraphs", []):
        for srec in para.get("sentences", []):
            span = srec.get("span")
            if span is None:
                continue
            if _alpha_token_count(span) >= 6:
                return srec
    return None


def _remaining_substantial_sentences(section: Dict[str, Any], skip_start: int):
    out = []
    for para in section.get("paragraphs", []):
        for srec in para.get("sentences", []):
            span = srec.get("span")
            if span is None:
                continue
            if int(srec.get("start", -1)) <= skip_start:
                continue
            if _alpha_token_count(span) >= 3:
                out.append(srec)
    return out


def check(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Section-level unity via heading/topic and topic/body coherence."""
    path = context.get("path")
    text = context.get("text", "")
    doc = context.get("doc")
    nlp = context.get("nlp")
    const = context.get("const")
    sections = context.get("sections", [])
    issues: List[Dict[str, Any]] = []

    if not doc:
        return []

    pronouns = set(getattr(const, "PRONOUNS", [])) if const else set()

    min_heading_topic = (
        float(getattr(const, "UNITY_MIN_HEADING_TOPIC_CONTENT_OVERLAP", 0.2))
        if const
        else 0.2
    )
    min_topic_section = (
        float(getattr(const, "UNITY_MIN_TOPIC_SECTION_CONTENT_OVERLAP", 0.15))
        if const
        else 0.15
    )

    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        if not heading or nlp is None:
            continue

        # H1 sections have no reliable topic sentence (often just a subtitle/byline)
        if sec.get("level", 0) == 1:
            continue

        topic = _first_substantial_sentence(sec)
        if not topic:
            continue

        try:
            heading_doc = nlp(heading)
        except Exception:
            continue

        heading_channels = channelize_tokens(heading_doc, pronouns)
        topic_span = topic.get("span")
        topic_channels = channelize_tokens(topic_span, pronouns)

        body_sentences = _remaining_substantial_sentences(
            sec,
            int(topic.get("start", -1)),
        )
        body_channels = [channelize_tokens(s.get("span"), pronouns) for s in body_sentences]

        metrics = section_coherence_metrics(
            heading_channels=heading_channels,
            topic_channels=topic_channels,
            body_channels=body_channels,
            channels=("content", "nouns", "argument"),
        )

        heading_topic_content = metrics["heading_topic"]["content"]["containment_left"]
        topic_section_content = metrics["topic_section"]["content"]["containment_left"]

        sec_line = _line_from_pos(text, int(sec.get("start", 0)))

        if heading_topic_content < min_heading_topic:
            # Stem bridge fallback: when overlap is zero, check 6-char morphological
            # prefix intersection (handles require/requirement, install/installation, etc.)
            stem_bridge = False
            if heading_topic_content == 0.0:
                h_stems = {l[:6] for l in heading_channels["content"] if len(l) >= 5}
                t_stems = {l[:6] for l in topic_channels["content"] if len(l) >= 5}
                stem_bridge = bool(h_stems & t_stems)
            if not stem_bridge:
                issues.append(
                    {
                        "path": path,
                        "line": sec_line,
                        "message": (
                            f"Section heading and topic sentence are weakly aligned "
                            f"(content overlap {heading_topic_content:.2f})"
                        ),
                        "severity": (
                            const.RULE_SEVERITY_LEVELS.get("Unity.HeadingTopicCoherence", "warning")
                            if const
                            else "warning"
                        ),
                        "check": "Unity.HeadingTopicCoherence",
                    }
                )

        if body_channels and topic_section_content < min_topic_section:
            topic_line = _line_from_pos(text, int(topic.get("start", sec.get("start", 0))))
            issues.append(
                {
                    "path": path,
                    "line": topic_line,
                    "message": (
                        f"Section topic sentence drifts from later content "
                        f"(content overlap {topic_section_content:.2f})"
                    ),
                    "severity": (
                        const.RULE_SEVERITY_LEVELS.get("Unity.TopicSectionDrift", "suggestion")
                        if const
                        else "suggestion"
                    ),
                    "check": "Unity.TopicSectionDrift",
                }
            )

    # Temporary fallback while heading/topic thresholds are tuned.
    use_noun_density_fallback = bool(
        getattr(const, "UNITY_ENABLE_NOUN_DENSITY_FALLBACK", False)
    )
    if use_noun_density_fallback:
        noun_count = sum(1 for t in doc if t.pos_ in ("NOUN", "PROPN"))
        token_count = max(1, len(doc))
        ratio = noun_count / token_count

        if ratio < float(getattr(const, "UNITY_MIN_NOUN_RATIO", 0.05)):
            issues.append(
                {
                    "path": path,
                    "line": 1,
                    "message": f"Low noun density ({ratio:.2f}) - document may lack a clear topic",
                    "severity": "suggestion",
                    "check": "unity.noun_density",
                }
            )

    return issues
