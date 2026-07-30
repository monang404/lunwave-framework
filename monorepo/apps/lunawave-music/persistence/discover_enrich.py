"""
Module: persistence.discover_enrich

Purpose:
    Shared batch-enrichment helper for Discover personalization queries.
    Given a list of artist rows, attach a cover thumbnail and genre tag
    list to each one using two queries total for the whole batch (never
    per-artist), so `discover_repo.py` doesn't run into N+1 query fan-out
    when enriching a page of results.

Responsibilities:
    - enrich_artists(conn, artist_rows) -> same rows + "cover" + "genres".

Depends on:
    None (raw SQL only; no dependency on other repos)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from typing import Any


async def enrich_artists(conn, artist_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach `cover` (YouTube thumbnail URL, or None if the artist has no
    songs yet) and `genres` (list[str], possibly empty) to each row.

    Each item in `artist_rows` must have an "id" key. Returns new dicts;
    input rows are not mutated.

    Exactly two queries run regardless of how many artists are passed in:
    - one MIN(id)-per-artist_id query for a stable "first" song to use as
      cover art (deterministic, so cover art doesn't flicker between two
      calls for the same artist — RANDOM() would).
    - one artist_genres/genres join for all requested artist_ids at once.
    """
    if not artist_rows:
        return []

    artist_ids = [row["id"] for row in artist_rows]
    placeholders = ",".join("?" for _ in artist_ids)

    covers: dict[int, str] = {}
    cover_query = (
        "SELECT artist_id, youtube_id FROM songs "
        "WHERE id IN (SELECT MIN(id) FROM songs "
        f"WHERE artist_id IN ({placeholders}) "
        "GROUP BY artist_id)"
    )  # nosec B608
    async with conn.execute(cover_query, artist_ids) as cursor:
        async for row in cursor:
            covers[row["artist_id"]] = f"https://i.ytimg.com/vi/{row['youtube_id']}/mqdefault.jpg"

    genres: dict[int, list[str]] = {aid: [] for aid in artist_ids}
    genre_query = (
        "SELECT ag.artist_id, g.nama_genre FROM artist_genres ag "
        "JOIN genres g ON g.id = ag.genre_id "
        f"WHERE ag.artist_id IN ({placeholders})"
    )  # nosec B608
    async with conn.execute(genre_query, artist_ids) as cursor:
        async for row in cursor:
            genres.setdefault(row["artist_id"], []).append(row["nama_genre"])

    enriched = []
    for row in artist_rows:
        item = dict(row)
        item["cover"] = covers.get(row["id"])
        item["genres"] = genres.get(row["id"], [])
        enriched.append(item)
    return enriched
