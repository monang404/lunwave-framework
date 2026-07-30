#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 3 of the framework extraction (see docs/extraction/ and
docs/adr/0013-core-domain-split.md) moved this module (100% music-domain
command constants) to music.domain.commands. This file exists purely so
existing imports keep working unchanged:

    from core.commands import CMD_PLAY_TRACK, CMD_TOGGLE_PAUSE, ...

Also re-exported via wildcard from core/command_bus.py, matching the
pre-Phase-3 behavior where command_bus.py did `from core.commands import *`
itself.
"""

from music.domain.commands import (
    CMD_CANCEL_DOWNLOAD,
    CMD_DOWNLOAD,
    CMD_LYRICS_OFFSET,
    CMD_NEXT,
    CMD_PLAY_TRACK,
    CMD_PREV,
    CMD_QUEUE_ADD,
    CMD_QUEUE_REMOVE,
    CMD_QUEUE_REORDER,
    CMD_QUEUE_REPLACE,
    CMD_QUEUE_SELECT,
    CMD_QUIT,
    CMD_RADIO_RANDOMIZE,
    CMD_SEEK,
    CMD_SET_CROSSFADE,
    CMD_SET_LOOP,
    CMD_SET_LOUDNESS_NORMALIZATION,
    CMD_SET_MODE,
    CMD_SET_OUTPUT,
    CMD_SET_SLEEP_TIMER,
    CMD_SET_SPEED,
    CMD_SET_SPONSORBLOCK,
    CMD_STOP,
    CMD_TOGGLE_PAUSE,
    CMD_VOLUME_DOWN,
    CMD_VOLUME_SET,
    CMD_VOLUME_UP,
)

__all__ = [
    "CMD_PLAY_TRACK",
    "CMD_TOGGLE_PAUSE",
    "CMD_NEXT",
    "CMD_PREV",
    "CMD_STOP",
    "CMD_SEEK",
    "CMD_VOLUME_UP",
    "CMD_VOLUME_DOWN",
    "CMD_VOLUME_SET",
    "CMD_DOWNLOAD",
    "CMD_CANCEL_DOWNLOAD",
    "CMD_SET_MODE",
    "CMD_SET_OUTPUT",
    "CMD_SET_SPONSORBLOCK",
    "CMD_SET_LOUDNESS_NORMALIZATION",
    "CMD_SET_CROSSFADE",
    "CMD_QUEUE_SELECT",
    "CMD_QUEUE_ADD",
    "CMD_QUEUE_REPLACE",
    "CMD_QUEUE_REMOVE",
    "CMD_QUEUE_REORDER",
    "CMD_RADIO_RANDOMIZE",
    "CMD_LYRICS_OFFSET",
    "CMD_SET_SLEEP_TIMER",
    "CMD_SET_SPEED",
    "CMD_SET_LOOP",
    "CMD_QUIT",
]
