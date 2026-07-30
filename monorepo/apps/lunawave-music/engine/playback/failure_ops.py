"""
Module: engine.playback.failure_ops

Purpose:
    Menangani semua cabang except dari play_track() saat gagal memutar
    sebuah track (video tidak tersedia permanen, bot-check/rate-limit
    YouTube, atau error generik lainnya). Diekstrak dari controller.py
    (PATCH-2026-07-20-136) agar file controller tetap ramping (di bawah
    LARGE_FILE_THRESHOLD 500 LOC), sama seperti track_ended_ops.py.

Responsibilities:
    - VideoUnavailableError: tandai video permanen tidak tersedia di DB
      (mark_unavailable) dan skip ke track berikutnya TANPA backoff --
      retry pada video yang sama tidak akan pernah berhasil.
    - BotCheckError/RateLimitedError: video ini sudah gagal walau resolver
      sendiri sudah mencoba client fallback (bot-check) -- catat error yang
      jelas, tetap lewat backoff yang sama seperti error generik.
    - Exception generik lain: log + backoff naik sebelum lanjut ke track
      berikutnya, seperti perilaku asli sebelum patch ini.
    - `advance_after_track_failure`: titik tunggal setelah play_track
      menyerah pada satu track. `controller._breaker` (PlaybackCircuitBreaker,
      lihat engine.playback.circuit_breaker) di sini BUKAN retry pada track
      yang sama (play_track tidak pernah dipanggil ulang untuk track yang
      sama dari sini) -- ia melacak berapa kali BERTURUT-TURUT play_track
      gagal untuk track MANAPUN, dan berfungsi sebagai circuit breaker
      lintas-track: begitu mencapai 3x beruntun, auto-advance dihentikan
      sama sekali supaya kegagalan sistemik (internet mati, YouTube
      rate-limit global) tidak diam-diam menghabiskan seluruh queue dalam
      hitungan detik. Direset ke CLOSED begitu ada satu track yang berhasil
      play, atau saat _on_stop -- termasuk segera setelah breaker baru saja
      OPEN (lihat advance_after_track_failure), supaya round kegagalan
      berikutnya mulai dari hitungan 0 lagi, identik dengan perilaku
      counter lama yang digantikannya.

Depends on:
    - core.events, core.state, core.task_utils

Subscribes to:
    None (dipanggil langsung oleh PlaybackController.play_track)

Publishes:
    LogMessageEvent (via callback bus milik controller)

Thread Safety:
    Main thread (async event loop).
"""

import asyncio

import structlog

from core.events import LogMessageEvent
from core.log_categories import LC_PLAYBACK
from core.state import PlayerStatus, TrackInfo
from core.task_utils import safe_create_task

logger = structlog.get_logger(component="playback.failure_ops")


class FailureOps:
    """Operasi reaksi terhadap kegagalan play_track(). Dipanggil oleh
    PlaybackController -- lihat controller.py untuk pemanggilnya."""

    def __init__(self, controller):
        self.c = controller

    async def handle_video_unavailable(self, track: TrackInfo, e: Exception) -> None:
        c = self.c
        c._loading = False
        logger.warning(
            "track_permanently_unavailable",
            category=LC_PLAYBACK,
            video_id=track.video_id,
            reason=str(e),
        )
        c.state.status = PlayerStatus.ERROR
        c.state.error_msg = f"Lagu tidak tersedia: {track.title}"
        safe_create_task(
            c.resolver.db.mark_unavailable(track, str(e)),
            name=f"mark_unavailable_{track.video_id}",
        )
        await c.bus.publish(
            LogMessageEvent(
                message=f"Lagu tidak tersedia (dihapus/private): {track.title} — dilewati"
            )
        )
        await self.advance_after_track_failure(track, backoff=False)

    async def handle_bot_check_or_rate_limited(self, track: TrackInfo, e: Exception) -> None:
        c = self.c
        c._loading = False
        # L8.1 (G8/L-D4): field baru vs stream_resolve_failed resolver.py --
        # consecutive_failures (state circuit-breaker cross-track yang hanya
        # diketahui di sini, bukan di resolver.py) menjustifikasi log ulang
        # di boundary playback ini (§11.4: titik final paling informatif).
        logger.error(
            "track_play_failed",
            category=LC_PLAYBACK,
            video_id=track.video_id,
            error_type=type(e).__name__,
            error=str(e),
            consecutive_failures=c._breaker._consecutive_failures + 1,
        )
        c.state.status = PlayerStatus.ERROR
        c.state.error_msg = str(e)
        await c.bus.publish(LogMessageEvent(message=f"{type(e).__name__}: {track.title} — {e}"))
        await self.advance_after_track_failure(track, backoff=True)

    async def handle_generic_error(self, track: TrackInfo, e: Exception) -> None:
        c = self.c
        c._loading = False  # RC-TERMUX-01: clear flag jika error
        # L8.1 (G8/L-D4): consecutive_failures = field baru yang tidak
        # diketahui resolver.py, menjustifikasi log ulang di boundary ini.
        logger.error(
            "track_play_failed",
            category=LC_PLAYBACK,
            video_id=track.video_id,
            error_type=type(e).__name__,
            error=str(e),
            exc_info=True,
            consecutive_failures=c._breaker._consecutive_failures + 1,
        )
        c.state.status = PlayerStatus.ERROR
        c.state.error_msg = f"Error: {e}"
        await c.bus.publish(
            LogMessageEvent(
                message=f"Gagal memutar lagu: {track.title} | {type(e).__name__}: {str(e)}"
            )
        )
        await self.advance_after_track_failure(track, backoff=True)

    async def advance_after_track_failure(self, track: TrackInfo, backoff: bool) -> None:
        c = self.c
        just_tripped = c._breaker.record_failure()
        if just_tripped:
            # Reset segera (bukan biarkan OPEN permanen) -- identik dengan
            # perilaku lama (reset counter ke 0) setelah menyentuh threshold:
            # round kegagalan berikutnya mulai dari hitungan 0 lagi.
            c._breaker.record_success()
            await c.bus.publish(
                LogMessageEvent(
                    message="Beberapa lagu berbeda berturut-turut gagal diputar. "
                    "Pemutaran dihentikan -- cek koneksi internet, atau coba lagi nanti "
                    "kalau ini karena YouTube membatasi sementara."
                )
            )
            return

        if backoff:
            await asyncio.sleep(2**c._breaker._consecutive_failures)

        # Ensure we don't call _on_next if we are no longer trying to play this track
        if c.state.current_track == track:
            safe_create_task(c._advance_to_next(), name=f"advance_after_failure_{track.video_id}")
