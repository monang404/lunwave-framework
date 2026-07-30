#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 3 of the framework extraction (see docs/extraction/ and
docs/adr/0013-core-domain-split.md) split this module: the generic
DomainEvent base moved to lunawave_framework.core.kernel.events, and every
concrete event class (music-domain vocabulary) moved to music.domain.events.
This file exists purely so existing imports keep working unchanged:

    from core.events import TrackStartedEvent, QueueUpdatedEvent, ...
"""

from lunawave_framework.core.kernel.events import DomainEvent
from music.domain.events import (
    DownloadCompleteEvent,
    DownloadProgressEvent,
    LogMessageEvent,
    LyricsUpdatedEvent,
    MpvReconnectedEvent,
    QueueUpdatedEvent,
    TrackDurationEvent,
    TrackEndedEvent,
    TrackPauseChangedEvent,
    TrackProgressEvent,
    TrackStartedEvent,
    VolumeChangedEvent,
)

__all__ = [
    "DomainEvent",
    "TrackStartedEvent",
    "TrackEndedEvent",
    "TrackProgressEvent",
    "TrackDurationEvent",
    "QueueUpdatedEvent",
    "LyricsUpdatedEvent",
    "DownloadCompleteEvent",
    "DownloadProgressEvent",
    "LogMessageEvent",
    "VolumeChangedEvent",
    "TrackPauseChangedEvent",
    "MpvReconnectedEvent",
]
