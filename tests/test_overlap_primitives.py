from rhetoric_lint.overlap import adjacent_overlap_metrics, sentence_pair_givenness_metrics


def test_adjacent_overlap_metrics_adj1_basic():
    segments = [
        {"deploy", "service"},
        {"service", "healthcheck"},
        {"healthcheck", "alerts"},
    ]
    out = adjacent_overlap_metrics(segments, lookahead=1)

    assert out["pair_count"] == 2.0
    assert out["token_opportunities"] == 4.0
    assert out["overlap_count"] == 2.0
    assert out["binary_overlap_pairs"] == 2.0
    assert out["overlap_per_opportunity"] == 0.5
    assert out["binary_ratio"] == 1.0


def test_adjacent_overlap_metrics_adj2_union_lookahead():
    segments = [
        {"deploy", "service"},
        {"runtime"},
        {"service", "logs"},
    ]
    out = adjacent_overlap_metrics(segments, lookahead=2)

    # Pair 0 compares with union(segment1, segment2) so "service" overlaps.
    assert out["pair_count"] == 2.0
    assert out["overlap_count"] == 1.0
    assert out["binary_overlap_pairs"] == 1.0


def test_adjacent_overlap_metrics_handles_small_inputs():
    assert adjacent_overlap_metrics([], lookahead=1)["overlap_per_pair"] == 0.0
    assert adjacent_overlap_metrics([{"one"}], lookahead=2)["binary_ratio"] == 0.0


def test_sentence_pair_givenness_metrics_basic():
    prev = {
        "content": {"deploy", "service"},
    }
    cur = {
        "content": {"service", "status"},
    }
    counts = {"alpha_tokens": 5.0, "pronoun_tokens": 2.0, "noun_tokens": 1.0}
    out = sentence_pair_givenness_metrics(prev, cur, counts)

    assert out["pronoun_density"] == 0.4
    assert out["pronoun_noun_ratio"] == 2.0
    assert out["repeated_content_lemmas"] == 1.0
    assert out["repeated_content_ratio"] == 0.5
