"""
Module: services.discover_service

Purpose:
    Query the SQLite database to provide discover-page data: recently played
    tracks, favorites, cached tracks, and featured artists/genres.

Responsibilities:
    - Expose async methods for each discover data category.
    - Return empty lists gracefully when the DB connection is unavailable.
    - Expose personalization wrappers (for_you, unheard, genre_affinity,
      taste_spectrum, artist_detail) backed by persistence.discover_repo.
    - Apply score/ranking math (match_pct, taste-spectrum normalization)
      via services.discover_ranking on the raw rows discover_repo returns
      (T3.3 — discover_repo only returns raw rows, this is where the pure
      ranking functions actually get called).

Depends on:
    - core.ports
    - core.state
    - persistence.discover_repo
    - services.discover_ranking

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (async; read-only queries).
"""

from typing import Any

from core.ports import DiscoverRepositoryPort
from core.state import TrackInfo
from services import discover_ranking


class DiscoverService:
    def __init__(self, discover: DiscoverRepositoryPort):
        self.discover = discover

    async def get_recent(self, n: int) -> list[TrackInfo]:
        """Mengambil n lagu yang terakhir diputar dari DB."""
        if not getattr(self.discover, "conn", None):
            return []

        tracks = []
        try:
            async with self.discover.conn.execute(  # type: ignore
                "SELECT * FROM tracks ORDER BY last_played DESC LIMIT ?", (n,)
            ) as cursor:
                async for row in cursor:
                    d = dict(row)
                    tracks.append(
                        TrackInfo(
                            video_id=d["video_id"],
                            title=d["title"],
                            artist=d["artist"],
                            duration=d["duration"],
                            thumbnail=d["thumbnail"],
                            local_path=d["local_path"],
                            stream_url=d["stream_url"],
                            view_count=d["view_count"],
                            is_favorite=d.get("is_favorite", 0),
                        )
                    )
        except Exception as e:
            raise e
        return tracks

    async def get_favorites(self, n: int) -> list[TrackInfo]:
        """Mengambil n lagu dengan play_count tertinggi atau eksplisit difavoritkan dari DB."""
        if not getattr(self.discover, "conn", None):
            return []

        tracks = []
        try:
            async with self.discover.conn.execute(  # type: ignore
                "SELECT * FROM tracks WHERE is_favorite = 1 OR play_count > 0 ORDER BY is_favorite DESC, play_count DESC LIMIT ?",
                (n,),
            ) as cursor:
                async for row in cursor:
                    d = dict(row)
                    tracks.append(
                        TrackInfo(
                            video_id=d["video_id"],
                            title=d["title"],
                            artist=d["artist"],
                            duration=d["duration"],
                            thumbnail=d["thumbnail"],
                            local_path=d["local_path"],
                            stream_url=d["stream_url"],
                            view_count=d["view_count"],
                            is_favorite=d.get("is_favorite", 0),
                        )
                    )
        except Exception as e:
            raise e
        return tracks

    async def get_cached(self, n: int) -> list[TrackInfo]:
        """Mengambil n lagu yang sudah ter-cache (local_path is not null)."""
        if not getattr(self.discover, "conn", None):
            return []

        tracks = []
        try:
            async with self.discover.conn.execute(  # type: ignore
                "SELECT * FROM tracks WHERE local_path IS NOT NULL ORDER BY last_played DESC LIMIT ?",
                (n,),
            ) as cursor:
                async for row in cursor:
                    d = dict(row)
                    tracks.append(
                        TrackInfo(
                            video_id=d["video_id"],
                            title=d["title"],
                            artist=d["artist"],
                            duration=d["duration"],
                            thumbnail=d["thumbnail"],
                            local_path=d["local_path"],
                            stream_url=d["stream_url"],
                            view_count=d["view_count"],
                            is_favorite=d.get("is_favorite", 0),
                        )
                    )
        except Exception as e:
            raise e
        return tracks

    async def get_featured_artists(self, n: int) -> list[dict]:
        """Mengambil n artis acak dari tabel artists beserta click_count."""
        if not getattr(self.discover, "conn", None):
            return []

        artists = []
        try:
            async with self.discover.conn.execute(  # type: ignore
                "SELECT id, nama, kategori, tahun_aktif, COALESCE(click_count, 0) as click_count FROM artists WHERE id IN (SELECT id FROM artists ORDER BY RANDOM() LIMIT ?)",
                (n,),
            ) as cursor:
                async for row in cursor:
                    artists.append(dict(row))
        except Exception as e:
            raise e
        return artists

    async def get_featured_genres(self, n: int) -> list[dict]:
        """Mengambil n genre acak dari tabel genres beserta click_count."""
        if not getattr(self.discover, "conn", None):
            return []

        genres = []
        try:
            async with self.discover.conn.execute(  # type: ignore
                "SELECT id, nama_genre, COALESCE(click_count, 0) as click_count FROM genres WHERE id IN (SELECT id FROM genres ORDER BY RANDOM() LIMIT ?)",
                (n,),
            ) as cursor:
                async for row in cursor:
                    genres.append(
                        {
                            "id": row["id"],
                            "nama_genre": row["nama_genre"],
                            "click_count": row["click_count"],
                        }
                    )
        except Exception as e:
            print(f"Error in get_featured_genres: {e}")
        return genres

    # --- Discover personalization (PATCH-2026-07-17-070) ---
    # Delegates directly to persistence.discover_repo.DiscoverRepository
    # (T2.2d: no longer routed through the Database facade).

    async def get_for_you(self, n: int) -> list[dict[str, Any]]:
        """ "Untuk Kamu": artis top hasil bandit ranking. Kosong kalau
        bandit belum pernah belajar apapun (semua artis masih alpha=beta=1)
        — caller/frontend fallback ke featured/random seperti sekarang.

        `discover_repo` mengembalikan raw row (`reward_alpha`/`reward_beta`,
        tanpa `match_pct` — T3.3); `match_pct` dihitung di sini lewat
        `discover_ranking.compute_match_pct` sebelum dikembalikan ke caller.
        """
        if not getattr(self.discover, "conn", None):
            return []
        rows = await self.discover.get_bandit_ranked_artists(n)
        for row in rows:
            row["match_pct"] = discover_ranking.compute_match_pct(
                row["reward_alpha"], row["reward_beta"]
            )
        return rows

    async def get_unheard(self, n: int) -> list[dict[str, Any]]:
        """ "Belum Pernah Kamu Dengar": artis yang benar-benar belum
        tersentuh (bandit maupun click)."""
        if not getattr(self.discover, "conn", None):
            return []
        return await self.discover.get_unheard_artists(n)

    async def get_genre_affinity(self, n: int) -> dict[str, Any]:
        """ "Karena Kamu Suka [Genre]": genre teratas dari taste spectrum +
        artis lain di genre itu. `genre=None` kalau histori putar kosong
        (user baru) — caller menampilkan fallback UI, bukan section kosong."""
        if not getattr(self.discover, "conn", None):
            return {"genre": None, "artists": []}
        genre = await self.discover.get_top_genre()
        if not genre:
            return {"genre": None, "artists": []}
        artists = await self.discover.get_genre_artists_enriched(genre, n)
        return {"genre": genre, "artists": artists}

    async def get_taste_spectrum(self) -> list[dict[str, Any]]:
        """Breakdown genre dari histori putar, dinormalisasi ke persentase.
        [] kalau histori kosong.

        `discover_repo` mengembalikan raw row genre/score saja (T3.3);
        normalisasi persentase + bucket "Lainnya" dilakukan di sini lewat
        `discover_ranking.build_taste_spectrum`.
        """
        if not getattr(self.discover, "conn", None):
            return []
        rows = await self.discover.get_taste_spectrum()
        return discover_ranking.build_taste_spectrum(rows, limit=6)

    async def get_artist_detail(self, nama: str) -> dict[str, Any] | None:
        """Detail lengkap satu artis (untuk artist detail sheet). None
        kalau artis tidak ditemukan."""
        if not getattr(self.discover, "conn", None):
            return None
        return await self.discover.get_artist_detail(nama)
