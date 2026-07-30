"""
Module: engine.radio.engine

Purpose:
    Manages the state and playback progression for the radio mode feature.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.events
    - core.ports
    - core.state
    - engine.playback
    - engine.radio.artist_selector
    - engine.radio.radio_config
    - engine.radio.prefetcher

Subscribes to:
    None

Publishes:
    - LogMessageEvent
    - QueueUpdatedEvent

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import secrets
from typing import TYPE_CHECKING

import structlog

from core.events import LogMessageEvent, QueueUpdatedEvent
from core.log_categories import LC_RADIO
from core.log_context import bind_correlation
from core.ports import ArtistRepositoryPort, LibraryRepositoryPort, MediaExtractorPort
from core.state import AppState, PlayerStatus
from engine.radio.artist_selector import ArtistSelector
from engine.radio.prefetcher import RadioPrefetcher
from engine.radio.radio_config import ARTISTS_PER_BATCH, ARTISTS_QUICK, track_task

if TYPE_CHECKING:
    from engine.playback import PlaybackController

logger = structlog.get_logger(component="radio.engine")


class RadioMode:
    """
    Orchestrator radio: activate, deactivate, auto-next.
    """

    def __init__(
        self,
        ytdlp: MediaExtractorPort,
        state: AppState,
        artists: ArtistRepositoryPort | None = None,
        library: LibraryRepositoryPort | None = None,
    ):
        self.ytdlp = ytdlp
        self.state = state

        self.artist_selector = ArtistSelector(artists, library, state)
        self.prefetcher = RadioPrefetcher(state, self.artist_selector)

        self._bg_tasks: set = set()

    # ── lifecycle ─────────────────────────────────────────────

    async def on_activated(self, controller: "PlaybackController") -> None:
        try:
            await self.artist_selector.ensure_artists_loaded()
        except RuntimeError as e:
            await controller.bus.publish(LogMessageEvent(message=f"Radio: {e}"))
            return
        self.state.radio_queue.clear()
        self.artist_selector.reset_rotation()
        # L5.3: correlation_id baru untuk siklus radio ini, diwariskan
        # eksplisit ke _start() dan seterusnya ke prefetcher.py saat
        # prefetch dijadwalkan sebagai task terpisah (anti-pattern §12.9 --
        # bukan di-generate ulang di titik yang lebih dalam).
        correlation_id = secrets.token_hex(4)
        bind_correlation(correlation_id)
        track_task(self._bg_tasks, self._start(controller, correlation_id), name="radio_start")

    async def on_deactivated(self) -> None:
        self.state.radio_queue.clear()
        for task in list(self._bg_tasks):
            task.cancel()
        self._bg_tasks.clear()
        self.prefetcher.cancel_tasks()
        # Jangan buang _standby — bisa dipakai kalau radio dinyalakan lagi

    # ── next (dipanggil saat track habis) ─────────────────────

    async def next(self, controller: "PlaybackController") -> None:
        # L5.3: correlation_id baru untuk siklus radio ini (satu track
        # berakhir -> satu siklus next). Dibind di awal supaya kedua cabang
        # di bawah (ensure_standby maupun refill via _start) mewarisi id
        # yang sama, bukan generate ulang di titik yang lebih dalam.
        correlation_id = secrets.token_hex(4)
        bind_correlation(correlation_id)
        if self.state.radio_queue:
            track = self.state.radio_queue.popleft()
            # Kalau queue mulai tipis, pastikan standby sedang disiapkan
            if len(self.state.radio_queue) <= 5:
                track_task(
                    self._bg_tasks,
                    self.prefetcher.ensure_standby(controller, correlation_id),
                    name="radio_ensure_standby",
                )
            await controller.play_track(track)
        else:
            self.state.status = PlayerStatus.LOADING
            await controller.bus.publish(QueueUpdatedEvent())
            track_task(self._bg_tasks, self._start(controller, correlation_id), name="radio_refill")

    # ── inti: start dengan standby atau fetch cepat ───────────

    async def _start(
        self, controller: "PlaybackController", correlation_id: str | None = None
    ) -> None:
        """
        Urutan prioritas:
        1. Standby sudah ada → pakai langsung (instan)
        2. Belum ada → fetch cepat ARTISTS_QUICK artis, putar segera,
           lalu background fetch sisa untuk genapi dan isi standby berikutnya

        L5.3: correlation_id diwariskan dari titik mulai siklus radio
        (on_activated()/next()) yang menjadwalkan _start() sebagai task
        terpisah -- dibind ulang di sini secara eksplisit (bukan dibuat
        baru) supaya jelas terlihat di titik masuk task ini juga.
        """
        if correlation_id:
            bind_correlation(correlation_id)

        # L7.2: entry/exit siklus radio (G6). candidates_in = jumlah track
        # yang didapat siklus ini, candidates_out = jumlah yang benar-benar
        # masuk ke radio_queue (candidates_in minus 1 yang langsung diputar).
        logger.info("radio_cycle_started", category=LC_RADIO)

        tracks = await self.prefetcher.pop_standby()

        if tracks:
            # Langsung pakai standby
            self.state.radio_queue.clear()
            self.state.radio_queue.extend(tracks[1:])
            await controller.bus.publish(QueueUpdatedEvent())
            await controller.play_track(tracks[0])
            logger.info(
                "radio_cycle_completed",
                category=LC_RADIO,
                candidates_in=len(tracks),
                candidates_out=len(tracks[1:]),
            )
            # Siapkan standby berikutnya di background
            self.prefetcher.trigger_build_standby(controller, correlation_id)
            return

        # Fetch cepat: ARTISTS_QUICK artis dulu, langsung putar
        try:
            quick_tracks = await asyncio.wait_for(
                self.artist_selector.gather_batch(max_artists=ARTISTS_QUICK), timeout=20.0
            )
        except RuntimeError as e:
            # DB artists kosong — kirim pesan jelas ke frontend
            logger.error(
                "radio_cycle_failed",
                category=LC_RADIO,
                reason="no_artists",
            )
            await controller.bus.publish(QueueUpdatedEvent())
            await controller.bus.publish(LogMessageEvent(message=f"Radio: {e}"))
            return
        except (TimeoutError, Exception):
            quick_tracks = []

        if quick_tracks:
            self.state.radio_queue.clear()
            self.state.radio_queue.extend(quick_tracks[1:])
            await controller.bus.publish(QueueUpdatedEvent())
            await controller.play_track(quick_tracks[0])
            logger.info(
                "radio_cycle_completed",
                category=LC_RADIO,
                candidates_in=len(quick_tracks),
                candidates_out=len(quick_tracks[1:]),
            )
            # Background: fetch sisa artis dan masukkan ke queue + siapkan standby
            track_task(
                self._bg_tasks,
                self._backfill_and_standby(controller, correlation_id),
                name="radio_backfill",
            )
        else:
            # Broadcast state ulang agar frontend tidak stuck di "loading" tanpa info
            logger.error(
                "radio_cycle_failed",
                category=LC_RADIO,
                reason="no_results",
            )
            await controller.bus.publish(QueueUpdatedEvent())
            await controller.bus.publish(
                LogMessageEvent(message="Radio: Tidak ada hasil ditemukan.")
            )

    async def _backfill_and_standby(
        self, controller: "PlaybackController", correlation_id: str | None = None
    ) -> None:
        """Fetch sisa artis (ARTISTS_PER_BATCH - ARTISTS_QUICK) lalu
        tambahkan ke queue yang sedang berjalan. Setelah itu siapkan standby.

        L5.3: correlation_id diwariskan dari _start() yang menjadwalkan
        task ini -- dibind ulang secara eksplisit di titik masuk task
        terpisah ini, dan diteruskan lagi ke prefetcher.py."""
        if correlation_id:
            bind_correlation(correlation_id)
        extra = await self.prefetcher.fetch_batch_with_lock(
            max_artists=ARTISTS_PER_BATCH - ARTISTS_QUICK, correlation_id=correlation_id
        )
        if extra:
            self.state.radio_queue.extend(extra)
            while len(self.state.radio_queue) > 30:
                self.state.radio_queue.pop()
            await controller.bus.publish(QueueUpdatedEvent())

        # Setelah backfill selesai, langsung siapkan standby berikutnya
        self.prefetcher.trigger_build_standby(controller, correlation_id)

    # ── dipanggil dari playback_controller saat tombol Acak ───

    async def _fetch_and_play_initial(
        self, controller: "PlaybackController", seed_artist: str | None = None
    ) -> None:
        # L5.3: siklus radio baru (tombol Acak) -- correlation_id sendiri,
        # terpisah dari on_activated()/next().
        correlation_id = secrets.token_hex(4)
        bind_correlation(correlation_id)
        self.artist_selector.reset_rotation()
        await self.prefetcher.async_clear_standby()

        await controller.bus.publish(LogMessageEvent(message="Mengacak playlist radio..."))

        try:
            tracks = await asyncio.wait_for(
                self.artist_selector.gather_batch(
                    prioritized_artist=seed_artist, max_artists=ARTISTS_PER_BATCH
                ),
                timeout=40.0,
            )
        except RuntimeError as e:
            await controller.bus.publish(LogMessageEvent(message=f"Radio: {e}"))
            return
        except TimeoutError:
            await controller.bus.publish(
                LogMessageEvent(message="Radio: Timeout saat mengambil lagu. Coba lagi.")
            )
            return
        except Exception as e:
            logger.warning(
                "radio_randomize_failed",
                category=LC_RADIO,
                error_type=type(e).__name__,
                error=str(e),
            )
            return

        if not tracks:
            await controller.bus.publish(
                LogMessageEvent(message="Radio: Tidak ada hasil ditemukan.")
            )
            return

        self.state.radio_queue.clear()
        self.state.radio_queue.extend(tracks[1:])
        await controller.bus.publish(QueueUpdatedEvent())
        await controller.play_track(tracks[0])

        # Siapkan standby berikutnya di background untuk auto-refill
        self.prefetcher.trigger_build_standby(controller, correlation_id)

    def check_prefetch(
        self, controller: "PlaybackController", position: float, duration: float
    ) -> None:
        self.prefetcher.check_prefetch(controller, position, duration)
