"""
Module: persistence.library_repo

Purpose:
    Repository for global library operations such as fetching random songs.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.state

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from typing import Any

from core.state import TrackInfo


class LibraryRepository:
    def __init__(self, conn):
        self._conn = conn

    @property
    def conn(self):
        return self._conn

    async def get_random_songs(
        self,
        limit: int = 12,
        exclude_ids: set[str] | None = None,
        artists: list[str] | None = None,
        artist: str | None = None,
        max_per_artist: int = 3,
    ) -> list[TrackInfo]:
        if artist and not artists:
            artists = [artist]
        if exclude_ids is None:
            exclude_ids = set()

        placeholders = ",".join("?" for _ in exclude_ids)
        query = """
            WITH RankedSongs AS (
                SELECT s.youtube_id, s.judul, s.duration, a.nama,
                       ROW_NUMBER() OVER (PARTITION BY s.artist_id ORDER BY RANDOM()) as rn
                FROM songs s
                JOIN artists a ON s.artist_id = a.id
                WHERE 1=1
        """
        params: list[Any] = []
        if artists:
            artist_placeholders = ",".join("?" for _ in artists)
            query += f" AND a.nama IN ({artist_placeholders})"
            params.extend(artists)

        if exclude_ids:
            query += f" AND s.youtube_id NOT IN ({placeholders})"
            params.extend(exclude_ids)

        query += """
            )
            SELECT youtube_id, judul, duration, nama
            FROM RankedSongs
            WHERE rn <= ?
            ORDER BY RANDOM() LIMIT ?
        """
        params.append(max_per_artist)
        params.append(limit)

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        tracks = []
        for row in rows:
            tracks.append(
                TrackInfo(
                    video_id=row["youtube_id"],
                    title=row["judul"],
                    artist=row["nama"],
                    duration=row["duration"],
                    thumbnail=f"https://i.ytimg.com/vi/{row['youtube_id']}/mqdefault.jpg",
                )
            )
        return tracks
