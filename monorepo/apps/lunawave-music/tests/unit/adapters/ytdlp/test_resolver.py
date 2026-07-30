"""
Module: adapters.ytdlp.resolver

Purpose:
    Unit tests for adapters.ytdlp.resolver.

Responsibilities:
    - Test functionality and edge cases.

Depends on:
    - adapters.ytdlp.resolver

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.ytdlp.resolver import YtDlpResolver, classify_ytdlp_error
from core.exceptions import BotCheckError, RateLimitedError, VideoUnavailableError


@pytest.fixture
def mock_executor():
    return MagicMock()


@pytest.mark.asyncio
async def test_get_stream_url_success(mock_executor):
    resolver = YtDlpResolver(mock_executor)

    with patch.object(
        resolver, "_extract_sync", return_value={"url": "http://stream.url/audio.mp3"}
    ):
        with patch(
            "asyncio.get_running_loop",
            return_value=MagicMock(
                run_in_executor=AsyncMock(return_value={"url": "http://stream.url/audio.mp3"})
            ),
        ):
            # The method also calls _pick_audio_url internally, let's mock it
            with patch.object(
                resolver, "_pick_audio_url", return_value="http://stream.url/audio.mp3"
            ):
                url = await resolver.get_stream_url("abc123_")
                assert url == "http://stream.url/audio.mp3"


@pytest.mark.asyncio
async def test_get_stream_url_failure(mock_executor):
    resolver = YtDlpResolver(mock_executor)

    with patch(
        "asyncio.get_running_loop",
        return_value=MagicMock(run_in_executor=AsyncMock(side_effect=Exception("yt-dlp error"))),
    ):
        with pytest.raises(RuntimeError):
            await resolver.get_stream_url("abc123_")


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)


# --- PATCH-2026-07-20-136: klasifikasi error yt-dlp -------------------------


@pytest.mark.parametrize(
    "message,expected_type",
    [
        ("Sign in to confirm you're not a bot", BotCheckError),
        ("ERROR: [youtube] abc123: Sign in to confirm your age", BotCheckError),
        ("HTTP Error 429: Too Many Requests", RateLimitedError),
        ("Video unavailable", VideoUnavailableError),
        (
            "ERROR: [youtube] abc123: Private video. Sign in if you've been granted access "
            "to this video",
            VideoUnavailableError,
        ),
        ("This video has been removed by the uploader", VideoUnavailableError),
    ],
)
def test_classify_ytdlp_error_matches_known_patterns(message, expected_type):
    result = classify_ytdlp_error("abc123", Exception(message))
    assert isinstance(result, expected_type)


def test_classify_ytdlp_error_returns_none_for_unrecognized_message():
    result = classify_ytdlp_error("abc123", Exception("some random ffmpeg pipe error"))
    assert result is None


# --- get_stream_url dengan typed exceptions ---------------------------------


@pytest.mark.asyncio
async def test_get_stream_url_raises_video_unavailable_error(mock_executor):
    resolver = YtDlpResolver(mock_executor)
    with patch.object(
        resolver, "_resolve_once", AsyncMock(side_effect=Exception("Video unavailable"))
    ):
        with pytest.raises(VideoUnavailableError):
            await resolver.get_stream_url("gone123")


@pytest.mark.asyncio
async def test_get_stream_url_raises_rate_limited_error_without_retry(mock_executor):
    resolver = YtDlpResolver(mock_executor)
    mock_resolve = AsyncMock(side_effect=Exception("HTTP Error 429: Too Many Requests"))
    with patch.object(resolver, "_resolve_once", mock_resolve):
        with pytest.raises(RateLimitedError):
            await resolver.get_stream_url("limited123")
    # Rate-limit tidak boleh retry sama sekali di level resolver -- cuma 1x panggilan.
    assert mock_resolve.call_count == 1


@pytest.mark.asyncio
async def test_get_stream_url_botcheck_retries_once_with_fallback_client_and_succeeds(
    mock_executor,
):
    resolver = YtDlpResolver(mock_executor)
    mock_resolve = AsyncMock(
        side_effect=[
            Exception("Sign in to confirm you're not a bot"),
            "https://stream.url/fallback-ok.mp3",
        ]
    )
    with patch.object(resolver, "_resolve_once", mock_resolve):
        url = await resolver.get_stream_url("botcheck123")

    assert url == "https://stream.url/fallback-ok.mp3"
    assert mock_resolve.call_count == 2
    # Percobaan kedua harus pakai opsi client fallback (android), bukan client default.
    second_call_opts = mock_resolve.call_args_list[1].args[1]
    assert second_call_opts.get("extractor_args", {}).get("youtube", {}).get("player_client") == [
        "android"
    ]


@pytest.mark.asyncio
async def test_get_stream_url_botcheck_still_fails_after_fallback_client(mock_executor):
    resolver = YtDlpResolver(mock_executor)
    mock_resolve = AsyncMock(
        side_effect=[
            Exception("Sign in to confirm you're not a bot"),
            Exception("Sign in to confirm you're not a bot"),
        ]
    )
    with patch.object(resolver, "_resolve_once", mock_resolve):
        with pytest.raises(BotCheckError):
            await resolver.get_stream_url("botcheck456")
    assert mock_resolve.call_count == 2


@pytest.mark.asyncio
async def test_get_stream_url_timeout_raises_runtimeerror_with_broken_chain(mock_executor):
    """Timeout di percobaan pertama harus menghasilkan RuntimeError dengan
    chain yang sengaja diputus ('from None'), konsisten dengan raise
    TimeoutError lain di file yang sama (mis. retry fallback client)."""
    resolver = YtDlpResolver(mock_executor)
    with patch.object(resolver, "_resolve_once", AsyncMock(side_effect=TimeoutError())):
        with pytest.raises(RuntimeError) as exc_info:
            await resolver.get_stream_url("timeout123")
    assert "Timeout" in str(exc_info.value)
    assert exc_info.value.__cause__ is None


@pytest.mark.asyncio
async def test_get_stream_url_unrecognized_error_still_raises_runtimeerror(mock_executor):
    """Perilaku LAMA untuk error yang tidak dikenali harus tetap sama persis
    (RuntimeError generik) -- klasifikasi baru tidak boleh mengubah ini."""
    resolver = YtDlpResolver(mock_executor)
    with patch.object(
        resolver, "_resolve_once", AsyncMock(side_effect=Exception("some obscure ffmpeg error"))
    ):
        with pytest.raises(RuntimeError) as exc_info:
            await resolver.get_stream_url("weird123")
    assert not isinstance(exc_info.value, (BotCheckError, RateLimitedError, VideoUnavailableError))
