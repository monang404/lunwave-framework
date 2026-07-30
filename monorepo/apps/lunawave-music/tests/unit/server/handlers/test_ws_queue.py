from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.command_bus import (
    CMD_PLAY_TRACK,
    CMD_QUEUE_ADD,
    CMD_QUEUE_REMOVE,
    CMD_QUEUE_REORDER,
    CMD_QUEUE_REPLACE,
    CMD_QUEUE_SELECT,
    CMD_SET_MODE,
)
from core.state import PlaybackMode
from server.handlers.ws_queue import handle_queue_command


@pytest.mark.asyncio
async def test_handle_queue_command_queue_select():
    command_bus = AsyncMock()

    await handle_queue_command("queue_select", {"index": 5}, None, None, command_bus)
    command_bus.execute.assert_called_once_with(CMD_QUEUE_SELECT, 5)


@pytest.mark.asyncio
async def test_handle_queue_command_queue_remove():
    command_bus = AsyncMock()

    await handle_queue_command("queue_remove", {"index": 2}, None, None, command_bus)
    command_bus.execute.assert_called_once_with(CMD_QUEUE_REMOVE, 2)


@pytest.mark.asyncio
@patch("server.handlers.ws_queue.dict_to_track")
async def test_handle_queue_command_queue_add(mock_dict_to_track):
    mock_track = MagicMock()
    mock_dict_to_track.return_value = mock_track
    command_bus = AsyncMock()

    await handle_queue_command("queue_add", {"title": "Test"}, None, None, command_bus)
    mock_dict_to_track.assert_called_once_with({"title": "Test"})
    command_bus.execute.assert_called_once_with(CMD_QUEUE_ADD, mock_track)


@pytest.mark.asyncio
async def test_handle_queue_command_queue_reorder():
    command_bus = AsyncMock()

    await handle_queue_command(
        "queue_reorder", {"from_index": 1, "to_index": 3}, None, None, command_bus
    )
    command_bus.execute.assert_called_once_with(CMD_QUEUE_REORDER, {"from_index": 1, "to_index": 3})


@pytest.mark.asyncio
async def test_handle_queue_command_enqueue_artist_songs():
    mock_db = AsyncMock()
    mock_db.get_artist_songs_strict.return_value = ["track1", "track2"]

    command_bus = AsyncMock()

    await handle_queue_command(
        "enqueue_artist_songs", {"artist": "ArtistName"}, mock_db, None, command_bus
    )

    mock_db.get_artist_songs_strict.assert_called_once_with(artist="ArtistName", limit=10)
    mock_db.increment_artist_click.assert_called_once_with("ArtistName")

    assert command_bus.execute.call_count == 2
    command_bus.execute.assert_any_call(CMD_QUEUE_REPLACE, ["track2"])
    command_bus.execute.assert_any_call(CMD_PLAY_TRACK, "track1")


@pytest.mark.asyncio
async def test_handle_queue_command_enqueue_genre_songs():
    mock_db = AsyncMock()
    mock_db.get_genre_songs.return_value = ["track1", "track2", "track3"]

    command_bus = AsyncMock()

    await handle_queue_command("enqueue_genre_songs", {"genre": "Pop"}, None, mock_db, command_bus)

    mock_db.get_genre_songs.assert_called_once_with("Pop", total_limit=12, max_per_artist=3)
    mock_db.increment_genre_click.assert_called_once_with("Pop")

    assert command_bus.execute.call_count == 3
    command_bus.execute.assert_any_call(CMD_SET_MODE, PlaybackMode.QUEUE)
    command_bus.execute.assert_any_call(CMD_QUEUE_REPLACE, ["track1", "track2", "track3"])
    command_bus.execute.assert_any_call(CMD_QUEUE_SELECT, 0)
