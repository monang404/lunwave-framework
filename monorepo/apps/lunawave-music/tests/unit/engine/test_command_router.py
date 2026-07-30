"""tests/unit/engine/test_command_router.py — mirrors engine/command_router.py

CommandRouter registers 19 handlers (16 playback + 3 volume) onto the
*module-level* `command_bus` singleton (from core.command_bus). To keep
each test isolated we monkeypatch `engine.command_router.command_bus` to
a fresh `CommandBus()` instance per test, instead of sharing the real
process-wide singleton.

Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

import pytest

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
    CMD_SET_MODE,
    CMD_SET_OUTPUT,
    CMD_SET_SPONSORBLOCK,
    CMD_STOP,
    CMD_TOGGLE_PAUSE,
    CMD_VOLUME_DOWN,
    CMD_VOLUME_SET,
    CMD_VOLUME_UP,
    CommandBus,
)
from engine.command_router import CommandRouter


class FakeController:
    """Records every _on_* call; mixes sync and async return values to
    exercise both branches of CommandRouter._route()."""

    def __init__(self):
        self.calls = []

    def _on_cmd_play_track(self, data):
        self.calls.append(("play_track", data))
        return "sync-result"

    async def _on_cmd_toggle_pause(self, data):
        self.calls.append(("toggle_pause", data))
        return "async-result"

    def _on_next(self, data):
        self.calls.append(("next", data))

    def _on_prev(self, data):
        self.calls.append(("prev", data))

    def _on_stop(self, data):
        self.calls.append(("stop", data))

    def _on_seek(self, data):
        self.calls.append(("seek", data))

    def _on_set_mode(self, data):
        self.calls.append(("set_mode", data))

    def _on_queue_select(self, data):
        self.calls.append(("queue_select", data))

    def _on_queue_remove(self, data):
        self.calls.append(("queue_remove", data))

    def _on_queue_add(self, data):
        self.calls.append(("queue_add", data))

    def _on_queue_replace(self, data):
        self.calls.append(("queue_replace", data))

    def _on_queue_reorder(self, data):
        self.calls.append(("queue_reorder", data))

    def _on_radio_randomize(self, data):
        self.calls.append(("radio_randomize", data))

    def _on_set_output(self, data):
        self.calls.append(("set_output", data))

    def _on_set_sponsorblock(self, data):
        self.calls.append(("set_sponsorblock", data))

    def _on_lyrics_offset(self, data):
        self.calls.append(("lyrics_offset", data))


class FakeVolumeService:
    def __init__(self):
        self.calls = []

    def _on_volume_up(self, data):
        self.calls.append(("volume_up", data))

    async def _on_volume_down(self, data):
        self.calls.append(("volume_down", data))

    def _on_volume_set(self, data):
        self.calls.append(("volume_set", data))


@pytest.fixture
def isolated_bus():
    """Create a fresh CommandBus instance per test."""
    return CommandBus()


@pytest.fixture
def controller():
    return FakeController()


@pytest.fixture
def volume_service():
    return FakeVolumeService()


@pytest.fixture
def router(isolated_bus, controller, volume_service):
    return CommandRouter(
        playback_controller=controller, volume_service=volume_service, command_bus=isolated_bus
    )


PLAYBACK_COMMANDS = [
    (CMD_PLAY_TRACK, "play_track"),
    (CMD_TOGGLE_PAUSE, "toggle_pause"),
    (CMD_NEXT, "next"),
    (CMD_PREV, "prev"),
    (CMD_STOP, "stop"),
    (CMD_SEEK, "seek"),
    (CMD_SET_MODE, "set_mode"),
    (CMD_QUEUE_SELECT, "queue_select"),
    (CMD_QUEUE_REMOVE, "queue_remove"),
    (CMD_QUEUE_ADD, "queue_add"),
    (CMD_QUEUE_REPLACE, "queue_replace"),
    (CMD_QUEUE_REORDER, "queue_reorder"),
    (CMD_RADIO_RANDOMIZE, "radio_randomize"),
    (CMD_SET_OUTPUT, "set_output"),
    (CMD_SET_SPONSORBLOCK, "set_sponsorblock"),
    (CMD_LYRICS_OFFSET, "lyrics_offset"),
]

VOLUME_COMMANDS = [
    (CMD_VOLUME_UP, "volume_up"),
    (CMD_VOLUME_DOWN, "volume_down"),
    (CMD_VOLUME_SET, "volume_set"),
]


def test_init_registers_all_19_commands(router, isolated_bus):
    total = len(PLAYBACK_COMMANDS) + len(VOLUME_COMMANDS)
    assert total == 19
    for cmd_name, _ in PLAYBACK_COMMANDS + VOLUME_COMMANDS:
        assert cmd_name in isolated_bus._handlers


@pytest.mark.parametrize("cmd_name,expected_tag", PLAYBACK_COMMANDS)
async def test_playback_command_routes_to_controller_with_data(
    router, isolated_bus, controller, cmd_name, expected_tag
):
    payload = {"marker": expected_tag}
    await isolated_bus.execute(cmd_name, payload)
    assert controller.calls == [(expected_tag, payload)]


@pytest.mark.parametrize("cmd_name,expected_tag", VOLUME_COMMANDS)
async def test_volume_command_routes_to_volume_service_with_data(
    router, isolated_bus, volume_service, cmd_name, expected_tag
):
    payload = {"marker": expected_tag}
    await isolated_bus.execute(cmd_name, payload)
    assert volume_service.calls == [(expected_tag, payload)]


async def test_route_awaits_coroutine_results_and_returns_them(router, isolated_bus):
    result = await isolated_bus.execute(CMD_TOGGLE_PAUSE, None)
    assert result == "async-result"


async def test_route_returns_sync_results_directly(router, isolated_bus):
    result = await isolated_bus.execute(CMD_PLAY_TRACK, None)
    assert result == "sync-result"


async def test_route_volume_awaits_coroutine_results(router, isolated_bus, volume_service):
    # _on_volume_down is async on FakeVolumeService — must not raise and
    # must actually run to completion before execute() returns.
    await isolated_bus.execute(CMD_VOLUME_DOWN, {"x": 1})
    assert volume_service.calls == [("volume_down", {"x": 1})]


def test_registering_a_second_router_on_the_same_bus_raises_duplicate_error(
    router, isolated_bus, controller, volume_service
):
    with pytest.raises(RuntimeError):
        CommandRouter(
            playback_controller=controller, volume_service=volume_service, command_bus=isolated_bus
        )
