"""
Module: lunawave_framework.core.routing.app

Purpose:
    Provide the base aiohttp web application initialization for the framework.
"""

from aiohttp import web

from lunawave_framework.core.routing.context import (
    MANAGER,
    SERVER_CLOCK,
    COMMAND_BUS,
    SESSIONS,
    ADMIN_ACCOUNT,
)
from lunawave_framework.core.routing.connection_manager import ConnectionManager
from lunawave_framework.core.routing.websocket import WsRouter
from lunawave_framework.core.routing.setup import setup_required


def create_framework_app(
    command_bus,
    server_clock,
    sessions,
    admin_account,
) -> tuple[web.Application, ConnectionManager, WsRouter]:
    """
    Creates a base framework web application.

    Returns:
        tuple containing (app, manager, ws_router)
        The caller is expected to register routes and run the app.
    """
    app = web.Application()
    manager = ConnectionManager()
    ws_router = WsRouter()

    app[MANAGER] = manager
    app[SERVER_CLOCK] = server_clock
    app[COMMAND_BUS] = command_bus
    app[SESSIONS] = sessions
    app[ADMIN_ACCOUNT] = admin_account

    app.router.add_get("/api/setup-required", setup_required)
    app.router.add_get("/ws", ws_router.ws_handler)

    from pathlib import Path
    FRAMEWORK_STATIC_DIR = Path(__file__).parent.parent.parent / "web" / "static"
    app.router.add_static("/framework/static/", FRAMEWORK_STATIC_DIR, name="framework_static")

    return app, manager, ws_router
