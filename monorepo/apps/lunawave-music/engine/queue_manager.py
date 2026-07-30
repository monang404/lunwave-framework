"""
Module: engine.queue_manager

Purpose:
    Advance playback to the next track in the user queue when called by
    PlaybackController at track end.

Responsibilities:
    - Pop the next track from state.queue and delegate to play_track().
    - Set status to IDLE and broadcast QueueUpdatedEvent when the queue
      is empty.

Depends on:
    - core.events
    - core.state
    - engine.playback

Subscribes to:
    None

Publishes:
    QueueUpdatedEvent

Thread Safety:
    Worker thread (async; called from PlaybackController._lock).
"""

from typing import TYPE_CHECKING

from core.events import QueueUpdatedEvent
from core.state import PlayerStatus

if TYPE_CHECKING:
    from engine.playback import PlaybackController


class QueueMode:
    """
    Purpose: Mengelola playback dari user queue.
    Subscribes to: (tidak ada — dipanggil oleh PlaybackController)
    Publishes: QueueUpdatedEvent
    """

    async def next(self, controller: "PlaybackController") -> None:
        """Dipanggil PlaybackController saat track berakhir di QUEUE mode."""
        loop_mode = getattr(controller.state, "loop_mode", "off")

        if loop_mode == "track" and controller.state.current_track:
            await controller.play_track(controller.state.current_track)
            return

        if not controller.state.queue:
            controller.state.status = PlayerStatus.IDLE
            controller.state.current_track = None
            await controller.bus.publish(QueueUpdatedEvent())
            return

        track = controller.state.queue.popleft()
        if loop_mode == "queue":
            controller.state.queue.append(track)

        await controller.play_track(track)
