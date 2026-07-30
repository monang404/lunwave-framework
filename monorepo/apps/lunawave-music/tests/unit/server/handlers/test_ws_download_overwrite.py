import json
from unittest.mock import AsyncMock, patch

import pytest

from core.command_bus import CMD_DOWNLOAD
from server.handlers.ws_download import handle_download_command


@pytest.fixture
def mock_deps():
    class Deps:
        command_bus = AsyncMock()
        tracks = AsyncMock()
        discover = AsyncMock()
        manager = AsyncMock()
        state = AsyncMock()
        ws = AsyncMock()

    return Deps()


@pytest.mark.asyncio
@patch("server.handlers.ws_download.os.path.exists")
async def test_download_conflict_when_file_exists(mock_exists, mock_deps):
    mock_exists.return_value = True

    class MockTrack:
        video_id = "v1"
        local_path = "/tmp/v1.mp3"
        artist = "A"
        title = "T"

    mock_deps.tracks.get_track.return_value = MockTrack()

    data = {"video_id": "v1"}
    await handle_download_command(
        "download",
        data,
        mock_deps.tracks,
        mock_deps.discover,
        mock_deps.manager,
        mock_deps.state,
        mock_deps.command_bus,
        mock_deps.ws,
    )

    # Assert CMD_DOWNLOAD not executed
    mock_deps.command_bus.execute.assert_not_called()

    # Assert download_conflict sent
    mock_deps.ws.send_str.assert_called_once()
    sent_msg = json.loads(mock_deps.ws.send_str.call_args[0][0])
    assert sent_msg["type"] == "download_conflict"
    assert sent_msg["data"]["video_id"] == "v1"
    assert sent_msg["data"]["local_path"] == "/tmp/v1.mp3"


@pytest.mark.asyncio
async def test_download_normal_when_not_exists(mock_deps):
    mock_deps.tracks.get_track.return_value = None

    data = {"video_id": "v2"}
    await handle_download_command(
        "download",
        data,
        mock_deps.tracks,
        mock_deps.discover,
        mock_deps.manager,
        mock_deps.state,
        mock_deps.command_bus,
        mock_deps.ws,
    )

    # Assert CMD_DOWNLOAD executed
    mock_deps.command_bus.execute.assert_called_once()
    args = mock_deps.command_bus.execute.call_args[0]
    assert args[0] == CMD_DOWNLOAD
    assert args[1].video_id == "v2"


@pytest.mark.asyncio
async def test_download_confirm_overwrite(mock_deps):
    data = {"video_id": "v3"}
    await handle_download_command(
        "download_confirm_overwrite",
        data,
        mock_deps.tracks,
        mock_deps.discover,
        mock_deps.manager,
        mock_deps.state,
        mock_deps.command_bus,
        mock_deps.ws,
    )

    # Assert CMD_DOWNLOAD executed directly
    mock_deps.command_bus.execute.assert_called_once()
    args = mock_deps.command_bus.execute.call_args[0]
    assert args[0] == CMD_DOWNLOAD
    assert args[1].video_id == "v3"
