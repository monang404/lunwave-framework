"""
Module: engine.radio.prefetcher

Purpose:
    Pre-fetches tracks asynchronously to ensure seamless transitions in radio mode.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.state
    - engine.playback
    - engine.radio.artist_selector
    - engine.radio.radio_config

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
from typing import TYPE_CHECKING

import structlog

from config import (
    PREFETCH_DEFAULT_THRESHOLD_SEC,
    PREFETCH_MAX_THRESHOLD_SEC,
    PREFETCH_MIN_THRESHOLD_SEC,
    PREFETCH_SAFETY_FACTOR,
)
from core.log_categories import LC_RADIO
from core.log_context import bind_correlation
from core.state import AppState
from engine.radio.radio_config import ARTISTS_PER_BATCH, RADIO_SEARCH_SEM, track_task

if TYPE_CHECKING:
    from engine.playback import PlaybackController
    from engine.radio.artist_selector import ArtistSelector

logger = structlog.get_logger(component="radio.prefetcher")


class RadioPrefetcher:
    """Standby queue, prefetch background task."""

    PREFETCH_LOOKAHEAD = 3  # jumlah lagu ke depan yang di-prefetch sekaligus

    def __init__(self, state: AppState, artist_selector: "ArtistSelector"):
        self.state = state
        self.artist_selector = artist_selector
        self._standby: list = []
        self._standby_lock = asyncio.Lock()
        self._fetch_lock = asyncio.Lock()
        self._bg_tasks: set = set()
        self._last_prefetch_vid: str | None = None

    def cancel_tasks(self):
        for task in list(self._bg_tasks):
            task.cancel()
        self._bg_tasks.clear()

    async def pop_standby(self) -> list | None:
        async with self._standby_lock:
            if self._standby:
                tracks = self._standby
                self._standby = []
                return tracks
            return None

    async def async_clear_standby(self):
        async with self._standby_lock:
            self._standby = []

    async def ensure_standby(
        self, controller: "PlaybackController", correlation_id: str | None = None
    ) -> None:
        """Pastikan standby sedang disiapkan kalau belum ada.

        L5.3: correlation_id (jika ada) diwariskan dari siklus radio yang
        memicu pemanggilan ini (engine/radio/engine.py) -- diteruskan
        eksplisit ke build_standby(), TIDAK di-generate ulang di sini
        (anti-pattern §12.9)."""
        async with self._standby_lock:
            if self._standby:
                return
        track_task(
            self._bg_tasks,
            self.build_standby(controller, correlation_id),
            name="radio_build_standby2",
        )

    async def build_standby(
        self, controller: "PlaybackController", correlation_id: str | None = None
    ) -> None:
        """Siapkan playlist cadangan 12 lagu di background.
        Tidak akan jalan kalau standby sudah ada atau sedang dibangun.

        L5.3: bind_correlation(correlation_id) di titik masuk task
        terpisah ini (dijadwalkan via asyncio.create_task/track_task)
        supaya log build_standby memakai correlation_id yang identik
        dengan siklus radio yang memicunya, bukan id baru."""
        if correlation_id:
            bind_correlation(correlation_id)
        async with self._standby_lock:
            if self._standby:
                return  # sudah ada, tidak perlu rebuild

        async with self._fetch_lock:
            async with self._standby_lock:
                if self._standby:
                    return  # sudah ada, menghindari gather_batch redundant

            try:
                tracks = await asyncio.wait_for(
                    self.artist_selector.gather_batch(max_artists=ARTISTS_PER_BATCH), timeout=30.0
                )
                if tracks:
                    async with self._standby_lock:
                        self._standby = tracks
            except Exception as e:
                logger.warning(
                    "radio_build_standby_failed",
                    category=LC_RADIO,
                    error_type=type(e).__name__,
                    error=str(e),
                )

    def trigger_build_standby(
        self, controller: "PlaybackController", correlation_id: str | None = None
    ):
        track_task(
            self._bg_tasks,
            self.build_standby(controller, correlation_id),
            name="radio_build_standby",
        )

    def _current_threshold(self, controller: "PlaybackController") -> float:
        window = controller.track_loader.resolver.latency_window
        p90 = window.percentile(90, default=PREFETCH_DEFAULT_THRESHOLD_SEC)
        raw = p90 * PREFETCH_SAFETY_FACTOR
        return max(PREFETCH_MIN_THRESHOLD_SEC, min(raw, PREFETCH_MAX_THRESHOLD_SEC))

    def check_prefetch(
        self, controller: "PlaybackController", position: float, duration: float
    ) -> None:
        """Trigger prefetch stream_url untuk lagu berikutnya jika waktu tersisa <= threshold adaptif."""
        threshold = self._current_threshold(controller)
        if duration > 0 and (duration - position) <= threshold:
            current_vid = self.state.current_track.video_id if self.state.current_track else None
            if current_vid and self._last_prefetch_vid != current_vid:
                self._last_prefetch_vid = current_vid
                track_task(self._bg_tasks, self._prefetch_next(controller), name="radio_prefetch")

    async def _prefetch_next(self, controller: "PlaybackController") -> None:
        """Resolve stream_url untuk lagu pertama di radio_queue secara background."""
        try:
            await asyncio.wait_for(self._do_prefetch(controller), timeout=25.0)
        except Exception as e:
            logger.warning(
                "radio_prefetch_next_failed",
                category=LC_RADIO,
                error_type=type(e).__name__,
                error=str(e),
            )

    async def _do_prefetch(self, controller: "PlaybackController") -> None:
        if not self.state.radio_queue:
            return

        candidates = [
            t for t in list(self.state.radio_queue)[: self.PREFETCH_LOOKAHEAD] if not t.stream_url
        ]
        if not candidates:
            return

        async def _resolve_one(track):
            async with RADIO_SEARCH_SEM:
                try:
                    await controller.track_loader.resolver.resolve(track)
                    logger.info(
                        "radio_prefetch_resolved",
                        category=LC_RADIO,
                        video_id=track.video_id,
                    )
                except Exception:
                    # L8.1 (G8): exception ini sudah dicatat sebagai
                    # stream_resolve_failed (ERROR, video_id/error_type/error)
                    # oleh adapters/ytdlp/resolver.py di titik asal -- tidak ada
                    # field baru yang ditambahkan di sini (video_id/error_type/
                    # error identik), jadi diamkan (§12.5 / L-D4). Prefetch
                    # bersifat best-effort: kegagalan di sini tidak menghentikan
                    # kandidat lain di asyncio.gather.
                    pass

        await asyncio.gather(*[_resolve_one(t) for t in candidates])

    # Method proxy agar RadioMode bisa mendelegasikan fetch and lock
    async def fetch_batch_with_lock(
        self,
        prioritized_artist: str | None = None,
        max_artists: int = ARTISTS_PER_BATCH,
        correlation_id: str | None = None,
    ):
        if self._fetch_lock.locked():
            return []
        if correlation_id:
            bind_correlation(correlation_id)
        async with self._fetch_lock:
            try:
                return await asyncio.wait_for(
                    self.artist_selector.gather_batch(
                        prioritized_artist=prioritized_artist, max_artists=max_artists
                    ),
                    timeout=30.0,
                )
            except Exception as e:
                logger.warning(
                    "radio_fetch_batch_failed",
                    category=LC_RADIO,
                    error_type=type(e).__name__,
                    error=str(e),
                )
                return []
