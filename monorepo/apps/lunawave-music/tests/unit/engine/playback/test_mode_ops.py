"""
Module: tests.unit.engine.playback.test_mode_ops

Purpose:
    Unit tests for playback mode operations and toggles.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.event_bus
    - core.state
    - engine.playback.mode_ops
    - tests.fakes.fake_audio_player

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio

import pytest

from core.event_bus import EventBus
from core.state import AppState, AudioOutput, PlaybackMode, PlayerStatus, TrackInfo
from engine.loudness.gain_calculator import build_af_filter
from engine.playback.mode_ops import ModeOps
from tests.fakes.fake_audio_player import FakeAudioPlayer


class MockArtistSelector:
    def __init__(self):
        self.reset_rotation_called = False

    def reset_rotation(self):
        self.reset_rotation_called = True


class MockRadioMode:
    def __init__(self):
        self.deactivated = False
        self.artist_selector = MockArtistSelector()

    async def on_deactivated(self):
        self.deactivated = True


@pytest.fixture
def setup_mode_ops():
    state = AppState()
    bus = EventBus()
    lock = asyncio.Lock()
    mpv = FakeAudioPlayer()
    radio_mode = MockRadioMode()
    ops = ModeOps(state, bus, lock, mpv, radio_mode)
    return ops, state, mpv, radio_mode


@pytest.mark.asyncio
async def test_set_mode_to_radio(setup_mode_ops):
    ops, state, mpv, radio = setup_mode_ops

    should_activate = await ops.set_mode(PlaybackMode.RADIO)
    assert should_activate is True
    assert state.playback_mode == PlaybackMode.RADIO
    assert state.status == PlayerStatus.LOADING


@pytest.mark.asyncio
async def test_set_mode_from_radio(setup_mode_ops):
    ops, state, mpv, radio = setup_mode_ops
    state.playback_mode = PlaybackMode.RADIO

    should_activate = await ops.set_mode(PlaybackMode.QUEUE)
    assert should_activate is False
    assert state.playback_mode == PlaybackMode.QUEUE
    assert radio.deactivated is True
    assert mpv.is_playing is False
    assert state.status == PlayerStatus.IDLE


@pytest.mark.asyncio
async def test_randomize_radio(setup_mode_ops):
    ops, state, mpv, radio = setup_mode_ops
    state.playback_mode = PlaybackMode.RADIO

    should_fetch, seed = await ops.randomize_radio({"seed_artist": "Artist A"})
    assert should_fetch is True
    assert seed == "Artist A"
    assert radio.artist_selector.reset_rotation_called is True
    assert state.status == PlayerStatus.LOADING


@pytest.mark.asyncio
async def test_set_output(setup_mode_ops):
    ops, state, mpv, radio = setup_mode_ops
    state.volume = 50

    await ops.set_output(AudioOutput.BROWSER)
    assert state.audio_output == AudioOutput.BROWSER
    assert mpv.volume == 0

    await ops.set_output(AudioOutput.DEVICE)
    assert state.audio_output == AudioOutput.DEVICE
    assert mpv.volume == 50


@pytest.mark.asyncio
async def test_toggle_sponsorblock(setup_mode_ops):
    ops, state, mpv, radio = setup_mode_ops

    await ops.toggle_sponsorblock(True)
    assert state.sponsorblock_active is True


@pytest.mark.asyncio
async def test_toggle_loudness_normalization_applies_immediately_mid_song(setup_mode_ops):
    """Regression test: sebelumnya toggle ini cuma ganti state.loudness_normalization_enabled
    tanpa pernah manggil mpv.set_af(), jadi UI keliatan ON tapi audio baru berubah di lagu
    berikutnya. Toggle di tengah lagu sekarang harus langsung re-apply filter `af`."""
    ops, state, mpv, radio = setup_mode_ops
    state.current_track = TrackInfo(video_id="v1", title="Song", artist="Artist", duration=200)
    state.current_track_gain_db = 3.5

    await ops.toggle_loudness_normalization(True)
    assert state.loudness_normalization_enabled is True
    assert mpv.af == build_af_filter(3.5)

    await ops.toggle_loudness_normalization(False)
    assert state.loudness_normalization_enabled is False
    assert mpv.af == build_af_filter(0.0)


@pytest.mark.asyncio
async def test_toggle_loudness_normalization_no_current_track_is_noop_for_audio(setup_mode_ops):
    """Kalau tidak ada track yang sedang berjalan, tidak ada alasan untuk menyentuh mpv --
    state tetap diupdate untuk dipakai saat track berikutnya di-load."""
    ops, state, mpv, radio = setup_mode_ops
    assert state.current_track is None

    await ops.toggle_loudness_normalization(True)
    assert state.loudness_normalization_enabled is True
    assert ("set_af", build_af_filter(0.0)) not in mpv.call_log
    assert not any(call[0] == "set_af" for call in mpv.call_log)


@pytest.mark.asyncio
async def test_set_speed(setup_mode_ops):
    ops, state, mpv, radio = setup_mode_ops

    await ops.set_speed({"speed": 1.5})
    assert state.playback_speed == 1.5
    assert mpv.properties.get("speed") == 1.5
