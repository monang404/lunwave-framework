"""
Module: adapters.ytdlp.searcher

Purpose:
    Unit tests for adapters.ytdlp.searcher.

Responsibilities:
    - Test functionality and edge cases.

Depends on:
    - adapters.ytdlp.searcher

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from unittest.mock import MagicMock, patch

import pytest

from adapters.ytdlp.searcher import YtDlpSearcher


@pytest.fixture
def mock_executor():
    return MagicMock()


def test_to_track():
    searcher = YtDlpSearcher(None)

    entry = {
        "id": "abc123_",
        "title": "A Great Song",
        "uploader": "The Artist",
        "duration": "125",
        "thumbnail": "http://img.jpg",
    }

    track = searcher._to_track(entry)

    assert track.video_id == "abc123_"
    assert track.title == "A Great Song"
    assert track.artist == "The Artist"
    assert track.duration == 125
    assert track.thumbnail == "http://img.jpg"


def test_to_track_empty_or_invalid_id():
    searcher = YtDlpSearcher(None)

    entry = {"title": "Unknown Song"}

    track1 = searcher._to_track(entry)
    track2 = searcher._to_track(entry)

    assert track1.video_id.startswith("vid_")
    assert track1.video_id == track2.video_id  # Deterministic check
    assert track1.title == "Unknown Song"
    assert track1.artist == "Unknown"
    assert track1.duration == 0


@pytest.mark.asyncio
async def test_search_filters_and_limits_results(mock_executor):
    searcher = YtDlpSearcher(mock_executor)

    with patch.object(
        searcher,
        "_extract_sync",
        return_value={
            "entries": [
                {"id": "1", "title": "Song 1", "duration": 180},
                {"id": "2", "title": "Song 2 Compilation", "duration": 200},
                {"id": "3", "title": "Song 3", "duration": 700},
                {"id": "4", "title": "Song 4", "duration": 150},
            ]
        },
    ):
        with patch(
            "asyncio.get_running_loop",
            return_value=MagicMock(
                run_in_executor=AsyncMock(
                    return_value={
                        "entries": [
                            {"id": "1", "title": "Song 1", "duration": 180},
                            {"id": "2", "title": "Song 2 Compilation", "duration": 200},
                            {"id": "3", "title": "Song 3", "duration": 700},
                            {"id": "4", "title": "Song 4", "duration": 150},
                        ]
                    }
                )
            ),
        ):
            tracks = await searcher.search("query", max_results=5)

            assert len(tracks) == 2
            assert tracks[0].video_id == "1"
            assert tracks[1].video_id == "4"


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
