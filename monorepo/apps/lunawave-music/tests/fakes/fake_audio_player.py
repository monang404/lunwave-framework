"""Fake implementation of core.ports.AudioPlayerPort for tests.
Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""


class FakeAudioPlayer:
    def __init__(self):
        self.is_connected = False
        self.current_uri: str | None = None
        self.is_playing = False
        self.volume = 80
        self.position = 0.0
        self.af = ""
        self.properties = {}
        self.call_log: list[tuple] = []

    async def connect(self) -> None:
        self.call_log.append(("connect",))
        self.is_connected = True

    async def close(self) -> None:
        self.call_log.append(("close",))
        self.is_connected = False

    async def play(self, uri: str) -> None:
        self.call_log.append(("play", uri))
        self.current_uri = uri
        self.is_playing = True

    async def pause(self) -> None:
        self.call_log.append(("pause",))
        self.is_playing = False

    async def resume(self) -> None:
        self.call_log.append(("resume",))
        self.is_playing = True

    async def stop(self) -> None:
        self.call_log.append(("stop",))
        self.is_playing = False
        self.current_uri = None

    async def set_volume(self, volume: int) -> None:
        self.call_log.append(("set_volume", volume))
        self.volume = volume

    async def set_af(self, filter_str: str) -> None:
        self.call_log.append(("set_af", filter_str))
        self.af = filter_str

    async def seek(self, position: float) -> None:
        self.call_log.append(("seek", position))
        self.position = position

    async def set_property(self, prop: str, value: any) -> None:
        self.call_log.append(("set_property", prop, value))
        self.properties[prop] = value
