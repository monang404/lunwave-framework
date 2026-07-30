"""
Module: engine.command_router

Purpose:
    Register all CMD_* CommandBus handlers, routing each command to the
    appropriate method on PlaybackController or VolumeService.

Responsibilities:
    - Bind every playback and volume command on instantiation.
    - Wrap handler calls with async/sync dispatch to support both types.

Depends on:
    - core.command_bus

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread only (registered once at startup).
"""

import structlog

from core.command_bus import (
    CMD_LYRICS_OFFSET,
    CMD_NEXT,
    CMD_PLAY_TRACK,
    CMD_PREV,
    CMD_QUEUE_ADD,
    CMD_QUEUE_REMOVE,
    CMD_QUEUE_REORDER,
    CMD_QUEUE_REPLACE,
    CMD_QUEUE_SELECT,
    CMD_RADIO_RANDOMIZE,
    CMD_SEEK,
    CMD_SET_LOUDNESS_NORMALIZATION,
    CMD_SET_MODE,
    CMD_SET_OUTPUT,
    CMD_SET_SPONSORBLOCK,
    CMD_STOP,
    CMD_TOGGLE_PAUSE,
    CMD_VOLUME_DOWN,
    CMD_VOLUME_SET,
    CMD_VOLUME_UP,
)

logger = structlog.get_logger(component="engine.command_router")


class CommandRouter:
    """
    Rutes Global CommandBus requests ke RoomPlaybackController yang sesuai.
    """

    def __init__(self, playback_controller, volume_service, sleep_timer=None, command_bus=None):
        self.playback_controller = playback_controller
        self.volume_service = volume_service
        self.sleep_timer = sleep_timer
        self._command_bus = command_bus

        self._command_bus.register(
            CMD_PLAY_TRACK, self._route(lambda c, data: c._on_cmd_play_track(data))
        )
        self._command_bus.register(
            CMD_TOGGLE_PAUSE, self._route(lambda c, data: c._on_cmd_toggle_pause(data))
        )
        self._command_bus.register(CMD_NEXT, self._route(lambda c, data: c._on_next(data)))
        self._command_bus.register(CMD_PREV, self._route(lambda c, data: c._on_prev(data)))
        self._command_bus.register(CMD_STOP, self._route(lambda c, data: c._on_stop(data)))
        self._command_bus.register(CMD_SEEK, self._route(lambda c, data: c._on_seek(data)))
        self._command_bus.register(CMD_SET_MODE, self._route(lambda c, data: c._on_set_mode(data)))
        self._command_bus.register(
            CMD_QUEUE_SELECT, self._route(lambda c, data: c._on_queue_select(data))
        )
        self._command_bus.register(
            CMD_QUEUE_REMOVE, self._route(lambda c, data: c._on_queue_remove(data))
        )
        self._command_bus.register(
            CMD_QUEUE_ADD, self._route(lambda c, data: c._on_queue_add(data))
        )
        self._command_bus.register(
            CMD_QUEUE_REPLACE, self._route(lambda c, data: c._on_queue_replace(data))
        )
        self._command_bus.register(
            CMD_QUEUE_REORDER, self._route(lambda c, data: c._on_queue_reorder(data))
        )
        self._command_bus.register(
            CMD_RADIO_RANDOMIZE, self._route(lambda c, data: c._on_radio_randomize(data))
        )
        self._command_bus.register(
            CMD_SET_OUTPUT, self._route(lambda c, data: c._on_set_output(data))
        )
        self._command_bus.register(
            CMD_SET_SPONSORBLOCK, self._route(lambda c, data: c._on_set_sponsorblock(data))
        )
        self._command_bus.register(
            CMD_SET_LOUDNESS_NORMALIZATION,
            self._route(lambda c, data: c._on_set_loudness_normalization(data)),
        )
        self._command_bus.register(
            CMD_LYRICS_OFFSET, self._route(lambda c, data: c._on_lyrics_offset(data))
        )

        self._command_bus.register(
            CMD_VOLUME_UP, self._route_volume(lambda v, data: v._on_volume_up(data))
        )
        self._command_bus.register(
            CMD_VOLUME_DOWN, self._route_volume(lambda v, data: v._on_volume_down(data))
        )
        self._command_bus.register(
            CMD_VOLUME_SET, self._route_volume(lambda v, data: v._on_volume_set(data))
        )

        from core.command_bus import CMD_SET_LOOP, CMD_SET_SLEEP_TIMER, CMD_SET_SPEED
        from core.commands import CMD_SET_CROSSFADE

        self._command_bus.register(
            CMD_SET_CROSSFADE, self._route(lambda c, data: c._mode_ops.set_crossfade(data))
        )
        self._command_bus.register(
            CMD_SET_SPEED, self._route(lambda c, data: c._mode_ops.set_speed(data))
        )
        self._command_bus.register(
            CMD_SET_LOOP, self._route(lambda c, data: c._mode_ops.set_loop(data))
        )

        if self.sleep_timer:
            self._command_bus.register(
                CMD_SET_SLEEP_TIMER,
                self._route_sleep(lambda s, data: s.set_timer(data.get("minutes", 0))),
            )

    def _route_sleep(self, action):
        async def handler(data):
            import asyncio

            res = action(self.sleep_timer, data)
            if asyncio.iscoroutine(res):
                return await res
            return res

        return handler

    def _route(self, action):
        async def handler(data):
            import asyncio

            res = action(self.playback_controller, data)
            if asyncio.iscoroutine(res):
                return await res
            return res

        return handler

    def _route_volume(self, action):
        async def handler(data):
            import asyncio

            res = action(self.volume_service, data)
            if asyncio.iscoroutine(res):
                return await res
            return res

        return handler
