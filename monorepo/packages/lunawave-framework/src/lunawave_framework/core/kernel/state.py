"""
Module: lunawave_framework.core.kernel.state

Purpose:
    Generic runtime-state primitives with zero domain vocabulary: player
    lifecycle status and a RuntimeState base dataclass holding only the
    fields any interactive playback/session app would need.

Responsibilities:
    - Provide PlayerStatus (lifecycle enum).
    - Provide RuntimeState, a base dataclass for app-wide mutable runtime
      state, meant to be subclassed by the consuming app with its own
      domain-specific fields (see music.domain.state.MusicPlayerState in
      the lunawave-music app for the concrete example).

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread only (mutated only from the asyncio event loop) -- same
    contract as the pre-Phase-3 core.state.AppState this was split from.

Phase 3 extraction note:
    This is the framework half of the split proposed in ADR 0013
    (docs/adr/0013-core-domain-split.md) in the app repo. The original
    core/state.py mixed these fields with music-domain ones (queue,
    lyrics_*, current_track, etc.) in one flat AppState dataclass; those
    now live in music.domain.state.MusicPlayerState(RuntimeState).
"""

from dataclasses import dataclass
from enum import Enum, auto


class PlayerStatus(Enum):
    IDLE = auto()
    LOADING = auto()
    PLAYING = auto()
    PAUSED = auto()
    ERROR = auto()


@dataclass
class RuntimeState:
    """Generic runtime state any interactive media/session app needs.

    Subclass this and add domain-specific fields (see
    music.domain.state.MusicPlayerState for the concrete example this was
    split from). All fields here have defaults so subclasses can freely add
    their own defaulted fields after these without violating dataclass's
    "non-default argument follows default argument" rule.
    """

    status: PlayerStatus = PlayerStatus.IDLE
    position: float = 0.0
    duration: float = 0.0
    volume: int = 80
    playback_speed: float = 1.0
    # Generic UI-tab selector. The original app-specific allowed values
    # ("home"/"search"/"radio"/"queue") lived in a comment here before
    # Phase 3 -- moved out since "radio"/"queue" are domain concepts; this
    # base class makes no assumption about what tabs exist.
    active_tab: str = "home"
    error_msg: str | None = None
    is_online: bool = True
