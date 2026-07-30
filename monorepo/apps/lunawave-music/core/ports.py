#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 3 of the framework extraction (see docs/extraction/ and
docs/adr/0013-core-domain-split.md) moved every Protocol in this module to
music.domain.ports -- including SessionRepositoryPort, which is
generic-shaped but was deliberately kept alongside the other (music-domain)
ports rather than split into the framework now; see ADR 0013 Decision 2.
This file exists purely so existing imports keep working unchanged:

    from core.ports import AudioPlayerPort, TrackRepositoryPort, ...
"""

from music.domain.ports import (
    ArtistRepositoryPort,
    AudioPlayerPort,
    DatabasePort,
    DiscoverRepositoryPort,
    LibraryRepositoryPort,
    LyricsProvider,
    MediaExtractorPort,
    SessionRepositoryPort,
    SponsorBlockProvider,
    StreamResolverPort,
    TrackRepositoryPort,
)

__all__ = [
    "AudioPlayerPort",
    "MediaExtractorPort",
    "StreamResolverPort",
    "TrackRepositoryPort",
    "SessionRepositoryPort",
    "ArtistRepositoryPort",
    "LibraryRepositoryPort",
    "DiscoverRepositoryPort",
    "DatabasePort",
    "LyricsProvider",
    "SponsorBlockProvider",
]
