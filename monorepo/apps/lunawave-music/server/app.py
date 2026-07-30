"""
Module: server.app

Purpose:
    Create and configure the aiohttp web application with all routes,
    services, and EventBus listeners wired together.
"""

import asyncio
from pathlib import Path

import structlog
from aiohttp import web

from core.command_bus import CommandBus
from core.log_categories import LC_LIFECYCLE
from core.ports import MediaExtractorPort
from core.server_clock import server_clock
from engine.playback.controller import PlaybackController
from persistence import Repositories

# Framework AppKeys and bootstrap
from lunawave_framework.core.routing.app import create_framework_app
from lunawave_framework.core.routing.context import (
    COMMAND_BUS,
    MANAGER,
    SERVER_CLOCK,
)

logger = structlog.get_logger(component="server.app")
STATIC_DIR = Path(__file__).parent.parent / "web" / "static"

# Music AppKeys
PLAYBACK_CONTROLLER: web.AppKey[PlaybackController] = web.AppKey("playback_controller", PlaybackController)
STATE: web.AppKey = web.AppKey("state")
YTDLP: web.AppKey[MediaExtractorPort] = web.AppKey("ytdlp", MediaExtractorPort)
REPOS: web.AppKey[Repositories] = web.AppKey("repos", Repositories)
CONN: web.AppKey = web.AppKey("conn")
TRACKS: web.AppKey = web.AppKey("tracks")

def create_app(
    playback_controller: PlaybackController,
    ytdlp: MediaExtractorPort,
    repos: Repositories,
    command_bus: CommandBus,
) -> web.Application:
    from server.handlers.audio_stream_handler import serve_stream
    from server.handlers.http import health_check, serve_client, serve_index, serve_metrics
    from server.handlers.log_dashboard import get_logs_stats, get_logs_tail, serve_log_dashboard
    from server.middleware.compression import make_static_handler
    from server.middleware.traffic import traffic_middleware
    from server.handlers.websocket import register_music_ws_handlers
    from server.broadcast_service import BroadcastService
    from server.handlers.event_listeners import setup_event_listeners
    from services.stream_prefetch import StreamPrefetchService
    from server.handlers.ws_log_stream import cleanup_log_viewer

    # Ensure repos are initialized
    if repos.tracks is None or repos.sessions is None or repos.admin_account is None:
        raise RuntimeError("repos.init() must be called before create_app()")

    # Bootstrap the generic framework app
    app, manager, ws_router = create_framework_app(
        command_bus=command_bus,
        server_clock=server_clock,
        sessions=repos.sessions,
        admin_account=repos.admin_account,
    )
    app.middlewares.append(traffic_middleware)

    # Attach music specific state
    app[PLAYBACK_CONTROLLER] = playback_controller
    app[STATE] = playback_controller.state
    app[YTDLP] = ytdlp
    app[REPOS] = repos
    app[CONN] = repos.conn
    app[TRACKS] = repos.tracks

    # Hook up cleanup and music handlers to generic router
    manager.register_on_disconnect(cleanup_log_viewer)
    register_music_ws_handlers(ws_router)

    # Initialize music specific services
    prefetch_service = StreamPrefetchService(repos.tracks, ytdlp)
    broadcast_service = BroadcastService(manager)
    setup_event_listeners(playback_controller, prefetch_service, broadcast_service)

    async def serve_favicon(request):
        return web.FileResponse(STATIC_DIR / "icons" / "icon-192.png")

    app.router.add_get("/", serve_client)
    app.router.add_get("/favicon.ico", serve_favicon)
    app.router.add_get("/admin", serve_index)
    app.router.add_get("/admin/", serve_index)
    app.router.add_get("/api/stream/{video_id}", serve_stream)
    app.router.add_get("/health", health_check)
    app.router.add_get("/metrics", serve_metrics)
    app.router.add_get("/admin/logs", serve_log_dashboard)
    app.router.add_get("/admin/logs/", serve_log_dashboard)
    app.router.add_get("/api/logs/tail", get_logs_tail)
    app.router.add_get("/api/logs/stats", get_logs_stats)
    app.router.add_get("/static/{path:.*}", make_static_handler(STATIC_DIR), name="static")

    return app


async def run_server(app: web.Application, host: str = "0.0.0.0", port: int = 8765):
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    try:
        await site.start()
    except Exception as e:
        logger.critical(
            "server_bind_failed",
            category=LC_LIFECYCLE,
            host=host,
            port=port,
            error_type=type(e).__name__,
            error=str(e),
        )
        raise
    logger.info(
        "web_server_started",
        category=LC_LIFECYCLE,
        host=host,
        port=port,
    )

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()
