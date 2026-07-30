"""
Module: server.broadcast_service

Purpose:
    Provide typed broadcast helpers to push specific message types (like state,
    lyrics, progress) to all connected WebSocket clients.
    Inherits from the framework's generic BroadcastService.
"""

import time

from core.state import AppState
from lunawave_framework.core.routing.connection_manager import ConnectionManager
from lunawave_framework.core.routing.broadcast import BroadcastService as BaseBroadcastService
from server.serializers import state_to_dict

class BroadcastService(BaseBroadcastService):
    def __init__(self, manager: ConnectionManager):
        super().__init__(manager)

    async def broadcast_state(self, state: AppState, include_lyrics: bool = False):
        await self.broadcast(
            "state",
            state_to_dict(state, include_lyrics=include_lyrics)
        )

    async def broadcast_progress(self, position: float, status_name: str):
        await self.broadcast(
            "progress",
            {
                "position": position,
                "status": status_name,
                "server_ts": time.time(),
            }
        )

    async def broadcast_lyrics(self, state: AppState):
        await self.broadcast(
            "lyrics",
            {
                "lyrics_lines": list(state.lyrics_lines),
                "lyrics_timestamps": list(state.lyrics_timestamps),
                "lyrics_index": state.lyrics_index,
                "lyrics_offset": state.lyrics_offset,
                "lyrics_loading": getattr(state, "lyrics_loading", False),
            }
        )

    async def broadcast_log(self, message: str):
        await self.broadcast("log", message)

    async def broadcast_download_progress(self, progress: float):
        await self.broadcast("download_progress", progress)
