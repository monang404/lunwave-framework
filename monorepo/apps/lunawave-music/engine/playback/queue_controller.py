"""
Module: engine.playback.queue_controller

Purpose:
    Menangani command CMD_QUEUE_* (select/remove/add/replace/reorder) dan
    advance-to-next (lanjut ke lagu berikutnya, baik mode QUEUE maupun
    RADIO). Diekstrak dari PlaybackController (roadmap IMPLEMENTATION_PLAN.md
    §2.3, task T2.3.1) agar controller.py tetap ramping.

Responsibilities:
    - Delegasi manipulasi queue ke QueueOps (persist state.queue via lock).
    - Catat completion/skip lagu ke DB untuk artist-bandit sebelum advance.
    - Pilih next() dari queue_mode atau radio_mode sesuai playback_mode.

Depends on:
    - core.state, core.task_utils

Subscribes to:
    None (dipanggil langsung oleh PlaybackController / CommandRouter)

Publishes:
    None langsung (event dipublish oleh QueueOps yang dipanggil)

Thread Safety:
    Main thread (async event loop).
"""

from core.events import QueueUpdatedEvent
from core.state import PlaybackMode, TrackInfo
from core.task_utils import safe_create_task


class QueueController:
    """
    Operasi command queue dan advance-to-next. Dipanggil oleh PlaybackController.
    """

    def __init__(self, controller):
        # Simpan referensi controller (pola sama seperti TrackEndedOps) karena
        # method di sini butuh akses ke banyak state controller: self.state,
        # self.bus, self._queue_ops, self.resolver, self.queue_mode,
        # self.radio_mode, self.play_track.
        self.controller = controller

    async def on_queue_select(self, index: int):
        c = self.controller
        track = await c._queue_ops.queue_select(index)
        if track:
            if c.state.playback_mode == PlaybackMode.RADIO:
                await c.radio_mode.on_deactivated()
                c.state.playback_mode = PlaybackMode.QUEUE
                await c.bus.publish(QueueUpdatedEvent())
            await c.play_track(track)

    async def on_queue_remove(self, index: int):
        await self.controller._queue_ops.remove_track(index)

    async def on_queue_add(self, track: TrackInfo):
        await self.controller._queue_ops.add_track(track)

    async def on_queue_replace(self, tracks: list[TrackInfo]):
        await self.controller._queue_ops.replace_queue(tracks)

    async def on_queue_reorder(self, data: dict):
        from_index = data.get("from_index")
        to_index = data.get("to_index")
        if from_index is not None and to_index is not None:
            await self.controller._queue_ops.reorder(from_index, to_index)

    async def advance_to_next(self):
        c = self.controller
        # Track Completion/Skip for Bandit (Phase 5)
        if c.state.current_track and c.state.duration > 0:
            if c.state.position >= c.state.duration * 0.9:
                safe_create_task(c.resolver.db.record_completion(c.state.current_track.artist))
            else:
                safe_create_task(c.resolver.db.record_skip(c.state.current_track.artist))

        if c.state.playback_mode == PlaybackMode.QUEUE:
            await c.queue_mode.next(c)
        else:
            await c.radio_mode.next(c)
