from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.command_bus import CMD_CANCEL_DOWNLOAD, CMD_DOWNLOAD
from server.handlers.ws_download import handle_download_command


@pytest.mark.asyncio
@patch("server.handlers.ws_download.dict_to_track")
async def test_handle_download_command_download(mock_dict_to_track):
    mock_track = MagicMock()
    mock_dict_to_track.return_value = mock_track

    command_bus = AsyncMock()

    await handle_download_command(
        "download", {"title": "Test Track"}, None, None, None, None, command_bus
    )

    mock_dict_to_track.assert_called_once_with({"title": "Test Track"})
    command_bus.execute.assert_called_once_with(CMD_DOWNLOAD, mock_track)


@pytest.mark.asyncio
async def test_handle_download_command_cancel_download():
    """PATCH-2026-07-27: action baru 'cancel_download' harus meneruskan
    CMD_CANCEL_DOWNLOAD ke command_bus tanpa perlu payload track."""
    command_bus = AsyncMock()

    await handle_download_command("cancel_download", {}, None, None, None, None, command_bus)

    command_bus.execute.assert_called_once_with(CMD_CANCEL_DOWNLOAD)


@pytest.mark.asyncio
@patch("server.handlers.ws_download.DiscoverService")
@patch("server.handlers.ws_download.os.remove")
@patch("server.handlers.ws_download.os.path.exists")
async def test_handle_download_command_delete_download(
    mock_exists, mock_remove, mock_discover_service
):
    mock_tracks = AsyncMock()
    mock_discover = MagicMock()
    mock_track = MagicMock()
    mock_track.video_id = "test_vid"
    mock_track.local_path = "/path/to/test.mp3"
    mock_track.artist = "Test Artist"
    mock_track.title = "Test Title"

    mock_tracks.get_track.return_value = mock_track
    mock_exists.return_value = True

    mock_ds_instance = mock_discover_service.return_value
    mock_ds_instance.get_recent = AsyncMock(return_value=[])
    mock_ds_instance.get_favorites = AsyncMock(return_value=[])
    mock_ds_instance.get_cached = AsyncMock(return_value=[])
    mock_ds_instance.get_featured_artists = AsyncMock(return_value=[])
    mock_ds_instance.get_featured_genres = AsyncMock(return_value=[])

    mock_manager = AsyncMock()
    mock_state = MagicMock()

    with patch("server.handlers.ws_download.dict_to_track", return_value=mock_track):
        command_bus = AsyncMock()

        await handle_download_command(
            "delete_download",
            {"video_id": "test_vid"},
            mock_tracks,
            mock_discover,
            mock_manager,
            mock_state,
            command_bus,
        )

    mock_tracks.get_track.assert_called_once_with("test_vid")
    mock_exists.assert_called_with("/path/to/test.mp3")
    mock_remove.assert_any_call("/path/to/test.mp3")
    mock_tracks.set_local_path.assert_called_once_with("test_vid", None)

    assert mock_manager.broadcast.call_count == 2
    mock_manager.broadcast.assert_any_call(
        {"type": "log", "data": f"Unduhan dihapus: {mock_track.title}"}
    )
    discover_data_call = mock_manager.broadcast.call_args_list[0]
    assert discover_data_call[0][0]["type"] == "discover_data"
    assert discover_data_call[0][0]["data"]["favorites"] == []
