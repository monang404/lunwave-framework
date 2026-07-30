"""
Module: engine.playback.mode_ops

Purpose:
    Handles playback mode switches, such as toggling radio mode or SponsorBlock.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.events
    - core.ports
    - core.state
    - engine.radio

Subscribes to:
    None

Publishes:
    - LogMessageEvent
    - QueueUpdatedEvent

Thread Safety:
    Main thread (async event loop).
"""

import asyncio

import structlog

from core.events import LogMessageEvent, QueueUpdatedEvent
from core.log_categories import LC_PLAYBACK
from core.ports import AudioPlayerPort
from core.state import AppState, AudioOutput, PlaybackMode, PlayerStatus
from engine.radio import RadioMode

logger = structlog.get_logger(component="playback.mode_ops")


class ModeOps:
    """
    Operasi konfigurasi mode, output, dan sponsorblock.
    Dipanggil oleh PlaybackController.
    """

    def __init__(
        self, state: AppState, bus, lock: asyncio.Lock, mpv: AudioPlayerPort, radio_mode: RadioMode
    ):
        self.state = state
        self.bus = bus
        self._lock = lock
        self.mpv = mpv
        self.radio_mode = radio_mode

    async def set_mode(self, mode: PlaybackMode) -> bool:
        """Mengatur mode playback. Mengembalikan True jika radio mode harus diaktifkan."""
        should_activate_radio = False
        async with self._lock:
            if self.state.playback_mode != mode:
                previous_mode = self.state.playback_mode
                self.state.playback_mode = mode

                if previous_mode == PlaybackMode.RADIO:
                    await self.radio_mode.on_deactivated()
                    await self.mpv.pause()
                    self.state.current_track = None
                    self.state.status = PlayerStatus.IDLE

                if mode == PlaybackMode.RADIO:
                    self.state.status = PlayerStatus.LOADING
                    should_activate_radio = True

                logger.info(
                    "playback_mode_changed",
                    category=LC_PLAYBACK,
                    mode_baru=mode.name,
                )
                await self.bus.publish(LogMessageEvent(message=f"Mode diubah ke {mode.name}"))
                await self.bus.publish(QueueUpdatedEvent())

        return should_activate_radio

    async def randomize_radio(self, data: dict | None) -> tuple[bool, str | None]:
        """Mengacak ulang radio. Mengembalikan tuple (should_fetch, seed_artist)."""
        seed = None
        should_fetch = False
        async with self._lock:
            if self.state.playback_mode == PlaybackMode.RADIO:
                seed = data.get("seed_artist") if data else None
                self.state.radio_queue.clear()
                await self.mpv.pause()
                self.state.current_track = None
                self.state.status = PlayerStatus.LOADING
                self.state.position = 0.0
                if hasattr(self.radio_mode, "artist_selector"):
                    self.radio_mode.artist_selector.reset_rotation()
                else:
                    self.radio_mode._artist_rotation = []  # type: ignore
                await self.bus.publish(QueueUpdatedEvent())
                await self.bus.publish(LogMessageEvent(message="Mengacak ulang stasiun radio..."))
                should_fetch = True
            else:
                await self.bus.publish(LogMessageEvent(message="Radio tidak aktif"))

        return should_fetch, seed

    async def set_output(self, output: AudioOutput):
        self.state.audio_output = output
        if self.state.audio_output == AudioOutput.BROWSER:
            await self.mpv.set_volume(0)
        else:
            await self.mpv.set_volume(self.state.volume)

        msg = "Browser" if self.state.audio_output == AudioOutput.BROWSER else "HP"
        await self.bus.publish(LogMessageEvent(message=f"Output suara diubah ke: {msg}"))
        await self.bus.publish(QueueUpdatedEvent())

    async def set_speed(self, data: dict):
        speed = data.get("speed", 1.0)
        self.state.playback_speed = float(speed)
        await self.mpv.set_property("speed", self.state.playback_speed)
        await self.bus.publish(LogMessageEvent(message=f"Kecepatan pemutaran diubah ke {speed}x"))

    async def set_loop(self, data: dict):
        mode = data.get("mode", "off")
        if mode in ["off", "track", "queue"]:
            self.state.loop_mode = mode
            msg_map = {"off": "Mati", "track": "Ulangi Lagu", "queue": "Ulangi Antrean"}
            await self.bus.publish(LogMessageEvent(message=f"Mode Loop: {msg_map[mode]}"))
            from core.events import QueueUpdatedEvent

            await self.bus.publish(QueueUpdatedEvent())

    async def toggle_sponsorblock(self, enabled: bool):
        self.state.sponsorblock_active = enabled
        status_msg = "ON" if enabled else "OFF"
        await self.bus.publish(LogMessageEvent(message=f"SponsorBlock: {status_msg}"))
        await self.bus.publish(QueueUpdatedEvent())

    async def toggle_loudness_normalization(self, enabled: bool):
        self.state.loudness_normalization_enabled = enabled
        logger.info(
            "loudness_normalization_changed",
            category=LC_PLAYBACK,
            enabled=enabled,
        )

        # BUGFIX: sebelumnya toggle ini cuma ganti state, tidak pernah manggil mpv.set_af().
        # Filter gain cuma di-apply ulang di play_track() (saat load lagu baru), jadi UI
        # keliatan ON/OFF tapi audio tidak berubah sampai lagu berikutnya. Kalau ada track
        # yang sedang berjalan, re-apply `af` filter sekarang juga memakai gain_db yang
        # sudah dihitung untuk track itu (disimpan di state.current_track_gain_db saat load).
        if self.state.current_track is not None:
            from engine.loudness.gain_calculator import build_af_filter

            gain_db = self.state.current_track_gain_db if enabled else 0.0
            await self.mpv.set_af(build_af_filter(gain_db))

        status_msg = "ON" if enabled else "OFF"
        await self.bus.publish(LogMessageEvent(message=f"Loudness Normalization: {status_msg}"))
        await self.bus.publish(QueueUpdatedEvent())

    async def set_crossfade(self, data: dict):
        enabled = data.get("enabled", False)
        self.state.crossfade_enabled = enabled
        logger.info(
            "crossfade_changed",
            category=LC_PLAYBACK,
            enabled=enabled,
        )
        status_msg = "ON" if enabled else "OFF"
        await self.bus.publish(LogMessageEvent(message=f"Crossfade: {status_msg}"))
        await self.bus.publish(QueueUpdatedEvent())
