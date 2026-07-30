"""
Module: server.handlers.context

Purpose:
    Shared, typed accessors for values stashed on `request.app[...]`.
    Generic framework keys are re-exported from lunawave_framework.
"""

from typing import TYPE_CHECKING
from aiohttp import web

from lunawave_framework.core.routing.context import (
    get_command_bus,
    get_manager,
    get_server_clock,
    get_sessions,
    get_admin_account,
    COMMAND_BUS,
    MANAGER,
    SERVER_CLOCK,
    SESSIONS,
    ADMIN_ACCOUNT,
)

from core.ports import MediaExtractorPort, TrackRepositoryPort
from core.state import AppState

from server.app import (
    PLAYBACK_CONTROLLER,
    REPOS,
    CONN,
    TRACKS,
    STATE,
    YTDLP,
)

if TYPE_CHECKING:
    from engine.playback.controller import PlaybackController
    from persistence import Repositories

def get_repos(request: web.Request) -> "Repositories":
    return request.app[REPOS]

def get_tracks_repo(request: web.Request) -> TrackRepositoryPort:
    return request.app[TRACKS]

def get_conn(request: web.Request):
    return request.app[CONN]

def get_state(request: web.Request) -> AppState:
    return request.app[STATE]

def get_ytdlp(request: web.Request) -> MediaExtractorPort:
    return request.app[YTDLP]

def get_playback_controller(request: web.Request) -> "PlaybackController":
    return request.app[PLAYBACK_CONTROLLER]
