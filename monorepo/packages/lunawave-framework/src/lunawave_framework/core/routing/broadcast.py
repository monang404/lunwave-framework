"""
Module: lunawave_framework.core.routing.broadcast

Purpose:
    Provide typed broadcast helpers that wrap ConnectionManager to push
    messages to all connected WebSocket clients. Base generic class.
"""

from lunawave_framework.core.routing.connection_manager import ConnectionManager

class BroadcastService:
    def __init__(self, manager: ConnectionManager):
        self.manager = manager

    async def broadcast(self, message_type: str, data: any):
        """Generic method to broadcast a message payload to all clients."""
        await self.manager.broadcast(
            {
                "type": message_type,
                "data": data,
            }
        )
