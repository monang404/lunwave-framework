from unittest.mock import MagicMock, patch

import pytest
from aiohttp import web

from server.handlers.audio_stream_handler import serve_stream


@pytest.mark.asyncio
async def test_audio_stream_cors_no_header_when_unconfigured():
    request = MagicMock()
    request.match_info = {"video_id": "12345678901"}
    request.headers = {"Origin": "https://evil.example"}

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.resolve.return_value.is_relative_to.return_value = True
        mock_cache_dir.__truediv__.return_value = mock_file

        with patch("server.handlers.audio_stream_handler.ALLOWED_STREAM_ORIGIN", ""):
            response = await serve_stream(request)

            assert isinstance(response, web.FileResponse)
            assert response.headers.get("Access-Control-Allow-Origin") is None


@pytest.mark.asyncio
async def test_audio_stream_cors_configured():
    request = MagicMock()
    request.match_info = {"video_id": "12345678901"}
    request.headers = {"Origin": "https://evil.example"}

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.resolve.return_value.is_relative_to.return_value = True
        mock_cache_dir.__truediv__.return_value = mock_file

        with patch(
            "server.handlers.audio_stream_handler.ALLOWED_STREAM_ORIGIN", "https://good.example"
        ):
            response = await serve_stream(request)

            assert isinstance(response, web.FileResponse)
            assert response.headers.get("Access-Control-Allow-Origin") == "https://good.example"


@pytest.mark.asyncio
async def test_audio_stream_cors_never_reflects_request_origin():
    request = MagicMock()
    request.match_info = {"video_id": "12345678901"}
    request.headers = {"Origin": "https://evil.example"}

    with patch("server.handlers.audio_stream_handler.CACHE_DIR") as mock_cache_dir:
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.resolve.return_value.is_relative_to.return_value = True
        mock_cache_dir.__truediv__.return_value = mock_file

        with patch(
            "server.handlers.audio_stream_handler.ALLOWED_STREAM_ORIGIN", "https://good.example"
        ):
            response = await serve_stream(request)

            assert isinstance(response, web.FileResponse)
            # Even though the request Origin differs from ALLOWED_STREAM_ORIGIN,
            # the response must always reflect the configured value, never the
            # request's Origin header.
            assert response.headers.get("Access-Control-Allow-Origin") == "https://good.example"
            assert response.headers.get("Access-Control-Allow-Origin") != "https://evil.example"
