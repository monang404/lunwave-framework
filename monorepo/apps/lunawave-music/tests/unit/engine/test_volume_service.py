"""tests/unit/engine/test_volume_service.py — mirrors engine/volume_service.py
Purpose:
    Auto-generated purpose.

Subscribes to:
    - LogMessageEvent

Publishes:
    None
"""

import pytest

from core.event_bus import EventBus
from core.events import LogMessageEvent
from core.state import AppState, AudioOutput
from engine.volume_service import VolumeService
from tests.fakes.fake_audio_player import FakeAudioPlayer


@pytest.fixture
def player():
    return FakeAudioPlayer()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def service(bus, player):
    state = AppState(volume=80, audio_output=AudioOutput.DEVICE)
    return VolumeService(bus=bus, mpv=player, state=state)


async def test_init_seeds_current_volume_from_state(bus, player):
    state = AppState(volume=42)
    service = VolumeService(bus=bus, mpv=player, state=state)
    assert service.current_volume == 42


async def test_volume_up_increases_by_5(service):
    await service._on_volume_up()
    assert service.current_volume == 85
    assert service.state.volume == 85


@pytest.mark.asyncio
async def test_volume_up_caps_at_100(service):
    service.current_volume = 98
    await service._on_volume_up()
    assert service.current_volume == 100
    await service._on_volume_up()
    assert service.current_volume == 100


async def test_volume_down_decreases_by_5(service):
    await service._on_volume_down()
    assert service.current_volume == 75


async def test_volume_down_floors_at_0(service):
    service.current_volume = 3
    await service._on_volume_down()
    assert service.current_volume == 0
    await service._on_volume_down()
    assert service.current_volume == 0


async def test_volume_set_applies_exact_value(service):
    await service._on_volume_set({"volume": 33})
    assert service.current_volume == 33


@pytest.mark.asyncio
async def test_volume_set_clamps_above_100(service):
    await service._on_volume_set({"volume": 999})
    assert service.current_volume == 100


async def test_volume_set_clamps_below_0(service):
    await service._on_volume_set({"volume": -50})
    assert service.current_volume == 0


async def test_volume_set_defaults_to_80_when_key_missing(service):
    await service._on_volume_set({})
    assert service.current_volume == 80


async def test_volume_set_coerces_string_numbers(service):
    await service._on_volume_set({"volume": "60"})
    assert service.current_volume == 60


async def test_apply_volume_sends_real_volume_to_mpv_when_device_output(bus, player):
    state = AppState(volume=80, audio_output=AudioOutput.DEVICE)
    service = VolumeService(bus=bus, mpv=player, state=state)
    await service._on_volume_set({"volume": 55})
    assert ("set_volume", 55) in player.call_log
    assert state.volume == 55


async def test_apply_volume_mutes_mpv_but_keeps_state_volume_when_browser_output(bus, player):
    state = AppState(volume=80, audio_output=AudioOutput.BROWSER)
    service = VolumeService(bus=bus, mpv=player, state=state)
    await service._on_volume_set({"volume": 55})
    assert ("set_volume", 0) in player.call_log
    # state.volume still reflects the intended (browser-side) volume, not 0.
    assert state.volume == 55


async def test_apply_volume_falls_back_to_device_behavior_when_state_has_no_audio_output(
    bus, player
):
    class BareState:
        volume = 80

    state = BareState()
    service = VolumeService(bus=bus, mpv=player, state=state)
    await service._on_volume_set({"volume": 40})
    assert ("set_volume", 40) in player.call_log


async def test_apply_volume_publishes_log_message_event(service, bus):
    received = []
    bus.subscribe(LogMessageEvent, lambda e: received.append(e))
    await service._on_volume_set({"volume": 20})
    assert len(received) == 1
    assert received[0].message == "Volume: 20%"
