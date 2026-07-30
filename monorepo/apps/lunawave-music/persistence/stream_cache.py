"""
Module: persistence.stream_cache

Purpose:
    Resolve the playback URI for a track using a priority-based cache
    strategy: local file > cached stream URL > fresh yt-dlp extraction.

Responsibilities:
    - Check DB for a valid local path or a non-stale stream URL.
    - Fetch a fresh stream URL via yt-dlp on cache miss and persist it.

Depends on:
    - core.ports
    - core.state

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (async).
"""

import os
import time
from typing import Any

import structlog

from config import STREAM_URL_TTL_SEC
from core.exceptions import VideoUnavailableError
from core.latency_window import LatencyWindow
from core.observability import RESOLVE_LATENCY
from core.ports import DatabasePort, MediaExtractorPort
from core.state import TrackInfo

logger = structlog.get_logger(component="persistence.stream_cache")


class ResolverDbCompat:
    """Kompatibilitas untuk `resolver.db` pasca T2.2e (facade `Database`
    dihapus). `CacheResolver` sendiri cuma perlu `get_track`/`upsert_track`
    (TrackRepositoryPort), tapi kode lain yang mengakses `resolver.db` --
    `PlaybackController`, `TrackLoader`, `track_ended_ops`,
    `event_listeners` -- juga memanggil method artist (`record_completion`,
    `record_skip`) dan atribut `.discover`. Ini BUKAN facade baru: tidak ada
    logic sendiri, cuma menggabungkan repo yang sudah ada supaya
    `resolver.db.xxx` tetap bisa dipanggil dari satu tempat tanpa harus
    menembus PlaybackController/TrackLoader untuk inject 3 repo terpisah."""

    def __init__(self, tracks, artists, discover):
        self._tracks = tracks
        self._artists = artists
        self.discover = discover

    async def get_track(self, *a, **kw):
        return await self._tracks.get_track(*a, **kw)

    async def upsert_track(self, *a, **kw):
        return await self._tracks.upsert_track(*a, **kw)

    async def increment_play_count(self, *a, **kw):
        return await self._tracks.increment_play_count(*a, **kw)

    async def set_last_position(self, *a, **kw):
        return await self._tracks.set_last_position(*a, **kw)

    async def record_completion(self, *a, **kw):
        return await self._artists.record_completion(*a, **kw)

    async def record_skip(self, *a, **kw):
        return await self._artists.record_skip(*a, **kw)

    async def mark_unavailable(self, *a, **kw):
        return await self._tracks.mark_unavailable(*a, **kw)

    async def get_unavailable_reason(self, *a, **kw):
        return await self._tracks.get_unavailable_reason(*a, **kw)


class CacheResolver:
    """
    Priority Rules:
    1. Local file exists -> return local_path
    2. Stream URL is fresh -> return stream_url
    3. Stale -> fetch new stream URL from yt-dlp, save to DB, return it
    """

    def __init__(self, db: "DatabasePort | Any", ytdlp: MediaExtractorPort):
        self.db = db
        self.ytdlp = ytdlp
        self.latency_window = LatencyWindow()

    async def resolve(self, track: TrackInfo) -> str:
        """Returns the playback URI (local path atau YouTube URL untuk MPV)."""
        # Rule 0: PATCH-2026-07-20-136 -- video ini sudah pernah dikonfirmasi
        # dihapus/private/diblokir permanen (VideoUnavailableError). Jangan
        # buang request yt-dlp lagi untuk video_id yang sudah terbukti mati;
        # gagal cepat supaya PlaybackController langsung skip tanpa nunggu
        # timeout resolve (YTDLP_RESOLVE_TIMEOUT_SEC detik) percuma.
        reason = await self.db.get_unavailable_reason(track.video_id)
        if reason:
            raise VideoUnavailableError(
                f"{track.title} sebelumnya sudah ditandai tidak tersedia: {reason}"
            )

        row = await self.db.get_track(track.video_id)

        # Rule 1: Local file — ini yang benar-benar berguna
        if row and row.local_path:
            path = row.local_path
            import asyncio

            if await asyncio.to_thread(os.path.isfile, path):
                track.local_path = path
                return path

        # Rule 2: Gunakan stream_url dari cache jika belum kadaluwarsa
        if row and row.stream_url and row.stream_url_ts:
            ts = row.stream_url_ts
            if time.time() - ts < STREAM_URL_TTL_SEC:
                track.stream_url = row.stream_url
                return track.stream_url

        # Rule 3: Ambil direct URL dari yt-dlp
        t0 = time.monotonic()
        url = await self.ytdlp.get_stream_url(track.video_id)
        duration = time.monotonic() - t0
        self.latency_window.record(duration)
        RESOLVE_LATENCY.observe(duration)

        track.stream_url = url
        # Simpan metadata track ke DB
        await self.db.upsert_track(track, stream_url=url)
        return url  # type: ignore
