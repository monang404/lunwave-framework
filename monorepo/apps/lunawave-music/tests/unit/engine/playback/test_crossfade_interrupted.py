import asyncio
from unittest.mock import AsyncMock

import pytest

from core.state import AppState, PlayerStatus
from engine.playback.crossfade import apply_crossfade_in, apply_crossfade_out


@pytest.fixture
def mock_mpv():
    return AsyncMock()


@pytest.fixture
def state():
    s = AppState()
    s.status = PlayerStatus.PLAYING
    s.volume = 80
    return s


@pytest.mark.asyncio
async def test_crossfade_in_interrupted(mock_mpv, state):
    # Buat state status berubah menjadi STOPPED setelah beberapa iterasi sleep
    original_sleep = asyncio.sleep

    async def mock_sleep(delay, result=None, **kwargs):
        state.status = PlayerStatus.IDLE
        await original_sleep(delay, result, **kwargs)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(asyncio, "sleep", mock_sleep)
        await apply_crossfade_in(mock_mpv, state)

    # Karena terinterupsi, mpv.set_volume harusnya dipanggil terakhir dengan state.volume (80)
    mock_mpv.set_volume.assert_called_with(80)


@pytest.mark.asyncio
async def test_crossfade_out_interrupted(mock_mpv, state):
    original_sleep = asyncio.sleep

    async def mock_sleep(delay, result=None, **kwargs):
        state.status = PlayerStatus.IDLE
        await original_sleep(delay, result, **kwargs)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(asyncio, "sleep", mock_sleep)
        await apply_crossfade_out(mock_mpv, state)

    # Karena terinterupsi, mpv.set_volume harusnya dipanggil terakhir dengan state.volume (80)
    mock_mpv.set_volume.assert_called_with(80)
