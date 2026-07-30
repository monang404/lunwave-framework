"""
Module: server.handlers.http

Purpose:
    Serve the SPA index, health check, and Prometheus metrics endpoints
    over HTTP.

Responsibilities:
    - Serve index.html with no-cache headers for SPA routing.
    - Report DB/mpv connectivity for health checks.
    - Expose Prometheus metrics, gated to localhost or a shared token.

    Audio stream proxying (range-request support) moved out to
    server/handlers/audio_stream_handler.py (T3.4) — see that module for
    serve_stream.

Depends on:
    - core.mem_stats
    - core.observability

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (async aiohttp request handlers).
"""

from pathlib import Path

import structlog
from aiohttp import web

from core.mem_stats import get_rss_mb
from core.observability import get_metrics_content
from server.handlers import get_conn, get_manager, get_playback_controller, get_server_clock

logger = structlog.get_logger(component="server.http")
STATIC_DIR = Path(__file__).parent.parent.parent / "web" / "static"


async def serve_index(request):
    resp = web.FileResponse(STATIC_DIR / "pages/app/index.html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


async def serve_client(request):
    resp = web.FileResponse(STATIC_DIR / "pages/client/client.html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


async def health_check(request):
    conn = get_conn(request)
    db_status = "connected" if conn else "disconnected"

    pc = get_playback_controller(request)
    mpv_ok = getattr(getattr(pc, "mpv", None), "is_connected", False)
    mpv_status = "connected" if mpv_ok else "not_started"

    # ADR-0010: field tambahan, tidak pernah menggagalkan /health kalau
    # salah satu sumbernya bermasalah -- fallback None (JSON null).
    try:
        server_clock = get_server_clock(request)
        uptime_seconds = round(server_clock.uptime_seconds, 1)
    except Exception:
        uptime_seconds = None

    memory_mb = get_rss_mb()  # sudah fail-safe (None kalau gagal/tidak didukung)

    try:
        manager = get_manager(request)
        active_connections = len(manager.active_connections)
    except Exception:
        active_connections = None

    return web.json_response(
        {
            "status": "ok" if db_status == "connected" else "degraded",
            "db": db_status,
            "mpv": mpv_status,
            "uptime_seconds": uptime_seconds,
            "memory_mb": memory_mb,
            "active_connections": active_connections,
        }
    )


def require_local_or_token(request) -> bool:
    import os as _os
    import secrets as _secrets

    client_ip = request.remote
    _localhost_ips = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
    metrics_token = _os.environ.get(
        "LUNAWAVE_METRICS_TOKEN", _os.environ.get("YTGUI_METRICS_TOKEN")
    )
    is_local = client_ip in _localhost_ips
    request_token = request.headers.get("X-Metrics-Token", "")
    # PATCH-2026-07-16-001: secrets.compare_digest() alih-alih `==` untuk
    # membandingkan token, mencegah timing attack yang bisa membocorkan
    # token metrics byte demi byte.
    has_valid_token = bool(metrics_token) and _secrets.compare_digest(request_token, metrics_token)
    return is_local or has_valid_token


async def serve_metrics(request):
    if not require_local_or_token(request):
        return web.HTTPForbidden(
            text="Akses ditolak: metrics hanya untuk localhost atau gunakan X-Metrics-Token"
        )

    content, content_type = get_metrics_content()
    ct = content_type.split(";")[0].strip()
    return web.Response(body=content, content_type=ct)
