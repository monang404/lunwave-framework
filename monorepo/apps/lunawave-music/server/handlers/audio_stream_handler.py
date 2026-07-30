"""
Module: server.handlers.audio_stream_handler

Purpose:
    Proxy cached/streamed MP3 audio for a track, including range-request
    support for seeking. Split out of server/handlers/http.py (T3.4) so
    the streaming/range-request logic isn't bundled with the SPA/health/
    metrics endpoints.

Responsibilities:
    - Serve cached MP3 files straight from CACHE_DIR when present.
    - Otherwise resolve a fresh stream URL (DB cache -> ytdlp fallback,
      with retry on expired URLs) and either redirect to it directly
      (no http_session configured) or proxy it through, forwarding the
      Range header so seeking works.
    - Validate stream URLs are HTTPS + googlevideo.com/youtube.com before
      redirecting or proxying, to prevent open-redirect / SSRF.

Depends on:
    - config
    - core.event_bus
    - core.events

Subscribes to:
    None

Publishes:
    LogMessageEvent (on stream-URL-expired retry)

Thread Safety:
    Worker thread (async aiohttp request handlers).
"""

import re
import time

import structlog
from aiohttp import web

from config import ALLOWED_STREAM_ORIGIN, CACHE_DIR, STREAM_PREBUFFER_BYTES, STREAM_URL_TTL_SEC
from core.exceptions import VideoUnavailableError
from core.log_categories import LC_PERSISTENCE, LC_RESOLVE, LC_SECURITY
from server.handlers import get_tracks_repo, get_ytdlp

_STREAM_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

logger = structlog.get_logger(component="server.audio_stream_handler")


def _notify_track_unavailable(message: str) -> None:
    """PATCH-2026-07-27: surface `unavailable_reason` ke UI. Sebelumnya
    reason ini cuma dikembalikan sebagai body HTTPGone dari endpoint
    /api/stream/{video_id} -- tapi jalur browser-audio memuatnya lewat
    elemen <audio src=...> native, yang TIDAK PERNAH mengekspos response
    body ke JS (audio.onerror cuma dapat MediaError generik). Jalur yang
    sudah terbukti sampai ke client adalah LogMessageEvent -> broadcast_log
    -> WS type "log" -> toast:log (lihat event_listeners.py, sudah dipakai
    persis untuk kasus serupa oleh engine/playback/failure_ops.py di jalur
    mpv). Reuse jalur yang sama di sini alih-alih menambah mekanisme baru.
    Dijalankan sebagai background task (bukan awaited) supaya tidak
    menunda response HTTPGone ke pemanggil, sama seperti pola
    stream_url_expired_refetching di bawah."""
    import asyncio

    from core.event_bus import bus
    from core.events import LogMessageEvent

    asyncio.create_task(bus.publish(LogMessageEvent(message=message)))


async def _mark_video_unavailable(db, video_id: str, row, reason: str) -> None:
    """PATCH-2026-07-20-136: handler ini cuma punya video_id, belum tentu
    ada TrackInfo lengkap (row) di DB. Pakai row yang sudah ada kalau ada,
    kalau tidak buat placeholder minimal -- mark_unavailable() sendiri
    sudah UPSERT jadi aman dipanggil untuk video_id yang belum pernah
    tersimpan sama sekali."""
    from core.state import TrackInfo

    track = row or TrackInfo(video_id=video_id, title=video_id, artist="unknown", duration=0)
    try:
        await db.mark_unavailable(track, reason)
    except Exception as e:
        logger.error(
            "mark_unavailable_failed",
            category=LC_PERSISTENCE,
            video_id=video_id,
            error_type=type(e).__name__,
            error=str(e),
        )
    _notify_track_unavailable(f"Lagu tidak tersedia (dihapus/private): {track.title} — dilewati")


async def serve_stream(request):
    video_id = request.match_info.get("video_id")
    if not video_id or not _STREAM_ID_RE.match(video_id):
        return web.HTTPBadRequest(text="Invalid video_id")

    cache_file = CACHE_DIR / f"{video_id}.mp3"
    try:
        if not cache_file.resolve().is_relative_to(CACHE_DIR.resolve()):
            return web.HTTPForbidden(text="Akses ditolak")
    except Exception:
        return web.HTTPBadRequest(text="Path tidak valid")

    cors_headers = (
        {"Access-Control-Allow-Origin": ALLOWED_STREAM_ORIGIN}
        if ALLOWED_STREAM_ORIGIN
        else {}
    )
    if cache_file.exists():
        return web.FileResponse(cache_file, headers=cors_headers)

    db = get_tracks_repo(request)
    ytdlp = get_ytdlp(request)
    stream_url = None

    # PATCH-2026-07-20-136 Rule 0: jalur ini (dipakai saat AudioOutput.BROWSER,
    # HTML5 <audio> proxy langsung ke sini) juga harus menghormati flag
    # unavailable yang sama seperti CacheResolver -- kalau tidak, video yang
    # sudah dikonfirmasi dihapus/private lewat jalur mpv tetap akan dicoba
    # ulang tanpa henti lewat jalur browser-audio ini.
    unavailable_reason = await db.get_unavailable_reason(video_id)
    if unavailable_reason:
        # Row belum di-fetch di titik ini (lihat get_track di bawah) dan
        # sengaja tidak di-fetch di sini juga -- lihat komentar Rule 0 di
        # bawah soal kenapa ini early-return murni tanpa I/O tambahan.
        # Makanya pesan toast pakai video_id, bukan judul lagu.
        _notify_track_unavailable(
            f"Lagu tidak tersedia ({unavailable_reason}): {video_id} — dilewati"
        )
        return web.HTTPGone(text=f"Video tidak tersedia: {unavailable_reason}")

    row = await db.get_track(video_id)
    if row and row.stream_url and row.stream_url_ts:
        if time.time() - row.stream_url_ts < STREAM_URL_TTL_SEC:
            stream_url = row.stream_url

    http_session = request.app.get("http_session")
    if not http_session:
        # Tidak ada proxy session — redirect langsung ke YouTube stream URL.
        # Harus fetch dulu jika belum ada di cache agar tidak redirect ke "".
        if not stream_url:
            try:
                stream_url = await ytdlp.get_stream_url(video_id)
                await db.update_stream_url_only(video_id, stream_url)
            except VideoUnavailableError as e:
                await _mark_video_unavailable(db, video_id, row, str(e))
                return web.HTTPGone(text=f"Video tidak tersedia: {e}")
            except Exception:
                # L8.1 (G8): exception ini sudah dicatat sebagai
                # stream_resolve_failed (ERROR, video_id/error_type/error)
                # oleh adapters/ytdlp/resolver.py di titik asal (boundary
                # resolve) -- lapisan ini tidak menambah field baru apa pun
                # (video_id/error_type/error identik), jadi tidak logging
                # ulang di sini (§12.5 / L-D4).
                return web.HTTPServiceUnavailable(text="Stream tidak tersedia saat ini")
        # Validasi domain sebelum redirect (cegah open-redirect / SSRF)
        from urllib.parse import urlparse as _urlparse

        _p = _urlparse(stream_url)
        _domain = _p.netloc.lower()
        if _p.scheme != "https" or not (
            _domain.endswith(".googlevideo.com") or _domain.endswith(".youtube.com")
        ):
            logger.error(
                "stream_redirect_url_invalid",
                category=LC_SECURITY,
                stream_url=stream_url,
            )
            return web.HTTPForbidden(text="URL stream tidak valid")
        return web.HTTPFound(stream_url)

    for attempt in range(2):
        if not stream_url:
            try:
                stream_url = await ytdlp.get_stream_url(video_id)
                await db.update_stream_url_only(video_id, stream_url)
            except VideoUnavailableError as e:
                # PATCH-2026-07-20-136: tidak ada gunanya retry attempt
                # kedua untuk video yang sudah dikonfirmasi permanen hilang.
                await _mark_video_unavailable(db, video_id, row, str(e))
                return web.HTTPGone(text=f"Video tidak tersedia: {e}")
            except Exception as e:
                if attempt == 1:
                    return web.HTTPInternalServerError(text=f"Gagal mencari stream: {e}")
                continue

        try:
            from urllib.parse import urlparse

            parsed_url = urlparse(stream_url)
            if parsed_url.scheme != "https":
                raise ValueError("Skema URL harus HTTPS")
            domain = parsed_url.netloc.lower()
            if not (domain.endswith(".googlevideo.com") or domain.endswith(".youtube.com")):
                raise ValueError(f"Domain tidak sah: {domain}")
        except Exception as e:
            logger.error(
                "ssrf_or_invalid_stream_url_detected",
                category=LC_SECURITY,
                stream_url=stream_url,
                error_type=type(e).__name__,
                error=str(e),
            )
            return web.HTTPForbidden(text="URL stream tidak valid")

        try:
            headers = {}
            if "Range" in request.headers:
                headers["Range"] = request.headers["Range"]

            async with http_session.get(stream_url, headers=headers) as upstream:
                if upstream.status in (403, 410) and attempt == 0:
                    logger.warning(
                        "stream_url_expired_refetching",
                        category=LC_RESOLVE,
                        upstream_status=upstream.status,
                    )
                    import asyncio

                    from core.event_bus import bus
                    from core.events import LogMessageEvent

                    asyncio.create_task(
                        bus.publish(LogMessageEvent(message="Mencoba ulang koneksi stream..."))
                    )
                    stream_url = None
                    continue

                stream_headers = {
                    "Content-Type": upstream.headers.get("Content-Type", "audio/mpeg"),
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "private, max-age=3600",
                }
                if ALLOWED_STREAM_ORIGIN:
                    stream_headers["Access-Control-Allow-Origin"] = ALLOWED_STREAM_ORIGIN

                response = web.StreamResponse(
                    status=upstream.status,
                    headers=stream_headers,
                )

                if "Content-Range" in upstream.headers:
                    response.headers["Content-Range"] = upstream.headers["Content-Range"]
                if "Content-Length" in upstream.headers:
                    try:
                        response.content_length = int(upstream.headers["Content-Length"])
                    except ValueError:
                        pass

                await response.prepare(request)

                # PATCH-2026-07-20-136: buffer beberapa chunk pertama DULU
                # (dari upstream, belum ditulis ke client) sebelum mulai
                # menulis apa pun ke client. Sebelumnya setiap chunk upstream
                # langsung await response.write() satu-satu -- kalau upstream
                # tersendat di detik-detik pertama, client langsung ikut
                # kena stutter karena tidak ada cushion. Ini TIDAK menunda
                # response.prepare() (header tetap terkirim cepat), cuma
                # menunda mulai mengirim BODY sampai ada cushion data.
                prebuffer: list[bytes] = []
                prebuffer_size = 0
                chunk_iter = upstream.content.iter_chunked(16384)
                async for chunk in chunk_iter:
                    prebuffer.append(chunk)
                    prebuffer_size += len(chunk)
                    if prebuffer_size >= STREAM_PREBUFFER_BYTES:
                        break

                for chunk in prebuffer:
                    await response.write(chunk)
                async for chunk in chunk_iter:
                    await response.write(chunk)

                await response.write_eof()
                return response

        except Exception as e:
            logger.warning(
                "proxy_stream_error",
                category=LC_RESOLVE,
                video_id=video_id,
                error_type=type(e).__name__,
                error=str(e),
            )
            if attempt == 0:
                stream_url = None
                continue
            return web.HTTPInternalServerError(text="Proxy stream error")
