#!/usr/bin/env python3
"""
Backward-compatible shim.

Phase 3 of the framework extraction (see docs/extraction/ and
docs/adr/0013-core-domain-split.md) split this module: the generic
PlayerStatus/RuntimeState moved to lunawave_framework.core.kernel.state,
and the music-specific TrackInfo/AudioOutput/PlaybackMode/MusicPlayerState
moved to music.domain.state. This file exists purely so existing imports
keep working unchanged:

    from core.state import AppState, AudioOutput, PlaybackMode, PlayerStatus, TrackInfo

`AppState` here IS `MusicPlayerState` (an alias, not a copy) -- constructing
`AppState()` or checking `isinstance(x, AppState)` behaves exactly as
before this split.
"""

from lunawave_framework.core.kernel.state import PlayerStatus
from music.domain.state import AudioOutput, MusicPlayerState, PlaybackMode, TrackInfo

AppState = MusicPlayerState

__all__ = ["AppState", "AudioOutput", "PlaybackMode", "PlayerStatus", "TrackInfo"]
