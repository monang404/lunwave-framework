from unittest.mock import AsyncMock, MagicMock

import pytest

from core.events import QueueUpdatedEvent, TrackProgressEvent
from server.handlers.event_listeners import setup_event_listeners


@pytest.mark.asyncio
async def test_setup_event_listeners_binds_all_events():
    mock_pc = MagicMock()
    mock_prefetch = AsyncMock()
    mock_broadcast = AsyncMock()

    setup_event_listeners(mock_pc, mock_prefetch, mock_broadcast)

    # Check that bus.subscribe was called multiple times
    assert mock_pc.bus.subscribe.call_count == 8


@pytest.mark.asyncio
async def test_event_listener_track_progress():
    mock_pc = MagicMock()
    mock_pc.state.status.name = "PLAYING"
    mock_prefetch = AsyncMock()
    mock_broadcast = AsyncMock()

    callbacks = {}

    def mock_subscribe(event_cls, callback):
        callbacks[event_cls] = callback

    mock_pc.bus.subscribe.side_effect = mock_subscribe

    setup_event_listeners(mock_pc, mock_prefetch, mock_broadcast)

    # Retrieve the callback for TrackProgressEvent
    progress_callback = callbacks.get(TrackProgressEvent)
    assert progress_callback is not None

    event = TrackProgressEvent(position=10.5)
    await progress_callback(event)

    mock_broadcast.broadcast_progress.assert_called_once_with(10.5, "PLAYING")


@pytest.mark.asyncio
async def test_event_listener_queue_updated():
    mock_pc = MagicMock()
    mock_prefetch = AsyncMock()
    mock_broadcast = AsyncMock()

    callbacks = {}

    def mock_subscribe(event_cls, callback):
        callbacks[event_cls] = callback

    mock_pc.bus.subscribe.side_effect = mock_subscribe

    setup_event_listeners(mock_pc, mock_prefetch, mock_broadcast)

    queue_callback = callbacks.get(QueueUpdatedEvent)
    event = QueueUpdatedEvent()
    await queue_callback(event)

    mock_broadcast.broadcast_state.assert_called_once_with(mock_pc.state)
