"""
Module: persistence.discover_repo

Purpose:
    Repository for Discover-tab personalization queries: bandit-ranked
    "Untuk Kamu" artists, "Belum Pernah Kamu Dengar" (unheard) artists,
    genre taste spectrum, genre affinity, and artist detail lookup.

    Split out from `artist_repo.py` / `genre_repo.py` on purpose (see
    docs/PATCHLOG.md PATCH-2026-07-17-070): those two repos own click/reward
    *tracking*, this one owns Discover *personalization reads* built on top
    of that data. Same split as `LibraryRepository` vs `TrackRepository`.

    T3.3: score/ranking arithmetic (bandit match_pct, taste-spectrum
    percentage normalization) has moved to services.discover_ranking
    (pure functions, no DB) — this repo returns raw rows only. Persistence
    is not allowed to import services (.importlinter), so
    services.discover_service calls services.discover_ranking itself once
    it has the raw rows from here. get_top_genre() is the one exception:
    it stays a repo method (needed by DiscoverRepositoryPort) but only
    needs the highest-scored row, not any percentage math, so it can stay
    self-sufficient without touching the ranking layer.

Responsibilities:
    - get_bandit_ranked_artists / get_unheard_artists — "Untuk Kamu" /
      "Belum Pernah Kamu Dengar" sections (raw reward_alpha/reward_beta,
      no match_pct — see services.discover_ranking.compute_match_pct).
    - get_taste_spectrum — raw genre/score rows, sorted score descending
      (see services.discover_ranking.build_taste_spectrum for the
      percentage/"Lainnya" normalization).
    - get_top_genre — top genre name (or None), derived from the same raw
      rows above without needing percentage normalization.
    - get_genre_artists_enriched — artists for a given genre, with cover+tags.
    - get_artist_detail — full detail (genres + up to 10 songs) for a sheet.

Depends on:
    - persistence.discover_enrich

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from typing import Any

import structlog

from core.log_categories import LC_PERSISTENCE
from persistence.discover_enrich import enrich_artists

logger = structlog.get_logger(component="persistence.discover")


class DiscoverRepository:
    def __init__(self, conn):
        self._conn = conn

    @property
    def conn(self):
        return self._conn

    async def get_bandit_ranked_artists(self, limit: int = 10) -> list[dict]:
        """ "Untuk Kamu": artis yang bandit (reward_alpha/beta) sudah pernah
        belajar sesuatu tentangnya (bukan default alpha=beta=1), diurut
        berdasarkan posterior mean alpha/(alpha+beta) — makin tinggi makin
        besar kemungkinan disukai user.

        Raw row saja (T3.3): `reward_alpha`/`reward_beta` dikembalikan
        apa adanya, TIDAK ada `match_pct` di sini lagi — itu tugas
        `services.discover_ranking.compute_match_pct(alpha, beta)`,
        dipanggil oleh `services.discover_service.get_for_you()` setelah
        baris ini didapat.
        """
        if not self._conn:
            return []
        query = """
            SELECT id, nama, kategori, tahun_aktif,
                   COALESCE(reward_alpha, 1) AS reward_alpha,
                   COALESCE(reward_beta, 1) AS reward_beta
            FROM artists
            WHERE COALESCE(reward_alpha, 1) > 1 OR COALESCE(reward_beta, 1) > 1
            ORDER BY (CAST(COALESCE(reward_alpha, 1) AS REAL)
                      / (COALESCE(reward_alpha, 1) + COALESCE(reward_beta, 1))) DESC
            LIMIT ?
        """
        try:
            async with self._conn.execute(query, (limit,)) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(
                "discover_query_failed",
                category=LC_PERSISTENCE,
                query_type="bandit_ranked_artists",
                error_type=type(e).__name__,
                error=str(e),
            )
            return []

        return await enrich_artists(self._conn, rows)

    async def get_unheard_artists(self, limit: int = 10) -> list[dict]:
        """ "Belum Pernah Kamu Dengar": artis yang bandit belum pernah
        disentuh sama sekali (alpha=beta=1, artinya belum ada
        completion/skip tercatat) DAN belum pernah di-klik dari Discover
        (click_count=0) — supaya section ini benar-benar berisi hal baru,
        bukan sesuatu yang user sudah pernah lihat tapi belum diputar.
        """
        if not self._conn:
            return []
        query = """
            SELECT id, nama, kategori, tahun_aktif
            FROM artists
            WHERE COALESCE(reward_alpha, 1) = 1
              AND COALESCE(reward_beta, 1) = 1
              AND COALESCE(click_count, 0) = 0
            ORDER BY RANDOM()
            LIMIT ?
        """
        try:
            async with self._conn.execute(query, (limit,)) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(
                "discover_query_failed",
                category=LC_PERSISTENCE,
                query_type="unheard_artists",
                error_type=type(e).__name__,
                error=str(e),
            )
            return []

        return await enrich_artists(self._conn, rows)

    async def get_taste_spectrum(self) -> list[dict]:
        """Raw genre/score rows di balik taste spectrum: SUM(play_count +
        is_favorite*3) per genre, diurut score descending, sudah difilter
        `score > 0`.

        Raw row saja (T3.3) — TIDAK ada normalisasi persentase atau bucket
        "Lainnya" di sini lagi. Itu tugas
        `services.discover_ranking.build_taste_spectrum(rows, limit)`,
        dipanggil oleh `services.discover_service.get_taste_spectrum()`
        setelah baris ini didapat.

        Caveat (lihat AI_CONTEXT / implementation-plan): join
        tracks.artist -> artists.nama hanya reliable untuk lagu yang
        datang dari Radio Mode/library; lagu hasil pencarian bebas
        (nama artist beda karena uploader YouTube) tidak ikut kehitung.
        Ini batasan yang diketahui, bukan bug.

        Return [] kalau histori kosong (tracks tidak ber-genre sama
        sekali) — caller (discover_service/frontend) bertanggung jawab
        menampilkan fallback UI untuk kasus ini, bukan repo ini.
        """
        if not self._conn:
            return []
        query = """
            SELECT g.nama_genre AS genre,
                   SUM(t.play_count + t.is_favorite * 3) AS score
            FROM tracks t
            JOIN artists a ON a.nama = t.artist
            JOIN artist_genres ag ON ag.artist_id = a.id
            JOIN genres g ON g.id = ag.genre_id
            GROUP BY g.nama_genre
            HAVING score > 0
            ORDER BY score DESC
        """
        try:
            async with self._conn.execute(query) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(
                "discover_query_failed",
                category=LC_PERSISTENCE,
                query_type="taste_spectrum",
                error_type=type(e).__name__,
                error=str(e),
            )
            return []

        return rows

    async def get_top_genre(self) -> str | None:
        """Genre teratas dari histori putar, atau None kalau histori
        kosong (dipakai untuk seed section "Karena Kamu Suka [Genre]").

        Baris dari `get_taste_spectrum()` sudah `ORDER BY score DESC`,
        jadi genre teratas cukup diambil dari baris pertama — tidak perlu
        normalisasi persentase (`services.discover_ranking.build_taste_spectrum`)
        untuk sekadar tahu genre mana yang tertinggi.
        """
        rows = await self.get_taste_spectrum()
        if not rows:
            return None
        return rows[0]["genre"]

    async def get_genre_artists_enriched(self, genre_name: str, limit: int = 4) -> list[dict]:
        """Versi `GenreRepository.get_genre_artists` yang mengembalikan
        row lengkap (bukan cuma nama) sudah di-enrich cover+genre, untuk
        dipakai kartu artis di section "Karena Kamu Suka [Genre]".
        """
        if not self._conn:
            return []
        query = """
            SELECT a.id, a.nama, a.kategori, a.tahun_aktif
            FROM artists a
            JOIN artist_genres ag ON a.id = ag.artist_id
            JOIN genres g ON ag.genre_id = g.id
            WHERE g.nama_genre = ?
            ORDER BY RANDOM()
            LIMIT ?
        """
        try:
            async with self._conn.execute(query, (genre_name, limit)) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]
        except Exception as e:
            logger.error(
                "discover_query_failed",
                category=LC_PERSISTENCE,
                query_type="genre_artists_enriched",
                error_type=type(e).__name__,
                error=str(e),
            )
            return []

        return await enrich_artists(self._conn, rows)

    async def search_tracks(
        self,
        query: str,
        kategori: str | None = None,
        decade: int | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Quick Search Discover: cari lagu menggunakan FTS5 (Full-Text Search)
        untuk pencarian berkecepatan tinggi, paralel, dan otomatis merangking
        hasil berbasis relevansi bm25.
        """
        if not self._conn:
            return []

        q = (query or "").strip()
        if not q:
            return []

        tokens = q.split()
        if not tokens:
            return []

        import re

        safe_tokens = [re.sub(r"[^\w\s]", "", t) for t in tokens]
        safe_tokens = [t for t in safe_tokens if t]
        if not safe_tokens:
            return []

        match_query = " ".join([f'"{t}"*' for t in safe_tokens])

        # --- Sumber 1: tracks (cache/history, metadata lengkap) ---
        track_conds = ["tracks_fts MATCH ?"]
        track_params: list[Any] = [match_query]

        if kategori:
            track_conds.append("t.artist IN (SELECT nama FROM artists WHERE kategori = ?)")
            track_params.append(kategori)
        if decade is not None:
            track_conds.append(
                "t.artist IN ("
                "SELECT nama FROM artists "
                "WHERE CAST(tahun_aktif AS INTEGER) >= ? "
                "AND CAST(tahun_aktif AS INTEGER) < ?"
                ")"
            )
            track_params.extend([decade, decade + 10])

        sql_tracks = f"""
            SELECT t.video_id, t.title, t.artist, t.duration, t.thumbnail,
                   t.local_path, t.view_count, t.is_favorite,
                   bm25(tracks_fts) AS rank
            FROM tracks_fts fts
            JOIN tracks t ON t.rowid = fts.rowid
            WHERE {" AND ".join(track_conds)}
            ORDER BY rank
            LIMIT ?
        """
        track_params_full = track_params + [limit]

        # --- Sumber 2: songs JOIN artists (katalog kurasi) ---
        song_conds = ["songs_fts MATCH ?"]
        song_params: list[Any] = [match_query]

        if kategori:
            song_conds.append("a.kategori = ?")
            song_params.append(kategori)
        if decade is not None:
            song_conds.append(
                "CAST(a.tahun_aktif AS INTEGER) >= ? AND CAST(a.tahun_aktif AS INTEGER) < ?"
            )
            song_params.extend([decade, decade + 10])

        sql_songs = f"""
            SELECT s.youtube_id AS video_id, s.judul AS title, a.nama AS artist,
                   s.duration AS duration,
                   bm25(songs_fts) AS rank
            FROM songs_fts fts
            JOIN songs s ON s.id = fts.rowid
            JOIN artists a ON a.id = s.artist_id
            WHERE {" AND ".join(song_conds)}
            ORDER BY rank
            LIMIT ?
        """
        song_params_full = song_params + [limit]

        try:
            import asyncio

            track_rows, song_rows = await asyncio.gather(
                self._search_tracks_only(sql_tracks, track_params_full),
                self._search_songs_only(sql_songs, song_params_full),
            )
        except Exception as e:
            logger.error(
                "search_tracks_query_failed",
                category=LC_PERSISTENCE,
                error_type=type(e).__name__,
                error=str(e),
            )
            return []

        # --- Gabung + dedup (tracks menang atas songs untuk video_id sama) ---
        merged: dict[str, dict] = {}
        for r in track_rows:
            merged[r["video_id"]] = {
                "video_id": r["video_id"],
                "title": r["title"],
                "artist": r["artist"],
                "duration": r["duration"],
                "thumbnail": r["thumbnail"],
                "local_path": r["local_path"],
                "view_count": r["view_count"],
                "is_favorite": r["is_favorite"],
                "rank": r["rank"],
            }
        for r in song_rows:
            if r["video_id"] in merged:
                continue
            merged[r["video_id"]] = {
                "video_id": r["video_id"],
                "title": r["title"],
                "artist": r["artist"],
                "duration": r["duration"],
                "thumbnail": f"https://i.ytimg.com/vi/{r['video_id']}/mqdefault.jpg",
                "local_path": None,
                "view_count": None,
                "is_favorite": 0,
                "rank": r["rank"],
            }

        # --- Ranking: frasa utuh > token-only, lalu bm25 rank ---
        full_phrase = q.lower()

        rows = sorted(merged.values(), key=lambda row: self._search_sort_key(row, full_phrase))

        # Bersihkan field rank internal
        for r in rows:
            r.pop("rank", None)

        return rows[:limit]

    async def _search_tracks_only(self, sql_tracks: str, params: list) -> list[dict]:
        """Isi lama nested function `_fetch_tracks()` di
        `search_tracks()` -- diekstrak jadi method privat biasa
        (Temuan K, proposal_god_file_splitting.md §4.K) supaya
        bisa di-unit-test terpisah dari `_search_songs_only`.
        """
        async with self._conn.execute(sql_tracks, params) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

    async def _search_songs_only(self, sql_songs: str, params: list) -> list[dict]:
        """Isi lama nested function `_fetch_songs()` -- lihat
        `_search_tracks_only` untuk rationale yang sama."""
        async with self._conn.execute(sql_songs, params) as cursor:
            return [dict(r) for r in await cursor.fetchall()]

    @staticmethod
    def _search_sort_key(row: dict, full_phrase: str):
        """Isi lama nested function `_sort_key()` di dalam
        `search_tracks()` -- diekstrak jadi staticmethod (Temuan K).
        `full_phrase` dulu diambil dari closure, sekarang parameter
        eksplisit."""
        title_l = (row["title"] or "").lower()
        artist_l = (row["artist"] or "").lower()
        is_phrase_match = full_phrase in title_l or full_phrase in artist_l
        return (0 if is_phrase_match else 1, row["rank"])

    async def get_artist_detail(self, nama: str) -> dict | None:
        """Info lengkap satu artis untuk detail sheet: data dasar + cover +
        genre tags + hingga 10 lagu. Return None kalau artis tidak
        ditemukan (caller balas error/empty state, bukan sheet kosong).
        """
        if not self._conn:
            return None
        try:
            async with self._conn.execute(
                "SELECT id, nama, kategori, tahun_aktif FROM artists WHERE nama = ?",
                (nama,),
            ) as cursor:
                artist_row = await cursor.fetchone()
        except Exception as e:
            logger.error(
                "artist_detail_query_failed",
                category=LC_PERSISTENCE,
                artist_name=nama,
                error_type=type(e).__name__,
                error=str(e),
            )
            return None

        if not artist_row:
            return None

        artist = dict(artist_row)
        enriched = await enrich_artists(self._conn, [artist])
        detail = enriched[0]

        try:
            async with self._conn.execute(
                """
                SELECT youtube_id, judul, duration FROM songs
                WHERE artist_id = ?
                ORDER BY id
                LIMIT 10
                """,
                (artist["id"],),
            ) as cursor:
                song_rows = await cursor.fetchall()
        except Exception as e:
            logger.error(
                "artist_detail_songs_query_failed",
                category=LC_PERSISTENCE,
                artist_name=artist["nama"],
                error_type=type(e).__name__,
                error=str(e),
            )
            song_rows = []

        detail["songs"] = [
            {
                "video_id": row["youtube_id"],
                "title": row["judul"],
                "duration": row["duration"],
                "thumbnail": f"https://i.ytimg.com/vi/{row['youtube_id']}/mqdefault.jpg",
            }
            for row in song_rows
        ]
        return detail
