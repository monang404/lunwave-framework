"""
Module: adapters.ytdlp.downloader

Purpose:
    Unit tests for adapters.ytdlp.downloader.

Responsibilities:
    - Test functionality and edge cases.

Depends on:
    - adapters.ytdlp.downloader

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.ytdlp.downloader import YtDlpDownloader


@pytest.fixture
def mock_executor():
    return MagicMock()


@pytest.mark.asyncio
async def test_download_audio_success(mock_executor, tmp_path):
    downloader = YtDlpDownloader(mock_executor)

    def mock_download_sync(video_id, on_progress):
        return str(tmp_path / f"{video_id}.mp3")

    with patch.object(downloader, "_download_sync", side_effect=mock_download_sync):
        with patch(
            "asyncio.get_running_loop",
            return_value=MagicMock(
                run_in_executor=AsyncMock(return_value=mock_download_sync("abc123_", None))
            ),
        ):
            file_path = await downloader.download_audio("abc123_")
            assert "abc123_.opus" in file_path


@pytest.mark.asyncio
async def test_download_audio_handles_cancellation(mock_executor):
    downloader = YtDlpDownloader(mock_executor)
    downloader.cancel_download()

    assert downloader.is_cancelled is True


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
