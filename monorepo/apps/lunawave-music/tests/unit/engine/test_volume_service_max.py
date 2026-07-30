from unittest.mock import AsyncMock

import pytest

from core.state import AppState, AudioOutput
from engine.volume_service import MAX_VOLUME, VolumeService


@pytest.fixture
def mock_bus():
    bus = AsyncMock()
    return bus


@pytest.fixture
def mock_mpv():
    mpv = AsyncMock()
    return mpv


@pytest.fixture
def volume_service(mock_bus, mock_mpv):
    state = AppState()
    state.volume = 95
    state.audio_output = AudioOutput.DEVICE
    return VolumeService(mock_bus, mock_mpv, state)


@pytest.mark.asyncio
async def test_volume_set_clamps_to_max(volume_service):
    # Set volume 200
    await volume_service._on_volume_set({"volume": 200})
    assert volume_service.current_volume == MAX_VOLUME
    assert volume_service.state.volume == MAX_VOLUME
    volume_service.mpv.set_volume.assert_called_with(MAX_VOLUME)


@pytest.mark.asyncio
async def test_volume_up_clamps_to_max(volume_service):
    # Initial volume 95, up 5
    await volume_service._on_volume_up()
    assert volume_service.current_volume == 100

    # Up again, should stay at 100
    await volume_service._on_volume_up()
    assert volume_service.current_volume == 100
