"""
Module: server.handlers.ws_playback

Purpose:
    WebSocket handler for processing playback control commands.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.command_bus
    - core.state
    - server.serializers

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

import structlog

from core.command_bus import (
    CMD_LYRICS_OFFSET,
    CMD_NEXT,
    CMD_PLAY_TRACK,
    CMD_PREV,
    CMD_RADIO_RANDOMIZE,
    CMD_SEEK,
    CMD_SET_CROSSFADE,
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
from core.state import AudioOutput, PlaybackMode
from server.handlers.ws_schemas import (
    LyricsOffsetPayload,
    SetSleepTimerPayload,
    SetSpeedPayload,
    VolumeSetPayload,
)
from server.serializers import dict_to_track

logger = structlog.get_logger(component="ws.playback")


async def handle_playback_command(action: str, data: dict, command_bus):
    if action == "play_track":
        track = dict_to_track(data)
        if track:
            await command_bus.execute(CMD_PLAY_TRACK, track)

    elif action == "toggle_pause":
        await command_bus.execute(CMD_TOGGLE_PAUSE)

    elif action == "next":
        await command_bus.execute(CMD_NEXT, data)

    elif action == "prev":
        await command_bus.execute(CMD_PREV, data)

    elif action == "stop":
        await command_bus.execute(CMD_STOP)

    elif action == "seek":
        position = data.get("position", 0)
        await command_bus.execute(CMD_SEEK, float(position))

    elif action == "volume_up":
        await command_bus.execute(CMD_VOLUME_UP)

    elif action == "volume_down":
        await command_bus.execute(CMD_VOLUME_DOWN)

    elif action == "volume_set":
        payload = VolumeSetPayload.parse(data)
        await command_bus.execute(CMD_VOLUME_SET, {"volume": payload.volume})

    elif action == "set_mode":
        mode_str = data.get("mode", "queue").upper()
        mode = PlaybackMode.RADIO if mode_str == "RADIO" else PlaybackMode.QUEUE
        await command_bus.execute(CMD_SET_MODE, mode)

    elif action == "set_output":
        output_str = data.get("output", "device")
        output_val = AudioOutput.BROWSER if output_str == "browser" else AudioOutput.DEVICE
        await command_bus.execute(CMD_SET_OUTPUT, output_val)

    elif action == "set_sponsorblock":
        enabled = data.get("enabled", True)
        await command_bus.execute(CMD_SET_SPONSORBLOCK, bool(enabled))

    elif action == "radio_randomize":
        seed_artist = data.get("seed_artist")
        await command_bus.execute(CMD_RADIO_RANDOMIZE, {"seed_artist": seed_artist})

    elif action == "lyrics_offset":
        payload = LyricsOffsetPayload.parse(data)
        await command_bus.execute(CMD_LYRICS_OFFSET, {"offset": payload.offset})

    elif action == "set_crossfade":
        enabled = data.get("enabled", False)
        await command_bus.execute(CMD_SET_CROSSFADE, {"enabled": bool(enabled)})

    elif action == "set_sleep_timer":
        from core.command_bus import CMD_SET_SLEEP_TIMER

        payload = SetSleepTimerPayload.parse(data)
        await command_bus.execute(CMD_SET_SLEEP_TIMER, {"minutes": payload.minutes})

    elif action == "set_speed":
        from core.command_bus import CMD_SET_SPEED

        payload = SetSpeedPayload.parse(data)
        await command_bus.execute(CMD_SET_SPEED, {"speed": payload.speed})

    elif action == "set_loop":
        from core.command_bus import CMD_SET_LOOP

        mode = data.get("mode", "off")
        await command_bus.execute(CMD_SET_LOOP, {"mode": mode})

    elif action == "set_loudness_normalization":
        enabled = data.get("enabled", False)
        await command_bus.execute(CMD_SET_LOUDNESS_NORMALIZATION, bool(enabled))
