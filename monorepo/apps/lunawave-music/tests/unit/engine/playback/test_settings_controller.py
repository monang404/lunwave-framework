"""
Module: tests.unit.engine.playback.test_settings_controller

Purpose:
    Unit tests for SettingsController: command CMD_SET_MODE,
    CMD_RADIO_RANDOMIZE, CMD_SET_OUTPUT, CMD_SET_SPONSORBLOCK,
    CMD_SET_LOUDNESS_NORMALIZATION, CMD_LYRICS_OFFSET, diekstrak dari
    test_controller.py mengikuti pemisahan PlaybackController (T2.3.2)
    menjadi QueueController + SettingsController.

Responsibilities:
    - Verifikasi delegasi PlaybackController._on_set_* / _on_radio_randomize
      / _on_lyrics_offset ke SettingsController.
    - Verifikasi aktivasi radio_mode saat pindah ke PlaybackMode.RADIO.
    - Verifikasi trigger fetch awal saat CMD_RADIO_RANDOMIZE pada mode radio.

Depends on:
    - core.events
    - core.state
    - tests.unit.engine.conftest

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio

from core.events import LyricsUpdatedEvent
from core.state import AudioOutput, PlaybackMode


class TestSetMode:
    async def test_switch_to_radio_activates_radio_mode(self, controller, state, radio_mode):
        state.playback_mode = PlaybackMode.QUEUE
        await controller._on_set_mode(PlaybackMode.RADIO)
        assert radio_mode.activated is True

    async def test_switch_to_queue_does_not_activate_radio(self, controller, state, radio_mode):
        state.playback_mode = PlaybackMode.RADIO
        await controller._on_set_mode(PlaybackMode.QUEUE)
        assert radio_mode.activated is False

    async def test_same_mode_is_noop(self, controller, state, radio_mode):
        state.playback_mode = PlaybackMode.QUEUE
        await controller._on_set_mode(PlaybackMode.QUEUE)
        assert radio_mode.activated is False


class TestRadioRandomize:
    async def test_randomize_while_radio_active_triggers_fetch(self, controller, state, radio_mode):
        state.playback_mode = PlaybackMode.RADIO
        await controller._on_radio_randomize({"seed_artist": "Artist X"})
        await asyncio.sleep(0)
        assert radio_mode.fetch_initial_calls == ["Artist X"]

    async def test_randomize_while_not_radio_does_nothing(self, controller, state, radio_mode):
        state.playback_mode = PlaybackMode.QUEUE
        await controller._on_radio_randomize()
        await asyncio.sleep(0)
        assert radio_mode.fetch_initial_calls == []


class TestOutputSponsorblockLoudness:
    async def test_set_output_updates_state(self, controller, state):
        await controller._on_set_output(AudioOutput.BROWSER)
        assert state.audio_output == AudioOutput.BROWSER

    async def test_set_sponsorblock_updates_state(self, controller, state):
        await controller._on_set_sponsorblock(True)
        assert state.sponsorblock_active is True

    async def test_set_loudness_normalization_updates_state(self, controller, state):
        await controller._on_set_loudness_normalization(True)
        assert state.loudness_normalization_enabled is True


class TestLyricsOffset:
    async def test_updates_offset_in_state(self, controller, state):
        await controller._on_lyrics_offset({"offset": 1.5})
        assert state.lyrics_offset == 1.5

    async def test_publishes_lyrics_updated_event(self, controller, bus):
        received = []
        bus.subscribe(LyricsUpdatedEvent, received.append)
        await controller._on_lyrics_offset({"offset": 2.0})
        assert len(received) == 1

    async def test_missing_offset_defaults_to_zero(self, controller, state):
        await controller._on_lyrics_offset({})
        assert state.lyrics_offset == 0.0
