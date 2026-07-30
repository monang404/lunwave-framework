from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import RateLimitedError, VideoUnavailableError
from core.state import TrackInfo
from services.stream_prefetch import StreamPrefetchService


@pytest.mark.asyncio
async def test_stream_prefetch_service():
    # Basic instantiation
    state = AsyncMock()
    ytdlp = AsyncMock()
    svc = StreamPrefetchService(state, ytdlp)
    assert svc is not None


def _make_db(track_row=None, unavailable_reason=None):
    db = AsyncMock()
    db.get_track.return_value = track_row
    db.get_unavailable_reason.return_value = unavailable_reason
    return db


@pytest.mark.asyncio
async def test_prefetch_skips_ytdlp_when_marked_unavailable():
    # PATCH-2026-07-20-136 Rule 0
    db = _make_db(track_row=None, unavailable_reason="Private video")
    ytdlp = AsyncMock()
    svc = StreamPrefetchService(db, ytdlp)

    await svc.prefetch_stream_url("gone123")

    ytdlp.get_stream_url.assert_not_called()


@pytest.mark.asyncio
async def test_prefetch_retries_transient_error_and_succeeds_on_second_attempt():
    db = _make_db()
    ytdlp = AsyncMock()
    ytdlp.get_stream_url.side_effect = [Exception("network hiccup"), "https://ok.stream"]
    svc = StreamPrefetchService(db, ytdlp)

    with patch("services.stream_prefetch.asyncio.sleep", AsyncMock()):
        await svc.prefetch_stream_url("v1")

    assert ytdlp.get_stream_url.call_count == 2
    db.update_stream_url_only.assert_called_once_with("v1", "https://ok.stream")


@pytest.mark.asyncio
async def test_prefetch_gives_up_after_max_attempts_still_failing():
    db = _make_db()
    ytdlp = AsyncMock()
    ytdlp.get_stream_url.side_effect = Exception("always fails")
    svc = StreamPrefetchService(db, ytdlp)

    with patch("services.stream_prefetch.asyncio.sleep", AsyncMock()) as mock_sleep:
        await svc.prefetch_stream_url("v1")

    from config import PREFETCH_RETRY_ATTEMPTS

    assert ytdlp.get_stream_url.call_count == PREFETCH_RETRY_ATTEMPTS
    db.update_stream_url_only.assert_not_called()
    # Sleep hanya dipanggil ANTARA percobaan, bukan setelah percobaan terakhir
    assert mock_sleep.call_count == PREFETCH_RETRY_ATTEMPTS - 1


@pytest.mark.asyncio
async def test_prefetch_video_unavailable_error_marks_db_and_does_not_retry():
    track = TrackInfo(video_id="gone123", title="T", artist="A", duration=100)
    db = _make_db(track_row=track)
    ytdlp = AsyncMock()
    ytdlp.get_stream_url.side_effect = VideoUnavailableError("Video unavailable")
    svc = StreamPrefetchService(db, ytdlp)

    await svc.prefetch_stream_url("gone123")

    assert ytdlp.get_stream_url.call_count == 1  # tidak retry untuk error permanen
    db.mark_unavailable.assert_called_once()
    call_args = db.mark_unavailable.call_args
    assert call_args.args[0].video_id == "gone123"


@pytest.mark.asyncio
async def test_prefetch_rate_limited_error_does_not_retry():
    db = _make_db()
    ytdlp = AsyncMock()
    ytdlp.get_stream_url.side_effect = RateLimitedError("HTTP 429")
    svc = StreamPrefetchService(db, ytdlp)

    with patch("services.stream_prefetch.asyncio.sleep", AsyncMock()) as mock_sleep:
        await svc.prefetch_stream_url("v1")

    assert ytdlp.get_stream_url.call_count == 1
    mock_sleep.assert_not_called()
    db.update_stream_url_only.assert_not_called()
    db.mark_unavailable.assert_not_called()  # rate-limit BUKAN video yang permanen mati


@pytest.mark.asyncio
async def test_prefetch_still_respects_fresh_cache_ttl_without_hitting_ytdlp():
    """Sanity check: perilaku Rule-lama (skip kalau cache masih fresh) harus
    tetap sama persis -- patch retry/Rule-0 tidak boleh mengubah ini."""
    import time as time_module

    fresh_row = MagicMock()
    fresh_row.stream_url = "https://cached.stream"
    fresh_row.stream_url_ts = time_module.time() - 10
    db = _make_db(track_row=fresh_row)
    ytdlp = AsyncMock()
    svc = StreamPrefetchService(db, ytdlp)

    with patch("services.stream_prefetch.STREAM_URL_TTL_SEC", 3600):
        await svc.prefetch_stream_url("v1")

    ytdlp.get_stream_url.assert_not_called()
    db.get_unavailable_reason.assert_not_called()  # early-return sebelum sempat Rule 0
