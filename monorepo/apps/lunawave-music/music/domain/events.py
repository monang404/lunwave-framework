"""
Module: music.domain.events

Purpose:
    Define all typed DomainEvent dataclasses for the LunaWave event bus.

Responsibilities:
    - Declare event contracts for track, queue, lyrics, and download flows.

Depends on:
    - lunawave_framework.core.kernel.events (DomainEvent base)
    - music.domain.state (TrackInfo)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.

Phase 3 extraction note:
    App half of the split proposed in ADR 0013
    (docs/adr/0013-core-domain-split.md). The generic DomainEvent base now
    lives in lunawave_framework.core.kernel.events; every concrete event
    below is music-domain vocabulary and stays here.
"""

from dataclasses import dataclass

from lunawave_framework.core.kernel.events import DomainEvent
from music.domain.state import TrackInfo


@dataclass
class TrackStartedEvent(DomainEvent):
    track: TrackInfo | None = None


@dataclass
class TrackEndedEvent(DomainEvent):
    reason: str = ""


@dataclass
class TrackProgressEvent(DomainEvent):
    position: float = 0.0


@dataclass
class TrackDurationEvent(DomainEvent):
    duration: float = 0.0


@dataclass
class QueueUpdatedEvent(DomainEvent):
    pass


@dataclass
class LyricsUpdatedEvent(DomainEvent):
    pass


@dataclass
class DownloadCompleteEvent(DomainEvent):
    track: TrackInfo | None = None


@dataclass
class DownloadProgressEvent(DomainEvent):
    progress: float = 0.0


@dataclass
class LogMessageEvent(DomainEvent):
    message: str = ""


@dataclass
class VolumeChangedEvent(DomainEvent):
    volume: int = 0


@dataclass
class TrackPauseChangedEvent(DomainEvent):
    is_paused: bool = False


@dataclass
class MpvReconnectedEvent(DomainEvent):
    """Published once MpvObserver successfully re-establishes the mpv IPC
    connection after an unexpected drop. The mpv process behind the new
    connection is freshly spawned/idle, so whoever cares about playback
    continuity (PlaybackController) is responsible for reloading the current
    track, seeking, and reapplying volume/gain in reaction to this."""

    pass
