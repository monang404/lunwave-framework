"""
Module: server.handlers.websocket

Purpose:
    Register music domain WebSocket handlers and hooks onto the framework's WsRouter.
"""

import json

import structlog

import config
from core.log_categories import LC_COMMAND
from lunawave_framework.core.routing.auth import require_auth
from lunawave_framework.core.routing.context import get_manager
from server.handlers import get_playback_controller, get_repos, get_state, get_ytdlp
from server.handlers.context import get_command_bus
from server.handlers.ws_cache import handle_cache_command
from server.handlers.ws_chat import handle_chat_command
from server.handlers.ws_discovery import handle_discovery_command
from server.handlers.ws_download import handle_download_command
from server.handlers.ws_log_stream import handle_log_stream_command
from server.handlers.ws_playback import handle_playback_command
from server.handlers.ws_queue import handle_queue_command
from server.handlers.ws_schemas import WsValidationError
from server.middleware import check_rate_limit
from server.serializers import state_to_dict

logger = structlog.get_logger(component="ws.handler")

PLAYBACK_CMDS = {
    "play_track", "toggle_pause", "next", "prev", "stop", "seek", "set_mode", 
    "set_output", "lyrics_offset", "set_sponsorblock", "radio_randomize", 
    "volume_up", "volume_down", "volume_set", "set_sleep_timer", "set_speed", 
    "set_loop", "set_crossfade", "set_loudness_normalization"
}
QUEUE_CMDS = {
    "queue_select", "queue_remove", "queue_add", "queue_reorder", 
    "enqueue_artist_songs", "enqueue_genre_songs"
}
DISCOVERY_CMDS = {"search", "discover", "get_artist_detail", "discover_search"}
DOWNLOAD_CMDS = {"download", "download_confirm_overwrite", "cancel_download", "delete_download"}
CACHE_CMDS = {"get_cache_size", "clear_cache"}
CHAT_CMDS = {"send_chat", "get_chat_history"}


async def on_ws_connect(ws, request):
    state = get_state(request)
    get_playback_controller(request) # Ensure controller is fetched
    await ws.send_str(
        json.dumps(
            {
                "type": "state",
                "data": state_to_dict(state, include_lyrics=True),
            },
            ensure_ascii=False,
        )
    )

async def music_ws_dispatcher(action: str, data: dict, ws, request, now: float):
    manager = get_manager(request)
    client_ip = request.remote
    is_admin = require_auth(manager, ws)

    if action not in CHAT_CMDS and not is_admin:
        await ws.send_str(
            json.dumps({"type": "error", "data": "Akses ditolak. Silakan login sebagai Admin."})
        )
        return

    if not await check_rate_limit(manager, client_ip, now):
        await ws.send_str(
            json.dumps({"type": "error", "data": "Terlalu banyak permintaan. Mohon tunggu sesaat."})
        )
        return

    repos = get_repos(request)
    ytdlp = get_ytdlp(request)
    command_bus = get_command_bus(request)
    state = get_state(request)

    try:
        if action in PLAYBACK_CMDS:
            await handle_playback_command(action, data, command_bus)
        elif action in QUEUE_CMDS:
            await handle_queue_command(action, data, repos.artists, repos.genres, command_bus)
        elif action in DISCOVERY_CMDS:
            await handle_discovery_command(action, data, ytdlp, repos.discover, ws)
        elif action in DOWNLOAD_CMDS:
            await handle_download_command(
                action, data, repos.tracks, repos.discover, manager, state, command_bus, ws
            )
        elif action in CACHE_CMDS:
            await handle_cache_command(action, data, ws, repos, manager, state)
        elif action in CHAT_CMDS:
            if action == "send_chat":
                chat_key = manager.client_uids.get(ws) or client_ip
                from server.middleware import check_chat_rate_limit

                if not await check_chat_rate_limit(manager, chat_key, now):
                    await ws.send_str(
                        json.dumps(
                            {
                                "type": "error",
                                "data": "Terlalu banyak pesan chat. Mohon tunggu sesaat.",
                            }
                        )
                    )
                    return
            await handle_chat_command(action, data, ws, repos, manager, is_admin, client_ip)
        elif action == "log_tail":
            await handle_log_stream_command(data.get("action"), ws)
    except WsValidationError as e:
        try:
            await ws.send_str(json.dumps({"type": "error", "data": str(e)}))
        except Exception:
            pass
    except Exception as e:
        logger.error(
            "ws_command_handling_failed",
            category=LC_COMMAND,
            command_action=action,
            error_type=type(e).__name__,
            error=str(e),
            exc_info=True,
        )
        try:
            await ws.send_str(
                json.dumps(
                    {
                        "type": "error",
                        "data": str(e)
                        if config.DEBUG_EXPOSE_ERRORS
                        else "Terjadi kesalahan saat memproses permintaan.",
                    }
                )
            )
        except Exception:
            pass

def register_music_ws_handlers(ws_router):
    ws_router.register_on_connect(on_ws_connect)
    
    all_actions = (
        PLAYBACK_CMDS | QUEUE_CMDS | DISCOVERY_CMDS | 
        DOWNLOAD_CMDS | CACHE_CMDS | CHAT_CMDS | {"log_tail"}
    )
    for action in all_actions:
        ws_router.register_handler(action, music_ws_dispatcher)
