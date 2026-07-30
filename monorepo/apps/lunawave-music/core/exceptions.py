#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 3 of the framework extraction (see docs/extraction/ and
docs/adr/0013-core-domain-split.md) moved this module's entire hierarchy
(including the YtPlayerError base -- 100% domain, no generic exception base
was introduced) to music.domain.exceptions. This file exists purely so
existing imports keep working unchanged:

    from core.exceptions import MpvConnectionError, TrackResolutionError, ...
"""

from music.domain.exceptions import (
    BotCheckError,
    DownloadError,
    MpvConnectionError,
    RateLimitedError,
    TrackResolutionError,
    VideoUnavailableError,
    YtPlayerError,
)

__all__ = [
    "YtPlayerError",
    "MpvConnectionError",
    "TrackResolutionError",
    "DownloadError",
    "VideoUnavailableError",
    "BotCheckError",
    "RateLimitedError",
]
