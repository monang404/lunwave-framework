"""
Module: persistence.track_repo

Purpose:
    Repository for track metadata, play counts, favorites, and local file paths.

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

import time

import structlog

from core.log_categories import LC_PERSISTENCE
from core.state import TrackInfo

logger = structlog.get_logger(component="persistence.track_repo")


class TrackRepository:
    def __init__(self, conn):
        self._conn = conn

    async def get_track(self, video_id: str) -> TrackInfo | None:
        """Retrieves track metadata from the database as a TrackInfo entity."""
        async with self._conn.execute(
            "SELECT * FROM tracks WHERE video_id = ?", (video_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            is_fav = 0
            if "is_favorite" in row.keys():
                is_fav = row["is_favorite"] or 0
            loudness = row["loudness_lufs"] if "loudness_lufs" in row.keys() else None
            last_position = row["last_position"] if "last_position" in row.keys() else 0.0
            true_peak = row["true_peak_dbtp"] if "true_peak_dbtp" in row.keys() else None
            return TrackInfo(
                video_id=row["video_id"],
                title=row["title"],
                artist=row["artist"],
                duration=row["duration"],
                thumbnail=row["thumbnail"],
                local_path=row["local_path"],
                stream_url=row["stream_url"],
                view_count=row["view_count"],
                stream_url_ts=row["stream_url_ts"],
                play_count=row["play_count"],
                last_played=row["last_played"],
                is_favorite=is_fav,
                loudness_lufs=loudness,
                last_position=last_position,
                true_peak_dbtp=true_peak,
            )

    async def upsert_track(
        self, track: TrackInfo, stream_url: str | None = None, local_path: str | None = None
    ):
        """Inserts or updates a track record (metadata + cache URLs only)."""
        ts = int(time.time())
        query = """
            INSERT INTO tracks (
                video_id, title, artist, duration, view_count, thumbnail,
                stream_url, stream_url_ts, local_path, last_played
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title=excluded.title,
                artist=excluded.artist,
                duration=excluded.duration,
                view_count=excluded.view_count,
                thumbnail=excluded.thumbnail,
                stream_url=COALESCE(excluded.stream_url, tracks.stream_url),
                stream_url_ts=COALESCE(excluded.stream_url_ts, tracks.stream_url_ts),
                local_path=COALESCE(excluded.local_path, tracks.local_path),
                last_played=excluded.last_played
        """
        await self._conn.execute(
            query,
            (
                track.video_id,
                track.title,
                track.artist,
                track.duration,
                track.view_count,
                track.thumbnail,
                stream_url,
                ts if stream_url else None,
                local_path,
                ts,
            ),
        )
        await self._conn.commit()

    async def update_stream_url_only(self, video_id: str, stream_url: str):
        """Hanya update stream_url tanpa mengubah metadata (mencegah overwite dengan 'Temp')."""
        ts = int(time.time())
        await self._conn.execute(
            "UPDATE tracks SET stream_url=?, stream_url_ts=? WHERE video_id=?",
            (stream_url, ts, video_id),
        )
        await self._conn.commit()

    async def set_local_path(self, video_id: str, local_path: str | None):
        """Set local_path explicitly (can be used to clear it by passing None)."""
        await self._conn.execute(
            "UPDATE tracks SET local_path=? WHERE video_id=?", (local_path, video_id)
        )
        await self._conn.commit()

    async def increment_play_count(self, video_id: str):
        """Only called when a track actually starts playing."""
        ts = int(time.time())
        await self._conn.execute(
            "UPDATE tracks SET play_count = play_count + 1, last_played = ? WHERE video_id = ?",
            (ts, video_id),
        )
        await self._conn.commit()

    async def evict_stale_tracks(self) -> int:
        """Hapus track yang benar-benar tidak aktif"""
        thirty_days_ago = int(time.time()) - (30 * 24 * 3600)
        cursor = await self._conn.execute(
            """DELETE FROM tracks
               WHERE play_count = 0
                 AND local_path IS NULL
                 AND (is_favorite = 0 OR is_favorite IS NULL)
                 AND (
                     stream_url_ts IS NULL
                     OR stream_url_ts < ?
                 )""",
            (thirty_days_ago,),
        )
        await self._conn.commit()
        deleted = cursor.rowcount
        if deleted:
            logger.info(
                "cache_eviction_completed",
                category=LC_PERSISTENCE,
                deleted_count=deleted,
            )
        return deleted

    async def toggle_favorite(self, video_id: str) -> int:
        """Toggles the favorite status of a track dan kembalikan state baru (0 atau 1)."""
        async with self._conn.execute(
            "SELECT 1 FROM tracks WHERE video_id = ?", (video_id,)
        ) as cursor:
            if not await cursor.fetchone():
                return 0

        await self._conn.execute(
            "UPDATE tracks SET is_favorite = 1 - COALESCE(is_favorite, 0) WHERE video_id = ?",
            (video_id,),
        )
        await self._conn.commit()

        async with self._conn.execute(
            "SELECT is_favorite FROM tracks WHERE video_id = ?", (video_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return int(row["is_favorite"] or 0) if row else 0

    async def set_loudness(
        self, video_id: str, lufs: float, true_peak: float | None = None
    ) -> None:
        """Simpan hasil pengukuran integrated loudness (LUFS) dan opsional true peak (dBTP)."""
        if true_peak is not None:
            await self._conn.execute(
                "UPDATE tracks SET loudness_lufs = ?, true_peak_dbtp = ? WHERE video_id = ?",
                (lufs, true_peak, video_id),
            )
        else:
            await self._conn.execute(
                "UPDATE tracks SET loudness_lufs = ? WHERE video_id = ?",
                (lufs, video_id),
            )
        await self._conn.commit()

    async def set_last_position(self, video_id: str, position: float) -> None:
        """Simpan last playback position."""
        await self._conn.execute(
            "UPDATE tracks SET last_position = ? WHERE video_id = ?",
            (position, video_id),
        )
        await self._conn.commit()

    async def mark_unavailable(self, track: TrackInfo, reason: str) -> None:
        """PATCH-2026-07-20-136: tandai track sebagai permanen tidak
        tersedia (video dihapus/private/diblokir -- dikonfirmasi lewat
        VideoUnavailableError dari resolver) supaya CacheResolver.resolve()
        tidak lagi membuang request yt-dlp untuk video_id ini di masa
        depan (lihat Rule 0 di persistence/stream_cache.py).

        Pakai UPSERT (bukan UPDATE polos) karena baris untuk track ini
        belum tentu ada di DB -- kalau resolve gagal di percobaan PERTAMA
        (mis. lagu baru dari hasil pencarian yang belum pernah berhasil
        diputar), upsert_track() juga belum pernah dipanggil untuknya."""
        ts = int(time.time())
        query = """
            INSERT INTO tracks (
                video_id, title, artist, duration, unavailable, unavailable_reason, last_played
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                unavailable=1,
                unavailable_reason=excluded.unavailable_reason
        """
        await self._conn.execute(
            query, (track.video_id, track.title, track.artist, track.duration, reason, ts)
        )
        await self._conn.commit()

    async def get_unavailable_reason(self, video_id: str) -> str | None:
        """Return alasan (pesan error asli) kalau track ini pernah ditandai
        unavailable, None kalau belum pernah/tidak ada di DB. None berarti
        "boleh dicoba" -- caller (CacheResolver) tidak perlu membedakan
        "belum pernah dicoba" vs "tidak pernah ditandai gagal"."""
        async with self._conn.execute(
            "SELECT unavailable, unavailable_reason FROM tracks WHERE video_id = ?",
            (video_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row and row["unavailable"]:
                return row["unavailable_reason"] or "tidak diketahui"
            return None
