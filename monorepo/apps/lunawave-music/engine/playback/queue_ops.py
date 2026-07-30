"""
Module: engine.playback.queue_ops

Purpose:
    Manages queue operations including adding, removing, and reordering tracks.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.events
    - core.state

Subscribes to:
    None

Publishes:
    - LogMessageEvent
    - QueueUpdatedEvent

Thread Safety:
    Main thread (async event loop).
"""

import asyncio

from core.events import LogMessageEvent, QueueUpdatedEvent
from core.state import AppState, TrackInfo


class QueueOps:
    """
    Operasi manipulasi queue. Dipanggil oleh PlaybackController.
    """

    def __init__(self, state: AppState, bus, lock: asyncio.Lock):
        self.state = state
        self.bus = bus
        self._lock = lock

    async def queue_select(self, index: int) -> TrackInfo | None:
        """Pilih lagu dari queue, pop elemen sebelumnya, kembalikan track yang dipilih (jika valid)."""
        async with self._lock:
            if 0 <= index < len(self.state.queue):
                track = self.state.queue[index]
                for _ in range(index + 1):
                    self.state.queue.popleft()
                return track
        return None

    async def add_track(self, track: TrackInfo):
        async with self._lock:
            self.state.queue.append(track)
            await self.bus.publish(QueueUpdatedEvent())
            await self.bus.publish(
                LogMessageEvent(message=f"Ditambahkan ke antrean: {track.title}")
            )

    async def remove_track(self, index: int):
        async with self._lock:
            if 0 <= index < len(self.state.queue):
                removed = self.state.queue[index]
                del self.state.queue[index]
                await self.bus.publish(QueueUpdatedEvent())
                await self.bus.publish(
                    LogMessageEvent(message=f"Dihapus dari antrean: {removed.title}")
                )

    async def replace_queue(self, tracks: list[TrackInfo]):
        async with self._lock:
            self.state.queue.clear()
            self.state.queue.extend(tracks)
            await self.bus.publish(QueueUpdatedEvent())

    async def reorder(self, from_index: int, to_index: int):
        async with self._lock:
            q = self.state.queue
            if 0 <= from_index < len(q) and 0 <= to_index < len(q):
                item = q[from_index]
                del q[from_index]
                q.insert(to_index, item)
                await self.bus.publish(QueueUpdatedEvent())
