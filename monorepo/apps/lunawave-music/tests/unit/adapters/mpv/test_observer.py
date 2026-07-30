"""
Module: adapters.mpv.observer

Purpose:
    Unit tests for adapters.mpv.observer.

Responsibilities:
    - Test functionality and edge cases.

Depends on:
    - adapters.mpv.observer

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.mpv.observer import MpvObserver


@pytest.fixture
def mock_connection():
    conn = MagicMock()
    conn.is_connected = True
    conn.shutting_down = False
    conn.reader = AsyncMock()
    return conn


@pytest.fixture
def mock_ipc():
    ipc = MagicMock()
    ipc.send_command = AsyncMock()
    return ipc


@pytest.fixture
def mock_event_bus():
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


def test_observer_initialization(mock_connection, mock_ipc, mock_event_bus):
    observer = MpvObserver(mock_connection, mock_ipc, mock_event_bus, room_id="test_room")
    assert observer._conn == mock_connection
    assert observer._ipc == mock_ipc
    assert observer._bus == mock_event_bus
    assert observer._room_id == "test_room"


@pytest.mark.asyncio
async def test_observer_start_and_stop(mock_connection, mock_ipc, mock_event_bus):
    observer = MpvObserver(mock_connection, mock_ipc, mock_event_bus)

    # Mocking read_readline so the loop doesn't block forever
    # It returns one empty byte to break the loop internally
    mock_connection.reader.readline.return_value = b""

    await observer.start()
    assert observer._task is not None
    assert not observer._task.done()

    # Let the event loop run so the task can start and await the coroutine
    await asyncio.sleep(0)

    await observer.stop()
    try:
        await observer._task
    except asyncio.CancelledError:
        pass

    assert observer._task.cancelled() or observer._task.done()


@pytest.mark.asyncio
async def test_observer_handles_property_change(mock_connection, mock_ipc, mock_event_bus):
    observer = MpvObserver(mock_connection, mock_ipc, mock_event_bus)

    # Simulate an MPV property-change event for 'time-pos'
    event_data = {"event": "property-change", "name": "time-pos", "data": 12.5}
    await observer._handle_event(event_data)

    # It should have published a TrackPositionEvent
    assert mock_event_bus.publish.call_count == 1
    call_args = mock_event_bus.publish.call_args[0][0]
    assert call_args.__class__.__name__ == "TrackProgressEvent"
    assert call_args.position == 12.5


@pytest.mark.asyncio
async def test_observer_handles_pause_change(mock_connection, mock_ipc, mock_event_bus):
    observer = MpvObserver(mock_connection, mock_ipc, mock_event_bus)

    event_data = {"event": "property-change", "name": "pause", "data": True}
    await observer._handle_event(event_data)

    assert mock_event_bus.publish.call_count == 1
    call_args = mock_event_bus.publish.call_args[0][0]
    assert call_args.__class__.__name__ == "TrackPauseChangedEvent"
    assert call_args.is_paused is True


@pytest.mark.asyncio
async def test_observer_ignores_unknown_property_change(mock_connection, mock_ipc, mock_event_bus):
    observer = MpvObserver(mock_connection, mock_ipc, mock_event_bus)

    event_data = {"event": "property-change", "name": "unknown-prop", "data": "value"}
    await observer._handle_event(event_data)

    mock_event_bus.publish.assert_not_called()


@pytest.mark.asyncio
async def test_observer_start_stop_cleanup_path(mock_connection, mock_ipc, mock_event_bus):
    observer = MpvObserver(mock_connection, mock_ipc, mock_event_bus)

    # Block readline indefinitely to simulate waiting for event
    async def block_readline():
        return await asyncio.get_event_loop().create_future()

    mock_connection.reader.readline = block_readline

    await observer.start()

    # Allow loop to switch context
    await asyncio.sleep(0.01)

    # Stop should cancel the task
    mock_connection.shutting_down = True
    await observer.stop()
    await asyncio.sleep(0.01)

    assert observer._task.cancelled() or observer._task.done()

    assert mock_connection.is_connected is False
    mock_ipc.cancel_all_pending.assert_called_once()


@pytest.mark.asyncio
async def test_observer_reconnects_on_disconnect(mock_connection, mock_ipc, mock_event_bus):
    observer = MpvObserver(mock_connection, mock_ipc, mock_event_bus)

    async def mock_reconnect():
        mock_connection.is_connected = True
        return True

    mock_connection.reconnect = AsyncMock(side_effect=mock_reconnect)

    async def side_effect():
        if mock_connection.reader.readline.call_count == 1:
            raise ConnectionError("Disconnected")
        return await asyncio.get_event_loop().create_future()

    mock_connection.reader.readline = AsyncMock(side_effect=side_effect)

    original_sleep = asyncio.sleep

    async def fast_sleep(delay, *args, **kwargs):
        if delay >= 1:
            return await original_sleep(0.001)
        return await original_sleep(delay)

    with patch("adapters.mpv.observer.asyncio.sleep", side_effect=fast_sleep):
        await observer.start()
        await asyncio.sleep(0.05)

    mock_connection.shutting_down = True
    assert mock_connection.reconnect.call_count == 1
    await observer.stop()


@pytest.mark.asyncio
async def test_observer_reconnect_fails_publishes_error(mock_connection, mock_ipc, mock_event_bus):
    observer = MpvObserver(mock_connection, mock_ipc, mock_event_bus)

    mock_connection.reconnect = AsyncMock(return_value=False)

    # Immediately raise ConnectionError
    mock_connection.reader.readline = AsyncMock(side_effect=ConnectionError("Disconnected"))

    original_sleep = asyncio.sleep

    async def fast_sleep(delay, *args, **kwargs):
        if delay >= 1:
            return await original_sleep(0.001)
        return await original_sleep(delay)

    with patch("adapters.mpv.observer.asyncio.sleep", side_effect=fast_sleep):
        await observer.start()

        # Wait for the reconnect loop to finish (3 attempts)
        await asyncio.sleep(0.05)

    assert mock_connection.reconnect.call_count == 3

    # Yield once more for loop.create_task to run
    await asyncio.sleep(0.05)

    mock_event_bus.publish.assert_called()
    published_event = mock_event_bus.publish.call_args[0][0]
    assert published_event.__class__.__name__ == "TrackEndedEvent"
    assert published_event.reason == "error"

    mock_connection.shutting_down = True
    await observer.stop()
