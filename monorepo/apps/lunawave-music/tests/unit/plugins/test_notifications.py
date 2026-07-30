from unittest.mock import AsyncMock, MagicMock

import pytest

from plugins.notifications import TermuxNowPlaying


@pytest.mark.asyncio
async def test_termux_now_playing():
    bus = MagicMock()
    bus.publish = AsyncMock()
    state = AsyncMock()
    plugin = TermuxNowPlaying(bus, state)
    assert plugin is not None
