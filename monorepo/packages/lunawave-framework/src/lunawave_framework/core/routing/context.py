"""
Module: lunawave_framework.core.routing.context

Purpose:
    Shared, typed accessors for values stashed on `request.app[...]` by
    the framework.

Responsibilities:
    - Provide get_*() helper functions for framework dependencies.
    - Export web.AppKey constants.
"""

from typing import TYPE_CHECKING
from aiohttp import web

if TYPE_CHECKING:
    from lunawave_framework.core.kernel.command_bus import CommandBus
    from lunawave_framework.core.kernel.server_clock import ServerClock
    from lunawave_framework.core.routing.connection_manager import ConnectionManager
    from lunawave_framework.core.storage.session_repo import SessionRepository
    from lunawave_framework.core.storage.admin_account_repo import AdminAccountRepository

# Framework-level AppKeys
MANAGER: web.AppKey["ConnectionManager"] = web.AppKey("manager")
SERVER_CLOCK: web.AppKey["ServerClock"] = web.AppKey("server_clock")
COMMAND_BUS: web.AppKey["CommandBus"] = web.AppKey("command_bus")
SESSIONS: web.AppKey["SessionRepository"] = web.AppKey("sessions")
ADMIN_ACCOUNT: web.AppKey["AdminAccountRepository"] = web.AppKey("admin_account")


def get_manager(request: web.Request) -> "ConnectionManager":
    return request.app[MANAGER]

def get_server_clock(request: web.Request) -> "ServerClock":
    return request.app[SERVER_CLOCK]

def get_command_bus(request: web.Request) -> "CommandBus":
    return request.app[COMMAND_BUS]

def get_sessions(request: web.Request) -> "SessionRepository":
    return request.app.get(SESSIONS)

def get_admin_account(request: web.Request) -> "AdminAccountRepository":
    return request.app.get(ADMIN_ACCOUNT)
