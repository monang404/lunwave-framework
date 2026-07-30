"""
Module: tests.unit.engine.playback.test_track_ended_ops

Purpose:
    Unit tests for engine.playback.track_ended_ops -- sebelumnya modul ini
    punya nol test coverage (lihat implementation-plan.md Batch 3, item #9).

Responsibilities:
    - Verifikasi dispatch on_track_ended untuk reason eof/stop/error.
    - Verifikasi grace-window guard _handle_stop(): status "nyangkut" di
      PLAYING (stop basi diabaikan) vs stop asli (status di-set IDLE).
    - Verifikasi _handle_error() membatalkan autoplay kalau user sudah
      stop/ganti lagu selama sleep.
    - Verifikasi poll_duration mengisi durasi kalau belum tersedia dari mpv.

Depends on:
    - engine.playback.track_ended_ops
    - core.state

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.events import TrackEndedEvent
from core.state import AppState, PlayerStatus, TrackInfo
from engine.playback.track_ended_ops import GRACE_WINDOW_SECONDS, TrackEndedOps, poll_duration


def make_controller(status=PlayerStatus.PLAYING, last_play_start_offset=0.0):
    """Controller palsu minimal -- TrackEndedOps hanya butuh atribut ini."""
    controller = MagicMock()
    controller.state = AppState()
    controller.state.status = status
    controller.state.current_track = TrackInfo(
        video_id="vid1", title="Song", artist="Artist", duration=180
    )
    controller._loading = False
    controller._last_play_start_ts = asyncio.get_event_loop().time() - last_play_start_offset
    controller.bus = AsyncMock()
    controller.bus.publish = AsyncMock()
    controller._on_next = AsyncMock()
    return controller


@pytest.mark.asyncio
async def test_on_track_ended_eof_advances_to_next():
    controller = make_controller()
    ops = TrackEndedOps(controller)

    await ops.on_track_ended(TrackEndedEvent(reason="eof"))

    controller._on_next.assert_awaited_once()
    assert controller._on_next.call_args[0][0]["video_id"] == "vid1"


@pytest.mark.asyncio
async def test_on_track_ended_error_dispatches_to_handle_error():
    controller = make_controller(status=PlayerStatus.PLAYING)
    ops = TrackEndedOps(controller)

    await ops.on_track_ended(TrackEndedEvent(reason="error"))

    assert controller.state.status == PlayerStatus.ERROR
    controller.bus.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_stop_ignored_while_loading():
    """Kalau controller sedang _loading (transisi track), event 'stop'
    langsung diabaikan tanpa menyentuh status."""
    controller = make_controller(status=PlayerStatus.PLAYING)
    controller._loading = True
    ops = TrackEndedOps(controller)

    await ops._handle_stop({})

    assert controller.state.status == PlayerStatus.PLAYING


@pytest.mark.asyncio
async def test_handle_stop_within_grace_window_ignores_stale_stop_when_playing_again():
    """Kasus utama grace-window: 'stop' basi dari track lama datang setelah
    track baru sudah PLAYING -- status tidak boleh ke-overwrite jadi IDLE
    ('nyangkut' di PLAYING adalah perilaku yang benar di sini, bukan bug)."""
    controller = make_controller(status=PlayerStatus.PLAYING, last_play_start_offset=0.1)
    ops = TrackEndedOps(controller)

    await ops._handle_stop({})

    assert controller.state.status == PlayerStatus.PLAYING


@pytest.mark.asyncio
async def test_handle_stop_within_grace_window_sets_idle_if_not_playing_after_wait():
    """Masih dalam grace window, tapi status BUKAN PLAYING setelah nunggu
    -- berarti tidak ada transisi track baru yang menyusul, jadi ini stop
    asli dan status harus di-set IDLE."""
    controller = make_controller(status=PlayerStatus.LOADING, last_play_start_offset=0.1)
    ops = TrackEndedOps(controller)

    await ops._handle_stop({})

    assert controller.state.status == PlayerStatus.IDLE


@pytest.mark.asyncio
async def test_handle_stop_outside_grace_window_sets_idle_immediately():
    """Di luar grace window (track sudah lama mulai, bukan transisi baru
    saja) -- 'stop' langsung dianggap stop asli, status IDLE tanpa nunggu."""
    controller = make_controller(
        status=PlayerStatus.PLAYING,
        last_play_start_offset=GRACE_WINDOW_SECONDS + 5.0,
    )
    ops = TrackEndedOps(controller)

    await ops._handle_stop({})

    assert controller.state.status == PlayerStatus.IDLE


@pytest.mark.asyncio
async def test_handle_error_cancels_autoplay_if_user_already_stopped():
    controller = make_controller(status=PlayerStatus.PLAYING)
    ops = TrackEndedOps(controller)

    async def fast_sleep(_):
        controller.state.status = PlayerStatus.IDLE

    orig_sleep = asyncio.sleep
    try:
        asyncio.sleep = fast_sleep
        await ops._handle_error({"video_id": "vid1"})
    finally:
        asyncio.sleep = orig_sleep

    controller._on_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_error_cancels_autoplay_if_track_changed_during_sleep():
    controller = make_controller(status=PlayerStatus.PLAYING)
    ops = TrackEndedOps(controller)

    async def fast_sleep(_):
        controller.state.current_track = TrackInfo(
            video_id="different_vid", title="Other", artist="Other", duration=100
        )

    orig_sleep = asyncio.sleep
    try:
        asyncio.sleep = fast_sleep
        await ops._handle_error({"video_id": "vid1"})
    finally:
        asyncio.sleep = orig_sleep

    controller._on_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_error_advances_to_next_when_no_interruption():
    controller = make_controller(status=PlayerStatus.PLAYING)
    ops = TrackEndedOps(controller)

    async def fast_sleep(_):
        pass

    orig_sleep = asyncio.sleep
    try:
        asyncio.sleep = fast_sleep
        await ops._handle_error({"video_id": "vid1"})
    finally:
        asyncio.sleep = orig_sleep

    controller._on_next.assert_awaited_once_with({"video_id": "vid1"})


@pytest.mark.asyncio
async def test_poll_duration_fills_missing_duration():
    state = AppState()
    track = TrackInfo(video_id="vid1", title="Song", artist="Artist", duration=0)
    state.current_track = track

    mpv = AsyncMock()
    mpv.get_duration = AsyncMock(return_value=210.0)
    resolver = MagicMock()
    resolver.db.upsert_track = AsyncMock()
    bus = AsyncMock()
    bus.publish = AsyncMock()

    orig_sleep = asyncio.sleep
    try:
        asyncio.sleep = AsyncMock()
        await poll_duration(state, mpv, resolver, bus, track)
    finally:
        asyncio.sleep = orig_sleep

    assert state.duration == 210.0
    assert track.duration == 210
    bus.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_duration_stops_if_track_changed():
    """Kalau track sudah berganti selama polling, jangan lanjut update
    durasi track lama ke state track yang baru."""
    state = AppState()
    old_track = TrackInfo(video_id="vid1", title="Song", artist="Artist", duration=0)
    state.current_track = TrackInfo(video_id="vid2", title="Other", artist="Other", duration=0)

    mpv = AsyncMock()
    mpv.get_duration = AsyncMock(return_value=210.0)
    resolver = MagicMock()
    bus = AsyncMock()

    orig_sleep = asyncio.sleep
    try:
        asyncio.sleep = AsyncMock()
        await poll_duration(state, mpv, resolver, bus, old_track)
    finally:
        asyncio.sleep = orig_sleep

    mpv.get_duration.assert_not_awaited()
    bus.publish.assert_not_awaited()
