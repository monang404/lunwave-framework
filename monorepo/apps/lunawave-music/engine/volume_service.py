"""
Module: engine.volume_service

Purpose:
    Handle volume-related commands and apply the correct volume to mpv
    based on the active audio output mode.

Responsibilities:
    - Respond to CMD_VOLUME_UP, CMD_VOLUME_DOWN, and CMD_VOLUME_SET.
    - Suppress audio to mpv when audio_output is BROWSER.

Depends on:
    - core.event_bus
    - core.events
    - core.ports
    - core.state

Subscribes to:
    CMD_VOLUME_UP, CMD_VOLUME_DOWN, CMD_VOLUME_SET

Publishes:
    LogMessageEvent

Thread Safety:
    Worker thread (async).
"""

from core.event_bus import EventBus
from core.events import LogMessageEvent, VolumeChangedEvent
from core.ports import AudioPlayerPort
from core.state import AppState, AudioOutput

MAX_VOLUME = 100


class VolumeService:
    def __init__(self, bus: EventBus, mpv: AudioPlayerPort, state: AppState):
        self.bus = bus
        self.mpv = mpv
        self.state = state
        self.current_volume = state.volume

    async def _on_volume_up(self, _data=None):
        self.current_volume = min(MAX_VOLUME, self.current_volume + 5)
        await self._apply_volume()

    async def _on_volume_down(self, _data=None):
        self.current_volume = max(0, self.current_volume - 5)
        await self._apply_volume()

    async def _on_volume_set(self, data):
        vol = data.get("volume", 80)
        self.current_volume = max(0, min(MAX_VOLUME, int(vol)))
        await self._apply_volume()

    async def _apply_volume(self):
        if getattr(self.state, "audio_output", AudioOutput.DEVICE) == AudioOutput.BROWSER:
            await self.mpv.set_volume(0)
        else:
            await self.mpv.set_volume(self.current_volume)
        self.state.volume = self.current_volume
        await self.bus.publish(VolumeChangedEvent(volume=self.current_volume))
        await self.bus.publish(LogMessageEvent(message=f"Volume: {self.current_volume}%"))
