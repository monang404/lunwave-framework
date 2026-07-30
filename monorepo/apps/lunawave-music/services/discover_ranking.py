"""
Module: services.discover_ranking

Purpose:
    Pure scoring/aggregation functions for Discover-tab personalization,
    split out of persistence.discover_repo.py (T3.3) so the ranking math
    is unit-testable with plain numbers instead of a real DB, and so it
    lives in the services layer rather than persistence (which is not
    allowed to depend on services — see .importlinter).

Responsibilities:
    - compute_match_pct(alpha, beta): bandit posterior-mean match score
      (0-100) shown on "Untuk Kamu" artist cards.
    - build_taste_spectrum(rows, limit): normalize raw genre/score rows
      into a percentage spectrum with a "Lainnya" bucket for the tail.

    Callers (services.discover_service) fetch raw rows from
    persistence.discover_repo first, then call these functions to turn
    raw data into the values the frontend actually displays.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless (no I/O, pure functions).
"""


def compute_match_pct(alpha: float, beta: float) -> int:
    """Bandit posterior mean alpha/(alpha+beta) as a rounded 0-100 percent.

    Higher means the bandit has learned the user is more likely to like
    this artist. Used to label "Untuk Kamu" artist cards.
    """
    total = alpha + beta
    if total <= 0:
        return 0
    return round(100 * alpha / total)


def build_taste_spectrum(rows: list[dict], limit: int = 6) -> list[dict]:
    """Turn raw ``{"genre": ..., "score": ...}`` rows into a normalized
    percentage spectrum, folding everything past the top ``limit - 1``
    genres into a single "Lainnya" bucket so the bar doesn't split into
    dozens of thin slices.

    ``rows`` should already be sorted by score descending (the repo's SQL
    does this with ``ORDER BY score DESC``) and pre-filtered to
    ``score > 0``. Returns ``[]`` for empty input or non-positive total
    score.
    """
    if not rows:
        return []

    total = sum(r["score"] for r in rows)
    if total <= 0:
        return []

    top = rows[: max(limit - 1, 1)] if limit > 1 else rows[:1]
    rest = rows[len(top) :]

    spectrum = [{"genre": r["genre"], "pct": round(100 * r["score"] / total)} for r in top]
    if rest:
        rest_score = sum(r["score"] for r in rest)
        if rest_score > 0:
            spectrum.append({"genre": "Lainnya", "pct": round(100 * rest_score / total)})

    return spectrum
