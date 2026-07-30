"""
Module: persistence.artist_repo

Purpose:
    Repository for tracking artist statistics and fetching artist-specific tracks.

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

logger = structlog.get_logger(component="persistence.artist_repo")


class ArtistRepository:
    def __init__(self, conn):
        self._conn = conn
        self._reward_cache: dict[str, tuple[float, float]] | None = None

    @property
    def conn(self):
        return self._conn

    async def increment_artist_click(self, artist_name: str):
        if not self._conn:
            return
        try:
            await self._conn.execute(
                "UPDATE artists SET click_count = COALESCE(click_count, 0) + 1 WHERE nama = ?",
                (artist_name,),
            )
            await self._conn.commit()
        except Exception as e:
            logger.error(
                "artist_click_increment_failed",
                category=LC_PERSISTENCE,
                artist_name=artist_name,
                error_type=type(e).__name__,
                error=str(e),
            )

    async def get_all_artists(self, kategori: str | None = None) -> list[str]:
        if kategori:
            query = "SELECT nama FROM artists WHERE kategori = ? ORDER BY id"
            params = (kategori,)
        else:
            query = "SELECT nama FROM artists ORDER BY id"
            params = ()  # type: ignore

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        return [row["nama"] for row in rows]

    async def get_artist_songs_strict(self, artist: str, limit: int = 10) -> list[TrackInfo]:
        query = """
            SELECT s.youtube_id, s.judul, s.duration, a.nama
            FROM songs s
            JOIN artists a ON s.artist_id = a.id
            WHERE a.nama = ?
            ORDER BY RANDOM() LIMIT ?
        """
        async with self._conn.execute(query, (artist, limit)) as cursor:
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

    async def record_completion(self, artist_name: str) -> None:
        """Track selesai penuh — reward positif untuk bandit."""
        if not self._conn:
            return
        try:
            await self._conn.execute(
                "UPDATE artists SET reward_alpha = (COALESCE(reward_alpha, 1) * 0.98) + 1, reward_beta = COALESCE(reward_beta, 1) * 0.98 WHERE nama = ?",
                (artist_name,),
            )
            await self._conn.commit()
            if self._reward_cache is not None:
                a, b = self._reward_cache.get(artist_name, (1.0, 1.0))
                self._reward_cache[artist_name] = ((a * 0.98) + 1.0, b * 0.98)
        except Exception as e:
            logger.error(
                "artist_reward_completion_record_failed",
                category=LC_PERSISTENCE,
                artist_name=artist_name,
                error_type=type(e).__name__,
                error=str(e),
            )

    async def record_skip(self, artist_name: str) -> None:
        """Track skip dini — reward negatif untuk bandit."""
        if not self._conn:
            return
        try:
            await self._conn.execute(
                "UPDATE artists SET reward_alpha = COALESCE(reward_alpha, 1) * 0.98, reward_beta = (COALESCE(reward_beta, 1) * 0.98) + 1 WHERE nama = ?",
                (artist_name,),
            )
            await self._conn.commit()
            if self._reward_cache is not None:
                a, b = self._reward_cache.get(artist_name, (1.0, 1.0))
                self._reward_cache[artist_name] = (a * 0.98, (b * 0.98) + 1.0)
        except Exception as e:
            logger.error(
                "artist_reward_skip_record_failed",
                category=LC_PERSISTENCE,
                artist_name=artist_name,
                error_type=type(e).__name__,
                error=str(e),
            )

    async def get_reward_stats(self) -> dict[str, tuple[float, float]]:
        """Ambil {nama_artis: (alpha, beta)} untuk semua artis.
        Di-cache di in-memory untuk mencegah full-table scan DB setiap radio batch refill.
        """
        if self._reward_cache is not None:
            return self._reward_cache

        if not self._conn:
            return {}
        query = "SELECT nama, COALESCE(reward_alpha, 1) as a, COALESCE(reward_beta, 1) as b FROM artists"
        async with self._conn.execute(query) as cursor:
            rows = await cursor.fetchall()

        self._reward_cache = {row["nama"]: (float(row["a"]), float(row["b"])) for row in rows}
        return self._reward_cache
