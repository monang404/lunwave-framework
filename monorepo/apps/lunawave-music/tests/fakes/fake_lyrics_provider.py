"""
Module: tests.fakes.fake_lyrics_provider

Purpose:
    Provides mock lyrics for testing purposes.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.ports

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""

from core.ports import LyricsProvider


class FakeLyricsProvider(LyricsProvider):
    def __init__(self, lyrics=None):
        self._lyrics = lyrics or []

    async def get_lyrics(self, title: str, artist: str) -> list:
        return self._lyrics
