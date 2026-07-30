"""
Module: engine.playback.track_ended_ops

Purpose:
    Menangani reaksi terhadap TrackEndedEvent (eof/stop/error) dan polling
    durasi track yang belum diketahui. Diekstrak dari controller.py agar
    file controller tetap ramping (di bawah LARGE_FILE_THRESHOLD).

Responsibilities:
    - Reaksi terhadap reason == "eof" | "stop" | "error" dari TrackEndedEvent.
    - Grace-window guard untuk event 'stop' basi yang datang saat transisi
      track sedang berlangsung, tanpa membiarkan status nyangkut di PLAYING
      kalau memang tidak ada transisi baru yang menyusul.
    - Polling durasi track secara aktif kalau belum tersedia dari mpv.

Depends on:
    - core.events, core.state, core.task_utils

Subscribes to:
    None (dipanggil langsung oleh PlaybackController)

Publishes:
    - LogMessageEvent, QueueUpdatedEvent (via callback bus milik controller)

Thread Safety:
    Main thread (async event loop).
"""

import asyncio

import structlog

from core.events import LogMessageEvent, QueueUpdatedEvent, TrackEndedEvent
from core.log_categories import LC_PLAYBACK
from core.state import AppState, PlayerStatus, TrackInfo
from core.task_utils import safe_create_task

logger = structlog.get_logger(component="playback.track_ended_ops")

# Grace period untuk membedakan event 'stop' basi (dari track lama, akibat
# transisi mpv.play() yang internally stop dulu track lama) dengan stop asli
# (mpv benar-benar berhenti tanpa ada track baru yang menyusul).
GRACE_WINDOW_SECONDS = 1.0


class TrackEndedOps:
    """
    Operasi reaksi terhadap TrackEndedEvent. Dipanggil oleh PlaybackController.
    """

    def __init__(self, controller):
        # Simpan referensi controller (bukan field individual) karena method
        # di sini butuh akses ke banyak state controller: self.state, self.bus,
        # self._loading, self._last_play_start_ts, self._on_next, self.mpv,
        # self.resolver, self._advance_to_next.
        self.controller = controller

    async def on_track_ended(self, event: TrackEndedEvent):
        c = self.controller
        reason = event.reason
        logger.info(
            "track_ended",
            category=LC_PLAYBACK,
            reason=reason,
        )

        # Build payload for next to prevent double-skip if track changes concurrently
        next_data = {}
        if c.state.current_track:
            next_data["video_id"] = c.state.current_track.video_id

        if reason == "eof":
            await asyncio.sleep(0.35)
            await c._on_next(next_data)
        elif reason == "stop":
            await self._handle_stop(next_data)
        elif reason == "error":
            await self._handle_error(next_data)

    async def _handle_stop(self, next_data: dict):
        c = self.controller
        if c._loading:
            logger.info("track_end_stop_ignored_during_transition", category=LC_PLAYBACK)
            return

        # RACE-FIX: event 'stop' dari mpv untuk track LAMA bisa nyampe telat
        # (setelah _loading sudah balik False) kalau device lambat, karena
        # mpv.play() ke track baru internally stop dulu track lama sebelum
        # load yang baru. Tanpa grace period, status bisa ke-overwrite jadi
        # IDLE padahal track baru sudah sukses PLAYING -> playback macet.
        #
        # Tapi asumsi "kalau masih PLAYING setelah sleep berarti stop ini basi"
        # tidak selalu benar: kalau mpv benar-benar stop tanpa ada track baru
        # yang menyusul, status tetap PLAYING selamanya (bug: stuck status).
        # Grace period hanya relevan kalau memang ADA transisi track yang baru
        # saja dimulai (play_track dipanggil belum lama) -- di luar window itu,
        # event 'stop' dianggap stop asli dan status langsung di-set IDLE.
        elapsed = asyncio.get_event_loop().time() - c._last_play_start_ts
        if elapsed <= GRACE_WINDOW_SECONDS:
            await asyncio.sleep(0.35)
            if c.state.status == PlayerStatus.PLAYING:
                logger.info("track_end_stop_ignored_stale", category=LC_PLAYBACK)
                return
        if c.state.status not in (PlayerStatus.IDLE,):
            c.state.status = PlayerStatus.IDLE

    async def _handle_error(self, next_data: dict):
        c = self.controller
        c.state.status = PlayerStatus.ERROR
        await c.bus.publish(LogMessageEvent(message="Terjadi kesalahan pemutaran"))
        await asyncio.sleep(2)
        # Batalkan autoplay jika user sudah stop atau ganti lagu selama sleep
        if c.state.status == PlayerStatus.IDLE:
            return
        current_vid = getattr(c.state.current_track, "video_id", None)
        if next_data.get("video_id") and current_vid != next_data["video_id"]:
            return
        await c._on_next(next_data)


async def poll_duration(state: AppState, mpv, resolver, bus, track: TrackInfo):
    """Fetch durasi track secara aktif kalau belum tersedia dari mpv saat awal play."""
    for delay in [2, 5]:
        await asyncio.sleep(delay)
        if state.current_track != track:
            return
        dur = await mpv.get_duration()
        if dur > 0:
            state.duration = dur
            track.duration = int(dur)
            safe_create_task(resolver.db.upsert_track(track), name="upsert_duration")
            await bus.publish(QueueUpdatedEvent())
            return
