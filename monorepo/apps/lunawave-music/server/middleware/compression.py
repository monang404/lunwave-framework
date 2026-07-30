"""
Module: server.middleware.compression

Purpose:
    PATCH-UI-PERF-01: aiohttp's `add_static()` serves files as-is with no
    gzip/deflate and no explicit Cache-Control -- every CSS/JS request pays
    full uncompressed transfer cost and browsers fall back to heuristic
    caching. `make_static_handler()` replaces `add_static()` with a handler
    that:

    - Serves precompressed .gz siblings (generated once, cached on disk
      next to the source file, regenerated only if the source changes)
      when the client sends `Accept-Encoding: gzip`, for text-based types
      (css/js/json/html/svg). Fonts (woff2), images, and audio are already
      compressed formats, so they're served as-is.
    - Sets `Cache-Control: public, max-age=1 day` on every static response,
      independent of the Service Worker's own cache. Kept short-ish (1 day)
      rather than 1-year-immutable because filenames here aren't
      content-hashed, so a deploy can still change file contents under the
      same URL.

Depends on:
    - gzip (stdlib)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (async aiohttp middleware), no shared mutable state.
"""

import gzip
import mimetypes
from pathlib import Path

from aiohttp import web

# Extensions worth gzip'ing. Fonts (woff2), images, and audio are already
# compressed formats -- re-gzipping them burns CPU for negligible/negative gain.
_COMPRESSIBLE_EXTS = {".css", ".js", ".json", ".html", ".svg", ".txt"}

# Skip tiny files -- gzip container overhead can exceed savings below ~1KB.
_MIN_GZIP_SIZE = 1024


def _gzip_sibling_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".gz")


def _ensure_gzip_sibling(path: Path) -> Path | None:
    """Return a fresh .gz sibling for `path`, (re)creating it if missing or
    stale (source mtime newer than the cached .gz). Returns None if `path`
    isn't a compressible/large-enough file. Cheap after the first request
    per file/deploy since the .gz is cached on disk alongside the source.
    """
    if path.suffix not in _COMPRESSIBLE_EXTS:
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size < _MIN_GZIP_SIZE:
        return None

    gz_path = _gzip_sibling_path(path)
    try:
        if gz_path.exists() and gz_path.stat().st_mtime >= path.stat().st_mtime:
            return gz_path
    except OSError:
        pass

    try:
        with open(path, "rb") as src:
            data = src.read()
        gz_path.write_bytes(gzip.compress(data, compresslevel=6))
    except OSError:
        return None
    return gz_path


def make_static_handler(static_dir: Path):
    """Build a GET handler serving files under `static_dir` with gzip
    (precompressed .gz siblings, generated/cached on demand) and a
    Cache-Control header, replacing aiohttp's plain `add_static`.
    """

    # 1 day: long enough to skip re-fetching on typical repeat visits within
    # a session/day, short enough that a stale asset after a deploy
    # self-heals quickly even for clients that ignore the Service Worker.
    max_age = 60 * 60 * 24

    async def handler(request: web.Request) -> web.StreamResponse:
        rel_path = request.match_info["path"]
        file_path = (static_dir / rel_path).resolve()

        # Path traversal guard -- resolved path must stay under static_dir.
        if static_dir not in file_path.parents and file_path != static_dir:
            raise web.HTTPForbidden()
        if not file_path.is_file():
            raise web.HTTPNotFound()

        accepts_gzip = "gzip" in request.headers.get("Accept-Encoding", "")
        gz_path = _ensure_gzip_sibling(file_path) if accepts_gzip else None

        content_type, _ = mimetypes.guess_type(str(file_path))
        headers = {"Cache-Control": f"public, max-age={max_age}"}

        if gz_path is not None:
            resp = web.FileResponse(gz_path, headers=headers)
            if content_type:
                resp.content_type = content_type
            resp.headers["Content-Encoding"] = "gzip"
            resp.headers["Vary"] = "Accept-Encoding"
            return resp

        return web.FileResponse(file_path, headers=headers)

    return handler
