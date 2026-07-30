#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 3 of the framework extraction (see docs/extraction/ and
docs/adr/0013-core-domain-split.md, Decision 3) split this module: the
generic CommandBus dispatcher moved to
lunawave_framework.core.kernel.command_bus (which no longer re-exports
CMD_* constants -- a generic dispatcher must not depend on app-domain
vocabulary). This shim recombines the two, exactly reproducing the
pre-Phase-3 namespace so existing call sites keep working unchanged:

    from core.command_bus import CommandBus, CMD_PLAY_TRACK, CMD_TOGGLE_PAUSE, ...
"""

from lunawave_framework.core.kernel.command_bus import CommandBus
from music.domain.commands import *  # noqa: F401, F403 -- preserves the pre-Phase-3 wildcard re-export

__all__ = [
    "CommandBus",
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
