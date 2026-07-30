"""
Module: tests.fakes.fake_sponsorblock_provider

Purpose:
    Provides mock SponsorBlock segments for testing purposes.

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

from core.ports import SponsorBlockProvider


class FakeSponsorBlockProvider(SponsorBlockProvider):
    def __init__(self, segments=None):
        self._segments = segments or []

    async def get_segments(self, video_id: str) -> list:
        return self._segments
