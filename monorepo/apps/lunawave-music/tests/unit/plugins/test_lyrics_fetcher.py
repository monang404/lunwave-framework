from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.state import AppState, TrackInfo
from plugins.lyrics_fetcher import LyricsFetcher


@pytest.mark.asyncio
@patch("plugins.lyrics_parser.LyricsParser")
async def test_lyrics_fetcher_success(mock_parser):
    mock_parser.parse_lrc.return_value = [(10.0, "Line 1"), (20.0, "Line 2")]

    mock_state = AppState()
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_session = MagicMock()

    # Mocking the session get response for lrclib /get
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={"syncedLyrics": "[00:10.00]Line 1\n[00:20.00]Line 2"}
    )

    mock_request_context = MagicMock()
    mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_request_context.__aexit__ = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_request_context)

    fetcher = LyricsFetcher(mock_state, session=mock_session, event_bus=mock_bus)

    track = TrackInfo(video_id="123", title="Test Song", artist="Test Artist", duration=200)
    await fetcher.fetch(track)

    assert mock_session.get.call_count == 1
    # Check that lyrics were saved to state
    assert mock_state.lyrics_lines == ["Line 1", "Line 2"]
    assert mock_state.lyrics_timestamps == [10.0, 20.0]
    assert mock_state.lyrics_loading is False
    assert mock_bus.publish.call_count >= 2


@pytest.mark.asyncio
@patch("plugins.lyrics_fetcher.asyncio.wait_for")
@patch("plugins.lyrics_fetcher.asyncio.get_running_loop")
async def test_lyrics_fetcher_fallback_syncedlyrics(mock_get_loop, mock_wait_for):
    mock_state = AppState()
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_session = MagicMock()

    # Mock lrclib to fail (404)
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.json = AsyncMock(return_value={})

    mock_request_context = MagicMock()
    mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_request_context.__aexit__ = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_request_context)

    # Mock syncedlyrics response
    mock_wait_for.return_value = "[00:15.00]Fallback Line"

    fetcher = LyricsFetcher(mock_state, session=mock_session, event_bus=mock_bus)
    track = TrackInfo(video_id="123", title="Test Song", artist="Test Artist", duration=200)

    with patch("plugins.lyrics_parser.LyricsParser") as mock_parser:
        mock_parser.parse_lrc.return_value = [(15.0, "Fallback Line")]
        await fetcher.fetch(track)

    # We should have attempted /get and /search, so get is called 2 times
    assert mock_session.get.call_count == 2
    assert mock_wait_for.called
    assert mock_state.lyrics_lines == ["Fallback Line"]


@pytest.mark.asyncio
@patch("plugins.lyrics_fetcher.asyncio.wait_for")
@patch("plugins.lyrics_fetcher.asyncio.get_running_loop")
async def test_lyrics_fetcher_cleans_title(mock_get_loop, mock_wait_for):
    mock_state = AppState()
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_session = MagicMock()

    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.json = AsyncMock(return_value={})

    mock_request_context = MagicMock()
    mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_request_context.__aexit__ = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_request_context)

    fetcher = LyricsFetcher(mock_state, session=mock_session, event_bus=mock_bus)
    track = TrackInfo(
        video_id="123",
        title="Song Name Official Music Video (Lyrics)",
        artist="Test Artist",
        duration=200,
    )

    with patch("plugins.lyrics_parser.LyricsParser") as mock_parser:
        mock_parser.parse_lrc.return_value = []
        await fetcher.fetch(track)

    # Check search query
    assert mock_session.get.call_count == 2
    search_call_args = mock_session.get.call_args_list[1]
    assert search_call_args.kwargs["params"]["q"] == "Song Name Test Artist"
