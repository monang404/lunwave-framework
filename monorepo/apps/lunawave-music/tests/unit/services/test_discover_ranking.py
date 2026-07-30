"""tests/unit/services/test_discover_ranking.py — mirrors services/discover_ranking.py

Purpose:
    Unit tests for the pure Discover ranking/scoring functions
    (compute_match_pct, build_taste_spectrum) extracted from
    persistence/discover_repo.py in T3.3. These are plain-number test
    cases, no DB/fixture involved — that's the whole point of splitting
    this math out into its own module.

Responsibilities:
    - compute_match_pct: rounding, ties, and the alpha+beta<=0 edge case.
    - build_taste_spectrum: normalization, "Lainnya" bucketing, limit
      handling, and empty/zero-total edge cases.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from services.discover_ranking import build_taste_spectrum, compute_match_pct


class TestComputeMatchPct:
    def test_high_alpha_gives_high_pct(self):
        assert compute_match_pct(9, 1) == 90

    def test_low_alpha_gives_low_pct(self):
        assert compute_match_pct(2, 8) == 20

    def test_equal_alpha_beta_gives_fifty(self):
        assert compute_match_pct(1, 1) == 50

    def test_rounds_to_nearest_int(self):
        # 100 * 1/3 == 33.33... -> 33
        assert compute_match_pct(1, 2) == 33
        # 100 * 2/3 == 66.66... -> 67
        assert compute_match_pct(2, 1) == 67

    def test_zero_total_returns_zero_instead_of_dividing_by_zero(self):
        assert compute_match_pct(0, 0) == 0


class TestBuildTasteSpectrum:
    def test_empty_rows_returns_empty_list(self):
        assert build_taste_spectrum([]) == []

    def test_zero_total_score_returns_empty_list(self):
        assert build_taste_spectrum([{"genre": "rock", "score": 0}]) == []

    def test_single_genre_is_one_hundred_percent(self):
        result = build_taste_spectrum([{"genre": "rock", "score": 10}], limit=6)
        assert result == [{"genre": "rock", "pct": 100}]

    def test_normalizes_to_percentages_with_lainnya_bucket(self):
        rows = [
            {"genre": "rock", "score": 10},
            {"genre": "jazz", "score": 5},
            {"genre": "blues", "score": 1},
        ]
        result = build_taste_spectrum(rows, limit=2)
        # 100*10/16 == 62.5 -> Python round-half-to-even gives 62
        assert result[0] == {"genre": "rock", "pct": 62}
        assert result[1]["genre"] == "Lainnya"
        # jazz(5) + blues(1) out of total 16 -> 38%
        assert result[1]["pct"] == 38

    def test_fewer_genres_than_limit_no_lainnya_bucket(self):
        rows = [{"genre": "rock", "score": 10}, {"genre": "jazz", "score": 5}]
        result = build_taste_spectrum(rows, limit=6)
        assert result == [
            {"genre": "rock", "pct": 67},
            {"genre": "jazz", "pct": 33},
        ]
        assert not any(r["genre"] == "Lainnya" for r in result)

    def test_limit_one_keeps_single_top_genre_and_buckets_rest(self):
        rows = [
            {"genre": "rock", "score": 6},
            {"genre": "jazz", "score": 3},
            {"genre": "blues", "score": 1},
        ]
        result = build_taste_spectrum(rows, limit=1)
        assert result[0] == {"genre": "rock", "pct": 60}
        assert result[1] == {"genre": "Lainnya", "pct": 40}

    def test_rows_must_already_be_sorted_score_desc_by_caller(self):
        """build_taste_spectrum trusts its input order (the repo's SQL
        does ORDER BY score DESC) — it does not re-sort."""
        rows = [{"genre": "jazz", "score": 1}, {"genre": "rock", "score": 10}]
        result = build_taste_spectrum(rows, limit=2)
        assert result[0]["genre"] == "jazz"
