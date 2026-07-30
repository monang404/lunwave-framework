"""
Module: tests.unit.engine.playback.test_crossfade

Purpose:
    Unit tests for engine.playback.crossfade.

Responsibilities:
    - Verifikasi apply_crossfade_in mencapai volume target.
    - Verifikasi fade berhenti awal kalau status berubah.
    - Verifikasi cancellation.
    - Verifikasi apply_crossfade_out mencapai volume nol.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from core.state import AppState, PlayerStatus
from engine.playback.crossfade import apply_crossfade_in, apply_crossfade_out


def make_mpv():
    mpv = AsyncMock()
    mpv.set_volume = AsyncMock()
    return mpv


def patch_sleep():
    """Helper untuk mempercepat test tanpa harus benar-benar sleep 0.2s."""
    from unittest.mock import patch

    return patch("engine.playback.crossfade.asyncio.sleep", new_callable=AsyncMock)


@pytest.mark.asyncio
async def test_apply_crossfade_in_reaches_target_volume():
    state = AppState()
    state.status = PlayerStatus.PLAYING
    state.volume = 80
    mpv = make_mpv()

    with patch_sleep():
        await apply_crossfade_in(mpv, state)

    calls = [c.args[0] for c in mpv.set_volume.call_args_list]
    assert calls[0] == 0
    assert calls[-1] == 80


@pytest.mark.asyncio
async def test_apply_crossfade_in_stops_early_when_status_changes():
    state = AppState()
    state.status = PlayerStatus.PLAYING
    state.volume = 100
    mpv = make_mpv()

    call_count = 0

    async def fake_sleep(_):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            state.status = PlayerStatus.PAUSED

    from unittest.mock import patch

    with patch("engine.playback.crossfade.asyncio.sleep", fake_sleep):
        await apply_crossfade_in(mpv, state)

    calls = [c.args[0] for c in mpv.set_volume.call_args_list]
    assert calls[-1] == 100  # Now explicit restore to full volume is expected
    assert len(calls) < 11


@pytest.mark.asyncio
async def test_apply_crossfade_in_cancellation_does_not_corrupt_state():
    state = AppState()
    state.status = PlayerStatus.PLAYING
    state.volume = 80
    mpv = make_mpv()

    task = asyncio.create_task(apply_crossfade_in(mpv, state))
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    calls = [c.args[0] for c in mpv.set_volume.call_args_list]
    assert all(0 <= v <= state.volume for v in calls)


@pytest.mark.asyncio
async def test_apply_crossfade_out_reaches_zero():
    state = AppState()
    state.status = PlayerStatus.PLAYING
    state.volume = 60
    mpv = make_mpv()

    with patch_sleep():
        await apply_crossfade_out(mpv, state)

    calls = [c.args[0] for c in mpv.set_volume.call_args_list]
    assert calls[-1] == 0


@pytest.mark.asyncio
async def test_apply_crossfade_out_stops_early_when_status_changes():
    state = AppState()
    state.status = PlayerStatus.PLAYING
    state.volume = 100
    mpv = make_mpv()

    call_count = 0

    async def fake_sleep(_):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            state.status = PlayerStatus.PAUSED

    from unittest.mock import patch

    with patch("engine.playback.crossfade.asyncio.sleep", fake_sleep):
        await apply_crossfade_out(mpv, state)

    calls = [c.args[0] for c in mpv.set_volume.call_args_list]
    assert 0 not in calls
