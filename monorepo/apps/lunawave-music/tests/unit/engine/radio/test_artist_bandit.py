from engine.radio.artist_bandit import ArtistStat, sample_artists


def test_sample_artists_empty():
    assert sample_artists([], 2) == []


def test_sample_artists_with_stats():
    # A has great history (alpha=100), B has bad history (beta=100)
    candidates = [ArtistStat("A", alpha=100, beta=1), ArtistStat("B", alpha=1, beta=100)]

    # Run multiple times
    selected_A = 0
    for _ in range(100):
        if sample_artists(candidates, 1) == ["A"]:
            selected_A += 1

    assert selected_A > 80  # A should be chosen the vast majority of the time


def test_sample_artists_k_parameter():
    candidates = [ArtistStat("A"), ArtistStat("B"), ArtistStat("C")]
    selected = sample_artists(candidates, 2)
    assert len(selected) == 2
    for s in selected:
        assert s in ["A", "B", "C"]
