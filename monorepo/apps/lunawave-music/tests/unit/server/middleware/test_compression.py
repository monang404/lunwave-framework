"""
Module: tests.unit.server.middleware.test_compression

Purpose:
    Unit tests for server.middleware.compression (PATCH-UI-PERF-01),
    covering the handler that replaced aiohttp's plain add_static().

Responsibilities:
    - Verify gzip is served (with correct headers) when the client
      advertises Accept-Encoding: gzip, and only for compressible/large
      enough files.
    - Verify plain (non-gzip) responses when the client doesn't advertise
      gzip support, or for small/non-compressible files.
    - Verify Cache-Control is set on every static response.
    - Verify the .gz sibling is regenerated when the source file changes,
      and reused (not regenerated) when unchanged.
    - Verify path traversal attempts are rejected and missing files 404.

Depends on:
    - server.middleware.compression
    - aiohttp.test_utils

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop, pytest-asyncio).
"""

import gzip
import time

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from server.middleware.compression import _ensure_gzip_sibling, make_static_handler


def _make_app_request(tmp_path, rel_path, headers=None):
    handler = make_static_handler(tmp_path)
    request = make_mocked_request(
        "GET",
        f"/static/{rel_path}",
        headers=headers or {},
    )
    request.match_info["path"] = rel_path
    return handler, request


@pytest.mark.asyncio
async def test_serves_gzip_when_accepted_and_large_enough(tmp_path):
    css_content = ("body { color: red; }\n" * 100).encode()  # well over 1KB
    (tmp_path / "big.css").write_bytes(css_content)

    handler, request = _make_app_request(tmp_path, "big.css", {"Accept-Encoding": "gzip"})
    response = await handler(request)

    assert response.headers.get("Content-Encoding") == "gzip"
    assert response.headers.get("Vary") == "Accept-Encoding"
    assert response.headers.get("Cache-Control") == "public, max-age=86400"
    # The .gz sibling should now exist on disk, decompressing back to source.
    gz_path = tmp_path / "big.css.gz"
    assert gz_path.exists()
    assert gzip.decompress(gz_path.read_bytes()) == css_content


@pytest.mark.asyncio
async def test_no_gzip_when_client_does_not_accept_it(tmp_path):
    css_content = ("body { color: red; }\n" * 100).encode()
    (tmp_path / "big.css").write_bytes(css_content)

    handler, request = _make_app_request(tmp_path, "big.css", {})  # no Accept-Encoding
    response = await handler(request)

    assert "Content-Encoding" not in response.headers
    assert response.headers.get("Cache-Control") == "public, max-age=86400"


@pytest.mark.asyncio
async def test_small_file_not_gzipped_even_if_accepted(tmp_path):
    (tmp_path / "tiny.css").write_bytes(b"body{color:red}")  # well under 1KB

    handler, request = _make_app_request(tmp_path, "tiny.css", {"Accept-Encoding": "gzip"})
    response = await handler(request)

    assert "Content-Encoding" not in response.headers
    assert not (tmp_path / "tiny.css.gz").exists()


@pytest.mark.asyncio
async def test_non_compressible_extension_not_gzipped(tmp_path):
    # woff2/png/etc. are already compressed formats -- not in _COMPRESSIBLE_EXTS.
    (tmp_path / "font.woff2").write_bytes(b"\x00" * 2000)

    handler, request = _make_app_request(tmp_path, "font.woff2", {"Accept-Encoding": "gzip"})
    response = await handler(request)

    assert "Content-Encoding" not in response.headers


def test_gzip_sibling_regenerated_when_source_changes(tmp_path):
    path = tmp_path / "style.css"
    path.write_bytes(b"a" * 2000)

    gz1 = _ensure_gzip_sibling(path)
    first_bytes = gz1.read_bytes()

    # Same content, no mtime bump -- sibling should be reused as-is.
    gz2 = _ensure_gzip_sibling(path)
    assert gz2.read_bytes() == first_bytes

    # Bump mtime + change content -- sibling must be regenerated.
    time.sleep(0.01)
    path.write_bytes(b"b" * 2000)
    path.touch()
    gz3 = _ensure_gzip_sibling(path)
    assert gzip.decompress(gz3.read_bytes()) == b"b" * 2000


@pytest.mark.asyncio
async def test_path_traversal_is_rejected(tmp_path):
    (tmp_path / "safe.css").write_bytes(b"a" * 2000)
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("should not be reachable")

    handler, request = _make_app_request(tmp_path, "../secret.txt")
    with pytest.raises(web.HTTPForbidden):
        await handler(request)


@pytest.mark.asyncio
async def test_missing_file_returns_404(tmp_path):
    handler, request = _make_app_request(tmp_path, "does-not-exist.css")
    with pytest.raises(web.HTTPNotFound):
        await handler(request)
