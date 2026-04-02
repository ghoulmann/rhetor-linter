from typing import Dict, Iterable, List, Mapping, Optional, Set


def _as_segment_set(tokens: Iterable[str]) -> Set[str]:
    return {t for t in tokens if t}


def _token_lemma(token) -> str:
    text = getattr(token, "text", "")
    lemma = (getattr(token, "lemma_", "") or text or "").lower().strip()
    if not lemma:
        return ""
    return lemma


def channelize_tokens(tokens: Iterable, pronouns: Optional[Set[str]] = None) -> Dict[str, Set[str]]:
    """Build overlap channels from a token stream.

    Channels:
    - content: non-stop alpha lemmas
    - nouns: noun/proper-noun lemmas
    - pronouns: pronoun lemmas (lexicon or POS-based)
    - argument: nouns union pronouns
    """
    pronouns = pronouns or set()
    content: Set[str] = set()
    nouns: Set[str] = set()
    pron: Set[str] = set()

    for tok in tokens:
        if not getattr(tok, "is_alpha", False):
            continue
        lemma = _token_lemma(tok)
        if not lemma:
            continue

        surface = getattr(tok, "text", "").lower().strip()
        if not getattr(tok, "is_stop", False):
            content.add(lemma)
            if surface and surface != lemma:
                content.add(surface)
        if getattr(tok, "pos_", "") in ("NOUN", "PROPN"):
            nouns.add(lemma)
            if surface and surface != lemma:
                nouns.add(surface)
        if lemma in pronouns or getattr(tok, "pos_", "") == "PRON":
            pron.add(lemma)

    return {
        "content": content,
        "nouns": nouns,
        "pronouns": pron,
        "argument": nouns | pron,
    }


def set_overlap_metrics(left: Iterable[str], right: Iterable[str]) -> Dict[str, float]:
    """Compute overlap and normalized set similarity metrics."""
    left_set = _as_segment_set(left)
    right_set = _as_segment_set(right)

    overlap = len(left_set & right_set)
    left_size = len(left_set)
    right_size = len(right_set)
    union_size = len(left_set | right_set)

    return {
        "overlap_count": float(overlap),
        "left_size": float(left_size),
        "right_size": float(right_size),
        "containment_left": float(overlap / left_size) if left_size else 0.0,
        "containment_right": float(overlap / right_size) if right_size else 0.0,
        "jaccard": float(overlap / union_size) if union_size else 0.0,
    }


def channel_overlap_metrics(
    left_channels: Mapping[str, Set[str]],
    right_channels: Mapping[str, Set[str]],
    channels: Optional[Iterable[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """Compute overlap metrics per named channel."""
    out: Dict[str, Dict[str, float]] = {}
    target_channels = channels or ("content", "nouns", "pronouns", "argument")
    for name in target_channels:
        out[name] = set_overlap_metrics(left_channels.get(name, set()), right_channels.get(name, set()))
    return out


def section_coherence_metrics(
    heading_channels: Mapping[str, Set[str]],
    topic_channels: Mapping[str, Set[str]],
    body_channels: Optional[List[Mapping[str, Set[str]]]] = None,
    channels: Optional[Iterable[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """Compute heading/topic and topic/body coherence metrics by channel."""
    body_channels = body_channels or []
    target_channels = tuple(channels or ("content", "nouns", "argument"))

    heading_topic = channel_overlap_metrics(
        heading_channels,
        topic_channels,
        channels=target_channels,
    )

    topic_section: Dict[str, Dict[str, float]] = {}
    for ch in target_channels:
        body_union: Set[str] = set()
        for record in body_channels:
            body_union |= set(record.get(ch, set()))
        topic_section[ch] = set_overlap_metrics(topic_channels.get(ch, set()), body_union)

    return {
        "heading_topic": heading_topic,
        "topic_section": topic_section,
    }


def token_channel_counts(tokens: Iterable, pronouns: Optional[Set[str]] = None) -> Dict[str, float]:
    """Count alpha/pronoun/noun tokens for givenness-style metrics."""
    pronouns = pronouns or set()
    alpha_tokens = 0
    pronoun_tokens = 0
    noun_tokens = 0

    for tok in tokens:
        if not getattr(tok, "is_alpha", False):
            continue
        alpha_tokens += 1
        lemma = _token_lemma(tok)
        if lemma and (lemma in pronouns or getattr(tok, "pos_", "") == "PRON"):
            pronoun_tokens += 1
        if getattr(tok, "pos_", "") in ("NOUN", "PROPN"):
            noun_tokens += 1

    return {
        "alpha_tokens": float(alpha_tokens),
        "pronoun_tokens": float(pronoun_tokens),
        "noun_tokens": float(noun_tokens),
    }


def sentence_pair_givenness_metrics(
    prev_channels: Mapping[str, Set[str]],
    cur_channels: Mapping[str, Set[str]],
    cur_counts: Mapping[str, float],
) -> Dict[str, float]:
    """Compute sentence-pair givenness metrics for discourse continuity checks."""
    alpha_tokens = float(cur_counts.get("alpha_tokens", 0.0))
    pronoun_tokens = float(cur_counts.get("pronoun_tokens", 0.0))
    noun_tokens = float(cur_counts.get("noun_tokens", 0.0))

    prev_content = set(prev_channels.get("content", set()))
    cur_content = set(cur_channels.get("content", set()))
    repeated_content = len(prev_content & cur_content)
    cur_content_size = len(cur_content)

    pronoun_density = (pronoun_tokens / alpha_tokens) if alpha_tokens else 0.0
    pronoun_noun_ratio = (
        pronoun_tokens / noun_tokens
        if noun_tokens
        else (pronoun_tokens if pronoun_tokens else 0.0)
    )
    repeated_content_ratio = (
        repeated_content / cur_content_size if cur_content_size else 0.0
    )

    return {
        "pronoun_density": float(pronoun_density),
        "pronoun_noun_ratio": float(pronoun_noun_ratio),
        "repeated_content_lemmas": float(repeated_content),
        "repeated_content_ratio": float(repeated_content_ratio),
    }


def adjacent_overlap_metrics(
    segments: List[Iterable[str]], lookahead: int = 1
) -> Dict[str, float]:
    """Compute normalized overlap metrics across adjacent text segments.

    The overlap follows TAACO-style adjacency windows:
    - lookahead=1 compares segment i with segment i+1
    - lookahead=2 compares segment i with the union of i+1 and i+2

    Returns a dictionary containing raw counts and normalized scores.
    """
    seg_sets = [_as_segment_set(seg) for seg in segments]
    n = len(seg_sets)

    if n < 2:
        return {
            "overlap_count": 0.0,
            "token_opportunities": 0.0,
            "pair_count": 0.0,
            "binary_overlap_pairs": 0.0,
            "overlap_per_opportunity": 0.0,
            "overlap_per_pair": 0.0,
            "binary_ratio": 0.0,
        }

    overlap_count = 0
    token_opportunities = 0
    pair_count = 0
    binary_overlap_pairs = 0

    for i in range(n - 1):
        left = seg_sets[i]
        if not left:
            continue

        if lookahead <= 1:
            if i + 1 >= n:
                continue
            right = seg_sets[i + 1]
        else:
            right = set()
            if i + 1 < n:
                right |= seg_sets[i + 1]
            if i + 2 < n:
                right |= seg_sets[i + 2]

        if not right:
            continue

        pair_count += 1
        token_opportunities += len(left)
        overlap = len(left & right)
        overlap_count += overlap
        if overlap > 0:
            binary_overlap_pairs += 1

    overlap_per_opportunity = (
        overlap_count / token_opportunities if token_opportunities else 0.0
    )
    overlap_per_pair = overlap_count / pair_count if pair_count else 0.0
    binary_ratio = binary_overlap_pairs / pair_count if pair_count else 0.0

    return {
        "overlap_count": float(overlap_count),
        "token_opportunities": float(token_opportunities),
        "pair_count": float(pair_count),
        "binary_overlap_pairs": float(binary_overlap_pairs),
        "overlap_per_opportunity": float(overlap_per_opportunity),
        "overlap_per_pair": float(overlap_per_pair),
        "binary_ratio": float(binary_ratio),
    }
