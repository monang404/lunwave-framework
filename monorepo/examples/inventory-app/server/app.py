import asyncio
from aiohttp import web
from lunawave_framework.core.routing.app import create_framework_app
from lunawave_framework.core.lifecycle.clock import ServerClock
from lunawave_framework.core.routing.bus import CommandBus
from lunawave_framework.core.routing.connection_manager import SESSIONS
from lunawave_framework.core.storage.admin_account import AdminAccountManager

async def init_app():
    clock = ServerClock()
    bus = CommandBus()
    sessions = {}
    
    # Needs db
    admin_mgr = AdminAccountManager(None)

    app, manager, ws_router = create_framework_app(
        command_bus=bus,
        server_clock=clock,
        sessions=sessions,
        admin_account=admin_mgr
    )

    app.router.add_get("/", lambda req: web.Response(text="Hello from inventory-app"))
    return app

if __name__ == "__main__":
    web.run_app(init_app(), port=8080)
