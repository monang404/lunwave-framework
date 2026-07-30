"""
Module: persistence.genre_repo

Purpose:
    Repository for fetching genre information and tracking genre popularity.

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

import structlog

from core.log_categories import LC_PERSISTENCE
from core.state import TrackInfo

logger = structlog.get_logger(component="persistence.genre_repo")


class GenreRepository:
    def __init__(self, conn):
        self._conn = conn

    async def increment_genre_click(self, genre_name: str):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                "UPDATE genres SET click_count = COALESCE(click_count, 0) + 1 WHERE nama_genre = ?",
                (genre_name,),
            )
            await self._conn.commit()
        except Exception as e:
            logger.error(
                "genre_click_increment_failed",
                category=LC_PERSISTENCE,
                genre_name=genre_name,
                error_type=type(e).__name__,
                error=str(e),
            )

    async def get_genre_artists(self, genre_name: str, limit: int = 4) -> list[str]:
        if not self._conn:
            return []
        artists = []
        try:
            async with self._conn.execute(
                """SELECT a.nama FROM artists a
                   JOIN artist_genres ag ON a.id = ag.artist_id
                   JOIN genres g ON ag.genre_id = g.id
                   WHERE g.nama_genre = ?
                   ORDER BY RANDOM() LIMIT ?""",
                (genre_name, limit),
            ) as cursor:
                async for row in cursor:
                    artists.append(row["nama"])
        except Exception as e:
            logger.error(
                "genre_artists_query_failed",
                category=LC_PERSISTENCE,
                genre_name=genre_name,
                error_type=type(e).__name__,
                error=str(e),
            )
        return artists

    async def get_genre_songs(
        self, genre_name: str, total_limit: int = 12, max_per_artist: int = 3
    ) -> list[TrackInfo]:
        query = """
            WITH GenreSongs AS (
                SELECT s.youtube_id, s.judul, s.duration, a.nama,
                       ROW_NUMBER() OVER (PARTITION BY s.artist_id ORDER BY RANDOM()) as rn
                FROM songs s
                JOIN artists a ON s.artist_id = a.id
                JOIN artist_genres ag ON a.id = ag.artist_id
                JOIN genres g ON ag.genre_id = g.id
                WHERE g.nama_genre = ?
            )
            SELECT youtube_id, judul, duration, nama
            FROM GenreSongs
            WHERE rn <= ?
            ORDER BY RANDOM() LIMIT ?
        """
        async with self._conn.execute(query, (genre_name, max_per_artist, total_limit)) as cursor:
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
