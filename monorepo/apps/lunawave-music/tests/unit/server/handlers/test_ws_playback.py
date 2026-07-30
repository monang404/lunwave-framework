from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.command_bus import (
    CMD_LYRICS_OFFSET,
    CMD_NEXT,
    CMD_PLAY_TRACK,
    CMD_PREV,
    CMD_RADIO_RANDOMIZE,
    CMD_SEEK,
    CMD_SET_LOUDNESS_NORMALIZATION,
    CMD_SET_MODE,
    CMD_SET_OUTPUT,
    CMD_SET_SPONSORBLOCK,
    CMD_STOP,
    CMD_TOGGLE_PAUSE,
    CMD_VOLUME_DOWN,
    CMD_VOLUME_SET,
    CMD_VOLUME_UP,
)
from core.state import AudioOutput, PlaybackMode
from server.handlers.ws_playback import handle_playback_command


@pytest.mark.asyncio
async def test_handle_playback_command_toggle_pause():
    command_bus = AsyncMock()

    await handle_playback_command("toggle_pause", {}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_TOGGLE_PAUSE)


@pytest.mark.asyncio
async def test_handle_playback_command_set_mode():
    command_bus = AsyncMock()

    await handle_playback_command("set_mode", {"mode": "radio"}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_SET_MODE, PlaybackMode.RADIO)


@pytest.mark.asyncio
@patch("server.handlers.ws_playback.dict_to_track")
async def test_handle_playback_command_play_track(mock_dict_to_track):
    mock_track = MagicMock()
    mock_dict_to_track.return_value = mock_track
    command_bus = AsyncMock()

    await handle_playback_command("play_track", {"id": "123"}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_PLAY_TRACK, mock_track)


@pytest.mark.asyncio
@patch("server.handlers.ws_playback.dict_to_track", return_value=None)
async def test_handle_playback_command_play_track_invalid(mock_dict_to_track):
    command_bus = AsyncMock()

    await handle_playback_command("play_track", {}, command_bus)
    command_bus.execute.assert_not_called()


@pytest.mark.asyncio
async def test_handle_playback_command_set_sponsorblock():
    command_bus = AsyncMock()

    await handle_playback_command("set_sponsorblock", {"enabled": False}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_SET_SPONSORBLOCK, False)


@pytest.mark.asyncio
async def test_handle_playback_command_set_loudness_normalization():
    command_bus = AsyncMock()

    await handle_playback_command("set_loudness_normalization", {"enabled": True}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_SET_LOUDNESS_NORMALIZATION, True)


@pytest.mark.asyncio
async def test_handle_playback_command_set_loudness_normalization_default_false():
    command_bus = AsyncMock()

    await handle_playback_command("set_loudness_normalization", {}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_SET_LOUDNESS_NORMALIZATION, False)


@pytest.mark.asyncio
async def test_handle_playback_command_lyrics_offset():
    command_bus = AsyncMock()

    await handle_playback_command("lyrics_offset", {"offset": -1.5}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_LYRICS_OFFSET, {"offset": -1.5})


@pytest.mark.asyncio
async def test_handle_playback_command_radio_randomize():
    command_bus = AsyncMock()

    await handle_playback_command("radio_randomize", {"seed_artist": "Coldplay"}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_RADIO_RANDOMIZE, {"seed_artist": "Coldplay"})


@pytest.mark.asyncio
async def test_handle_playback_command_set_output():
    command_bus = AsyncMock()

    await handle_playback_command("set_output", {"output": "browser"}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_SET_OUTPUT, AudioOutput.BROWSER)


@pytest.mark.asyncio
async def test_handle_playback_command_other_commands():
    command_bus = AsyncMock()

    await handle_playback_command("next", {"random": True}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_NEXT, {"random": True})
    command_bus.execute.reset_mock()

    command_bus = AsyncMock()

    await handle_playback_command("prev", {}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_PREV, {})
    command_bus.execute.reset_mock()

    command_bus = AsyncMock()

    await handle_playback_command("stop", {}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_STOP)
    command_bus.execute.reset_mock()

    command_bus = AsyncMock()

    await handle_playback_command("seek", {"position": 12.5}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_SEEK, 12.5)
    command_bus.execute.reset_mock()

    command_bus = AsyncMock()

    await handle_playback_command("volume_up", {}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_VOLUME_UP)
    command_bus.execute.reset_mock()

    command_bus = AsyncMock()

    await handle_playback_command("volume_down", {}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_VOLUME_DOWN)
    command_bus.execute.reset_mock()

    command_bus = AsyncMock()

    await handle_playback_command("volume_set", {"volume": 42}, command_bus)
    command_bus.execute.assert_called_once_with(CMD_VOLUME_SET, {"volume": 42})
