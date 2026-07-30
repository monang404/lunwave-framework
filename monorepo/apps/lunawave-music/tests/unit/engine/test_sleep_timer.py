import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.command_bus import CMD_STOP
from engine.sleep_timer import SleepTimer


@pytest.mark.asyncio
async def test_set_timer_stops_playback():
    bus = AsyncMock()
    command_bus = AsyncMock()
    timer = SleepTimer(bus, command_bus)

    original_sleep = asyncio.sleep
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await timer.set_timer(1)

        # Allow the background task to run
        await original_sleep(0)

        mock_sleep.assert_any_call(60)
        command_bus.execute.assert_called_once_with(CMD_STOP)


@pytest.mark.asyncio
async def test_set_timer_cancels_previous():
    bus = AsyncMock()
    command_bus = AsyncMock()
    timer = SleepTimer(bus, command_bus)

    await timer.set_timer(5)
    first_task = timer._timer_task
    assert first_task is not None
    assert not first_task.cancelled()

    await timer.set_timer(0)
    import asyncio

    await asyncio.sleep(0)
    assert first_task.cancelled()
    assert timer._timer_task is None
