"""
Module: engine.playback.settings_controller

Purpose:
    Menangani command CMD_SET_OUTPUT, CMD_SET_SPONSORBLOCK,
    CMD_SET_LOUDNESS_NORMALIZATION, CMD_SET_MODE, CMD_RADIO_RANDOMIZE, dan
    CMD_LYRICS_OFFSET. Diekstrak dari PlaybackController (roadmap
    IMPLEMENTATION_PLAN.md §2.3, task T2.3.2) agar controller.py tetap
    ramping.

Responsibilities:
    - Delegasi perubahan mode/output/sponsorblock/loudness ke ModeOps.
    - Aktivasi radio_mode saat CMD_SET_MODE pindah ke RADIO.
    - Trigger fetch awal radio saat CMD_RADIO_RANDOMIZE.
    - Update lyrics_offset di state dan publish LyricsUpdatedEvent.

Depends on:
    - core.events, core.state, core.task_utils

Subscribes to:
    None (dipanggil langsung oleh PlaybackController / CommandRouter)

Publishes:
    - LyricsUpdatedEvent (langsung); LogMessageEvent/QueueUpdatedEvent
      (via ModeOps yang dipanggil)

Thread Safety:
    Main thread (async event loop).
"""

from core.state import AudioOutput, PlaybackMode
from core.task_utils import safe_create_task


class SettingsController:
    """
    Operasi command pengaturan mode/output/sponsorblock/loudness/lyrics.
    Dipanggil oleh PlaybackController.
    """

    def __init__(self, controller):
        # Simpan referensi controller (pola sama seperti TrackEndedOps) karena
        # method di sini butuh akses ke banyak state controller: self.state,
        # self.bus, self._mode_ops, self.radio_mode.
        self.controller = controller

    async def on_set_mode(self, mode: PlaybackMode):
        c = self.controller
        should_activate_radio = await c._mode_ops.set_mode(mode)
        if should_activate_radio:
            await c.radio_mode.on_activated(c)

    async def on_radio_randomize(self, data=None):
        c = self.controller
        should_fetch, seed = await c._mode_ops.randomize_radio(data)
        if should_fetch:
            safe_create_task(
                c.radio_mode._fetch_and_play_initial(c, seed_artist=seed),
                name="radio_randomize_fetch",
            )

    async def on_set_output(self, output: AudioOutput):
        await self.controller._mode_ops.set_output(output)

    async def on_set_sponsorblock(self, enabled: bool):
        await self.controller._mode_ops.toggle_sponsorblock(enabled)

    async def on_set_loudness_normalization(self, enabled: bool):
        await self.controller._mode_ops.toggle_loudness_normalization(enabled)

    async def on_lyrics_offset(self, data: dict):
        c = self.controller
        offset = data.get("offset", 0.0)
        c.state.lyrics_offset = float(offset)
        from core.events import LyricsUpdatedEvent

        await c.bus.publish(LyricsUpdatedEvent())
