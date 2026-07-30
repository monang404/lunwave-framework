"""
Module: server.handlers.log_dashboard

Purpose:
    Provide HTTP endpoints for the Logging Dashboard (tail, stats, and HTML).

Responsibility:
    - serve_log_dashboard: Serve the admin-logs.html file.
    - get_logs_tail: Read recent logs with optional filtering.
    - get_logs_stats: Provide log statistics and core server metrics.

Depends on:
    - core.log_reader
    - core.observability
    - server.handlers.http

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Worker thread (async aiohttp request handlers).
"""

from pathlib import Path

from aiohttp import web

from core.log_categories import ALL_CATEGORIES
from core.log_reader import stats, tail
from core.observability import COMMAND_COUNT, HTTP_REQUESTS_TOTAL, get_counter_value
from server.handlers.http import require_local_or_token

STATIC_DIR = Path(__file__).parent.parent.parent / "web" / "static"


async def serve_log_dashboard(request):
    if not require_local_or_token(request):
        return web.HTTPForbidden(
            text="Akses ditolak: metrics/logs hanya untuk localhost atau gunakan X-Metrics-Token"
        )
    resp = web.FileResponse(STATIC_DIR / "pages/admin-logs/admin-logs.html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


async def get_logs_tail(request):
    if not require_local_or_token(request):
        return web.HTTPForbidden(
            text="Akses ditolak: metrics/logs hanya untuk localhost atau gunakan X-Metrics-Token"
        )

    limit = int(request.query.get("limit", 200))
    category = request.query.get("category")
    level = request.query.get("level")
    q = request.query.get("q")

    logs = tail(limit=limit, category=category, level=level, query=q)
    return web.json_response({"logs": logs})


async def get_logs_stats(request):
    if not require_local_or_token(request):
        return web.HTTPForbidden(
            text="Akses ditolak: metrics/logs hanya untuk localhost atau gunakan X-Metrics-Token"
        )

    window = int(request.query.get("window", 3600))
    log_stats = stats(window_seconds=window)

    total_reqs = get_counter_value(HTTP_REQUESTS_TOTAL)
    total_cmds = get_counter_value(COMMAND_COUNT)

    import time

    from core.mem_stats import get_cpu_percent, get_rss_mb
    from server.app import MANAGER, REPOS, SERVER_CLOCK

    # Check if app context is available (it should be, except maybe in tests)
    system_stats = {}
    active_users = []

    try:
        conn = request.app[REPOS].conn

        async with conn.execute(
            "SELECT SUM(play_count) as total_plays, COUNT(*) as total_tracks FROM tracks"
        ) as cursor:
            track_row = await cursor.fetchone()
            songs_played = track_row["total_plays"] if track_row and track_row["total_plays"] else 0
            total_tracks = track_row["total_tracks"] if track_row else 0

        # Katalog Radio Mode (tabel `songs`, seed per-artist) -- BEDA dari
        # `tracks` di atas: `tracks` cuma lagu yang sudah pernah benar-benar
        # diputar/di-cache, sedangkan `songs` adalah seluruh katalog yang
        # dikenal sistem lewat radio seed, belum tentu semuanya pernah
        # dimainkan. Ditambahkan sebagai metrik terpisah, bukan pengganti.
        async with conn.execute("SELECT COUNT(*) as total_songs FROM songs") as cursor:
            songs_row = await cursor.fetchone()
            total_songs = songs_row["total_songs"] if songs_row else 0

        async with conn.execute("SELECT COUNT(*) as total_artists FROM artists") as cursor:
            artist_row = await cursor.fetchone()
            total_artists = artist_row["total_artists"] if artist_row else 0

        system_stats = {
            "cpu_percent": get_cpu_percent(),
            "ram_mb": get_rss_mb(),
            "songs_played": songs_played,
            "total_tracks": total_tracks,
            "total_songs": total_songs,
            "total_artists": total_artists,
            "uptime_seconds": request.app[SERVER_CLOCK].uptime_seconds,
        }

        manager = request.app[MANAGER]
        now = time.monotonic()
        for ws, info in manager.client_ips.items():
            if isinstance(info, str):
                ip = info
                ua = ""
                referer = ""
            else:
                ip = info.get("ip", "Unknown")
                ua = info.get("user_agent", "")
                referer = info.get("referer", "")

            connected_at = manager.connected_at.get(ws)
            duration = int(now - connected_at) if connected_at else 0
            # uid (client_uid, lihat server/handlers/ws_chat.py) baru ada
            # setelah koneksi ini mengirim command chat pertamanya --
            # normalnya sudah terisi begitu client terhubung (client.js
            # otomatis fetch riwayat chat saat connect), tapi bisa None
            # sesaat setelah koneksi baru dibuka. ip TETAP ditampilkan ke
            # admin sebagai info (identifikasi device secara manual), tapi
            # uid yang dipakai sebagai kunci routing chat -- lihat catatan
            # di ws_chat.py kenapa ip sendiri tidak reliable untuk itu.
            uid = manager.client_uids.get(ws)
            active_users.append(
                {"ip": ip, "uid": uid, "user_agent": ua, "referer": referer, "duration": duration}
            )
    except (KeyError, Exception) as e:
        import structlog

        structlog.get_logger().error("stats_appkey_error", error=str(e))

    response_data = {
        "log_stats": log_stats,
        "system_stats": system_stats,
        "active_users": active_users,
        "metrics": {"http_requests_total": total_reqs, "command_count": total_cmds},
        "available_categories": list(ALL_CATEGORIES),
    }
    return web.json_response(response_data)
