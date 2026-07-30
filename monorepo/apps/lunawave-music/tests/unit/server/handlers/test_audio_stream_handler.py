"""
Module: server.handlers.audio_stream_handler

Purpose:
    Unit tests for server.handlers.audio_stream_handler.serve_stream.
    Moved out of tests/unit/server/handlers/test_http.py (T3.4) alongside
    the serve_stream extraction into its own handler module.

Responsibilities:
    - Test functionality and edge cases: invalid video_id, path
      traversal, cache hit, DB-cached stream URL (fresh/stale), direct
      redirect vs proxy, range-request header forwarding, SSRF/domain
      validation, and retry-on-expired-URL behavior.

Depends on:
    - server.handlers.audio_stream_handler

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web

from core.event_bus import bus
from core.events import LogMessageEvent
from core.exceptions import VideoUnavailableError
from server.app import TRACKS, YTDLP
from server.handlers.audio_stream_handler import serve_stream


async def _drain_background_tasks():
    """_notify_track_unavailable() does `asyncio.create_task(bus.publish(...))`,
    and bus.publish() itself schedules a child task per async handler before
    awaiting it via gather -- so the notification needs the event loop to
    turn over more than once before it's actually delivered. A single
    `await asyncio.sleep(0)` only yields once (enough to start the outer
    task, not enough for the inner one to finish), so loop a few times."""
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.fixture
def captured_log_messages():
    """Subscribe to the global event bus for LogMessageEvent and yield the
    list it's appended to. _notify_track_unavailable() fires its publish as
    a background asyncio task (so it never delays the HTTPGone response),
    so tests using this fixture must `await _drain_background_tasks()` after
    calling serve_stream() to let that task actually run before asserting."""
    received = []

    async def _capture(event):
        received.append(event)

    bus.subscribe(LogMessageEvent, _capture)
    yield received
    bus.unsubscribe(LogMessageEvent, _capture)


@pytest.fixture
def mock_request():
    req = MagicMock()
    req.app = {}
    return req


@pytest.mark.asyncio
async def test_serve_stream_invalid_video_id(mock_request):
    mock_request.match_info = {"video_id": "invalid!"}

    resp = await serve_stream(mock_request)
    assert isinstance(resp, web.HTTPBadRequest)
    assert resp.text == "Invalid video_id"


@pytest.mark.asyncio
@patch("server.handlers.audio_stream_handler._STREAM_ID_RE")
async def test_serve_stream_path_traversal(mock_regex, mock_request):
    mock_regex.match.return_value = True
    mock_request.match_info = {"video_id": "../../../etc/passwd"}

    with patch("server.handlers.audio_stream_handler.CACHE_DIR", Path("/fake/cache")):
        resp = await serve_stream(mock_request)
        assert isinstance(resp, web.HTTPForbidden)
        assert resp.text == "Akses ditolak"


@pytest.mark.asyncio
async def test_serve_stream_cache_hit(mock_request):
    mock_request.match_info = {"video_id": "abc123DEF-4"}

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_file = MagicMock()
        mock_cache_dir.__truediv__.return_value = mock_cache_file

        mock_cache_file.resolve.return_value.is_relative_to.return_value = True
        mock_cache_file.exists.return_value = True

        mock_request.headers = {}
        with patch("server.handlers.audio_stream_handler.web.FileResponse") as mock_file_resp:
            mock_file_resp.return_value = "file_response_mock"
            resp = await serve_stream(mock_request)

            assert resp == "file_response_mock"
            mock_file_resp.assert_called_once_with(mock_cache_file, headers={})


@pytest.mark.asyncio
async def test_serve_stream_db_fresh_no_http_session(mock_request):
    mock_request.match_info = {"video_id": "abc123DEF-4"}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None  # PATCH-2026-07-20-136 Rule 0
    mock_row = MagicMock()
    mock_row.stream_url = "https://example.googlevideo.com/videoplayback"
    mock_row.stream_url_ts = time.time() - 10  # Fresh
    mock_db.get_track.return_value = mock_row

    mock_ytdlp = AsyncMock()

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        with patch("server.handlers.audio_stream_handler.STREAM_URL_TTL_SEC", 3600):
            resp = await serve_stream(mock_request)

            assert isinstance(resp, web.HTTPFound)
            assert resp.location == "https://example.googlevideo.com/videoplayback"
            mock_ytdlp.get_stream_url.assert_not_called()


@pytest.mark.asyncio
async def test_serve_stream_db_stale_no_http_session(mock_request):
    mock_request.match_info = {"video_id": "abc123DEF-4"}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None  # PATCH-2026-07-20-136 Rule 0
    mock_row = MagicMock()
    mock_row.stream_url = "https://old.googlevideo.com/videoplayback"
    mock_row.stream_url_ts = time.time() - 8000  # Stale
    mock_db.get_track.return_value = mock_row

    mock_ytdlp = AsyncMock()
    mock_ytdlp.get_stream_url.return_value = "https://new.googlevideo.com/videoplayback"

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        with patch("server.handlers.audio_stream_handler.STREAM_URL_TTL_SEC", 3600):
            resp = await serve_stream(mock_request)

            assert isinstance(resp, web.HTTPFound)
            assert resp.location == "https://new.googlevideo.com/videoplayback"
            mock_ytdlp.get_stream_url.assert_called_once_with("abc123DEF-4")
            mock_db.update_stream_url_only.assert_called_once_with(
                "abc123DEF-4", "https://new.googlevideo.com/videoplayback"
            )


@pytest.mark.asyncio
async def test_serve_stream_redirect_invalid_domain(mock_request):
    mock_request.match_info = {"video_id": "abc123DEF-4"}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None  # PATCH-2026-07-20-136 Rule 0
    mock_row = MagicMock()
    mock_row.stream_url = "https://evil.com/stream"
    mock_row.stream_url_ts = time.time() - 10  # Fresh
    mock_db.get_track.return_value = mock_row

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = AsyncMock()

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        with patch("server.handlers.audio_stream_handler.STREAM_URL_TTL_SEC", 3600):
            resp = await serve_stream(mock_request)

            assert isinstance(resp, web.HTTPForbidden)
            assert resp.text == "URL stream tidak valid"


@pytest.mark.asyncio
async def test_serve_stream_redirect_invalid_scheme(mock_request):
    mock_request.match_info = {"video_id": "abc123DEF-4"}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None  # PATCH-2026-07-20-136 Rule 0
    mock_row = MagicMock()
    mock_row.stream_url = "http://example.googlevideo.com/stream"
    mock_row.stream_url_ts = time.time() - 10  # Fresh
    mock_db.get_track.return_value = mock_row

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = AsyncMock()

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        with patch("server.handlers.audio_stream_handler.STREAM_URL_TTL_SEC", 3600):
            resp = await serve_stream(mock_request)

            assert isinstance(resp, web.HTTPForbidden)
            assert resp.text == "URL stream tidak valid"


@pytest.mark.asyncio
async def test_serve_stream_proxy_retry_fetch_success(mock_request):
    mock_request.match_info = {"video_id": "abc123DEF-4"}
    mock_request.headers = {}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None  # PATCH-2026-07-20-136 Rule 0
    mock_db.get_track.return_value = None

    mock_ytdlp = AsyncMock()
    # First attempt fails, second succeeds
    mock_ytdlp.get_stream_url.side_effect = [
        Exception("Fail"),
        "https://example.googlevideo.com/stream",
    ]

    mock_http_session = MagicMock()
    mock_upstream = MagicMock()
    mock_upstream.status = 200
    mock_upstream.headers = {"Content-Type": "audio/mpeg", "Content-Length": "100"}

    async def mock_chunked(*args, **kwargs):
        yield b"data"

    mock_upstream.content.iter_chunked = mock_chunked

    mock_http_session.get.return_value.__aenter__.return_value = mock_upstream

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp
    mock_request.app["http_session"] = mock_http_session

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        with patch(
            "server.handlers.audio_stream_handler.web.StreamResponse"
        ) as mock_stream_response:
            mock_resp_obj = AsyncMock()
            mock_resp_obj.headers = {}
            mock_stream_response.return_value = mock_resp_obj

            resp = await serve_stream(mock_request)

            assert resp == mock_resp_obj
            assert mock_ytdlp.get_stream_url.call_count == 2
            mock_resp_obj.write.assert_called_once_with(b"data")
            mock_resp_obj.write_eof.assert_called_once()


@pytest.mark.asyncio
async def test_serve_stream_proxy_retry_both_fail(mock_request):
    mock_request.match_info = {"video_id": "abc123DEF-4"}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None  # PATCH-2026-07-20-136 Rule 0
    mock_db.get_track.return_value = None

    mock_ytdlp = AsyncMock()
    mock_ytdlp.get_stream_url.side_effect = [Exception("Fail 1"), Exception("Fail 2")]

    mock_http_session = AsyncMock()

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp
    mock_request.app["http_session"] = mock_http_session

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        resp = await serve_stream(mock_request)

        assert isinstance(resp, web.HTTPInternalServerError)
        assert "Gagal mencari stream" in resp.text


@pytest.mark.asyncio
async def test_serve_stream_proxy_range_header(mock_request):
    mock_request.match_info = {"video_id": "abc123DEF-4"}
    mock_request.headers = {"Range": "bytes=0-100"}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None  # PATCH-2026-07-20-136 Rule 0
    mock_row = MagicMock()
    mock_row.stream_url = "https://example.googlevideo.com/stream"
    mock_row.stream_url_ts = time.time() - 10  # Fresh
    mock_db.get_track.return_value = mock_row

    mock_ytdlp = AsyncMock()

    mock_http_session = MagicMock()
    mock_upstream = MagicMock()
    mock_upstream.status = 206
    mock_upstream.headers = {"Content-Type": "audio/mpeg", "Content-Range": "bytes 0-100/1000"}

    async def mock_chunked(*args, **kwargs):
        yield b"data"

    mock_upstream.content.iter_chunked = mock_chunked

    mock_http_session.get.return_value.__aenter__.return_value = mock_upstream

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp
    mock_request.app["http_session"] = mock_http_session

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        with patch("server.handlers.audio_stream_handler.STREAM_URL_TTL_SEC", 3600):
            with patch(
                "server.handlers.audio_stream_handler.web.StreamResponse"
            ) as mock_stream_response:
                mock_resp_obj = AsyncMock()
                mock_resp_obj.headers = {}
                mock_stream_response.return_value = mock_resp_obj

                resp = await serve_stream(mock_request)

                assert resp == mock_resp_obj
                mock_http_session.get.assert_called_once_with(
                    "https://example.googlevideo.com/stream", headers={"Range": "bytes=0-100"}
                )
                assert mock_resp_obj.headers["Content-Range"] == "bytes 0-100/1000"


@pytest.mark.asyncio
async def test_serve_stream_proxy_forbidden_retry(mock_request):
    mock_request.match_info = {"video_id": "abc123DEF-4"}
    mock_request.headers = {}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None  # PATCH-2026-07-20-136 Rule 0
    mock_row = MagicMock()
    mock_row.stream_url = "https://example.googlevideo.com/stream"
    mock_row.stream_url_ts = time.time() - 10  # Fresh
    mock_db.get_track.return_value = mock_row

    mock_ytdlp = AsyncMock()
    mock_ytdlp.get_stream_url.return_value = "https://example.googlevideo.com/newstream"

    mock_http_session = MagicMock()

    # First request returns 403, second returns 200
    mock_upstream_403 = MagicMock()
    mock_upstream_403.status = 403
    mock_upstream_403.headers = {}

    mock_upstream_200 = MagicMock()
    mock_upstream_200.status = 200
    mock_upstream_200.headers = {}
    mock_http_session.get.return_value.__aenter__.side_effect = [
        mock_upstream_403,
        mock_upstream_200,
    ]

    # need to return an async mock for iter_chunked
    async def mock_chunked(*args, **kwargs):
        yield b"data"

    mock_upstream_200.content.iter_chunked = mock_chunked

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp
    mock_request.app["http_session"] = mock_http_session

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        with patch("server.handlers.audio_stream_handler.STREAM_URL_TTL_SEC", 3600):
            with patch(
                "server.handlers.audio_stream_handler.web.StreamResponse"
            ) as mock_stream_response:
                mock_resp_obj = AsyncMock()
                mock_resp_obj.headers = {}
                mock_stream_response.return_value = mock_resp_obj

                await serve_stream(mock_request)

                assert mock_http_session.get.call_count == 2
                assert mock_ytdlp.get_stream_url.call_count == 1


# --- PATCH-2026-07-20-136: Rule 0 (flag unavailable) -----------------------


@pytest.mark.asyncio
async def test_serve_stream_returns_410_when_marked_unavailable_without_calling_ytdlp(
    mock_request,
):
    mock_request.match_info = {"video_id": "abc123DEF-4"}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = "Private video"
    mock_ytdlp = AsyncMock()

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        resp = await serve_stream(mock_request)

        assert isinstance(resp, web.HTTPGone)
        assert "Private video" in resp.text
        mock_ytdlp.get_stream_url.assert_not_called()
        mock_db.get_track.assert_not_called()


@pytest.mark.asyncio
async def test_serve_stream_notifies_toast_when_already_marked_unavailable(
    mock_request, captured_log_messages
):
    """PATCH-2026-07-27: sebelumnya reason ini cuma jadi body HTTPGone yang
    tidak pernah dibaca browser (native <audio> tidak expose response body).
    Sekarang harus keluar juga lewat LogMessageEvent supaya sampai ke toast
    di client (lihat _notify_track_unavailable)."""
    mock_request.match_info = {"video_id": "abc123DEF-4"}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = "Private video"
    mock_ytdlp = AsyncMock()

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        await serve_stream(mock_request)
        await _drain_background_tasks()  # let the background publish task run

        assert len(captured_log_messages) == 1
        assert "Private video" in captured_log_messages[0].message
        assert "abc123DEF-4" in captured_log_messages[0].message


@pytest.mark.asyncio
async def test_serve_stream_marks_unavailable_on_video_unavailable_error_no_http_session(
    mock_request, captured_log_messages
):
    mock_request.match_info = {"video_id": "abc123DEF-4"}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None
    mock_db.get_track.return_value = None

    mock_ytdlp = AsyncMock()
    mock_ytdlp.get_stream_url.side_effect = VideoUnavailableError("Video unavailable")

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp
    # tidak ada http_session -> masuk jalur redirect

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        resp = await serve_stream(mock_request)
        await _drain_background_tasks()  # let the background publish task run

        assert isinstance(resp, web.HTTPGone)
        mock_db.mark_unavailable.assert_called_once()
        # tidak boleh retry attempt kedua untuk error permanen
        assert mock_ytdlp.get_stream_url.call_count == 1
        # PATCH-2026-07-27: toast juga harus terkirim untuk kasus baru
        # ditemukan (bukan cuma kasus sudah pernah ditandai sebelumnya)
        assert len(captured_log_messages) == 1
        assert "abc123DEF-4" in captured_log_messages[0].message


@pytest.mark.asyncio
async def test_serve_stream_marks_unavailable_on_video_unavailable_error_proxy_path(
    mock_request,
):
    mock_request.match_info = {"video_id": "abc123DEF-4"}
    mock_request.headers = {}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None
    mock_db.get_track.return_value = None

    mock_ytdlp = AsyncMock()
    mock_ytdlp.get_stream_url.side_effect = VideoUnavailableError("Private video")

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp
    mock_request.app["http_session"] = AsyncMock()  # proxy path (bukan redirect)

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        resp = await serve_stream(mock_request)

        assert isinstance(resp, web.HTTPGone)
        mock_db.mark_unavailable.assert_called_once()
        assert mock_ytdlp.get_stream_url.call_count == 1  # tidak retry attempt ke-2


# --- PATCH-2026-07-20-136: pre-buffer sebelum serve ke client --------------


@pytest.mark.asyncio
async def test_serve_stream_prebuffers_before_writing_to_client(mock_request):
    """Dengan prebuffer threshold kecil (2 chunk @4 byte = 8 byte), upstream
    yang mengirim 3 chunk harus di-buffer 2 chunk pertama dulu (ditulis
    sekaligus begitu threshold tercapai), baru chunk ke-3 ditulis menyusul --
    semua isi & urutan tetap benar, cuma TIMING pengirimannya yang berubah."""
    mock_request.match_info = {"video_id": "abc123DEF-4"}
    mock_request.headers = {}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None
    mock_db.get_track.return_value = None

    mock_ytdlp = AsyncMock()

    mock_http_session = MagicMock()
    mock_upstream = MagicMock()
    mock_upstream.status = 200
    mock_upstream.headers = {"Content-Type": "audio/mpeg"}

    async def mock_chunked(*args, **kwargs):
        yield b"aaaa"
        yield b"bbbb"
        yield b"cccc"

    mock_upstream.content.iter_chunked = mock_chunked
    mock_http_session.get.return_value.__aenter__.return_value = mock_upstream

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp
    mock_request.app["http_session"] = mock_http_session

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        with patch("server.handlers.audio_stream_handler.STREAM_URL_TTL_SEC", 3600):
            with patch("server.handlers.audio_stream_handler.STREAM_PREBUFFER_BYTES", 8):
                with patch(
                    "server.handlers.audio_stream_handler.web.StreamResponse"
                ) as mock_stream_response:
                    mock_resp_obj = AsyncMock()
                    mock_resp_obj.headers = {}
                    mock_stream_response.return_value = mock_resp_obj
                    mock_db.get_track.return_value = None

                    # Butuh stream_url langsung tersedia (DB row None -> ytdlp)
                    mock_ytdlp.get_stream_url.return_value = (
                        "https://example.googlevideo.com/stream"
                    )

                    resp = await serve_stream(mock_request)

        assert resp == mock_resp_obj
        # Urutan & isi semua chunk tetap benar & lengkap, cuma cara
        # penulisannya yang berubah (buffer dulu baru tulis).
        written = [call.args[0] for call in mock_resp_obj.write.call_args_list]
        assert written == [b"aaaa", b"bbbb", b"cccc"]
        mock_resp_obj.write_eof.assert_called_once()


@pytest.mark.asyncio
async def test_serve_stream_prebuffer_handles_short_stream_smaller_than_threshold(
    mock_request,
):
    """Range request pendek (sisa file < ukuran prebuffer) harus tetap
    terkirim utuh -- loop prebuffer berhenti wajar begitu upstream habis,
    tidak menunggu/nge-hang menunggu data yang tidak akan pernah datang."""
    mock_request.match_info = {"video_id": "abc123DEF-4"}
    mock_request.headers = {"Range": "bytes=990-1000"}

    mock_db = AsyncMock()
    mock_db.get_unavailable_reason.return_value = None
    mock_db.get_track.return_value = None

    mock_ytdlp = AsyncMock()
    mock_ytdlp.get_stream_url.return_value = "https://example.googlevideo.com/stream"

    mock_http_session = MagicMock()
    mock_upstream = MagicMock()
    mock_upstream.status = 206
    mock_upstream.headers = {"Content-Type": "audio/mpeg"}

    async def mock_chunked(*args, **kwargs):
        yield b"tinychunk"  # jauh lebih kecil dari STREAM_PREBUFFER_BYTES default

    mock_upstream.content.iter_chunked = mock_chunked
    mock_http_session.get.return_value.__aenter__.return_value = mock_upstream

    mock_request.app[TRACKS] = mock_db
    mock_request.app[YTDLP] = mock_ytdlp
    mock_request.app["http_session"] = mock_http_session

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_cache_dir.__truediv__.return_value.resolve.return_value.is_relative_to.return_value = (
            True
        )
        mock_cache_dir.__truediv__.return_value.exists.return_value = False

        with patch(
            "server.handlers.audio_stream_handler.web.StreamResponse"
        ) as mock_stream_response:
            mock_resp_obj = AsyncMock()
            mock_resp_obj.headers = {}
            mock_stream_response.return_value = mock_resp_obj

            resp = await serve_stream(mock_request)

    assert resp == mock_resp_obj
    written = [call.args[0] for call in mock_resp_obj.write.call_args_list]
    assert written == [b"tinychunk"]
    mock_resp_obj.write_eof.assert_called_once()
