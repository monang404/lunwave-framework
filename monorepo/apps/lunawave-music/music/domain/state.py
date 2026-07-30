"""
Module: music.domain.state

Purpose:
    Music-domain state: track metadata, playback-mode/output enums, and
    MusicPlayerState -- the music-specific extension of
    lunawave_framework.core.kernel.state.RuntimeState.

Responsibilities:
    - Provide TrackInfo, PlaybackMode, AudioOutput.
    - Provide MusicPlayerState(RuntimeState), holding queue/radio/lyrics/
      download runtime state on top of the generic fields inherited from
      RuntimeState (status, position, duration, volume, playback_speed,
      active_tab, error_msg, is_online).

Depends on:
    - lunawave_framework.core.kernel.state (RuntimeState, PlayerStatus)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread only (mutated only from the asyncio event loop).

Phase 3 extraction note:
    App half of the split proposed in ADR 0013
    (docs/adr/0013-core-domain-split.md). core/state.py in the app repo is
    now a backward-compat shim: `AppState = MusicPlayerState` there
    preserves the old name for every existing caller.
"""

from collections import deque
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto

from lunawave_framework.core.kernel.state import PlayerStatus, RuntimeState

# Re-exported so `from music.domain.state import PlayerStatus` and the old
# `from core.state import PlayerStatus` both resolve to the exact same enum
# class -- callers doing isinstance()/equality checks see one PlayerStatus,
# not two.
__all__ = [
    "PlayerStatus",
    "AudioOutput",
    "PlaybackMode",
    "TrackInfo",
    "MusicPlayerState",
]


class AudioOutput(StrEnum):
    DEVICE = "device"
    BROWSER = "browser"


class PlaybackMode(Enum):
    QUEUE = auto()  # user-directed
    RADIO = auto()  # autonomous, self-sustaining


@dataclass
class TrackInfo:
    video_id: str
    title: str
    artist: str
    duration: int
    thumbnail: str | None = None
    local_path: str | None = None
    stream_url: str | None = None
    view_count: int | None = None
    stream_url_ts: int | None = None
    play_count: int | None = None
    last_played: int | None = None
    is_favorite: int | None = 0
    loudness_lufs: float | None = None
    true_peak_dbtp: float | None = None  # dBTP, dari ffmpeg loudnorm; None = belum dianalisis
    last_position: float | None = 0.0


@dataclass
class MusicPlayerState(RuntimeState):
    """Music-domain runtime state. Adds queue/radio/lyrics/download fields
    on top of the generic RuntimeState fields (status, position, duration,
    volume, playback_speed, active_tab, error_msg, is_online)."""

    # Playback (music-specific)
    loop_mode: str = "off"
    playback_mode: PlaybackMode = PlaybackMode.QUEUE
    audio_output: AudioOutput = AudioOutput.BROWSER
    current_track: TrackInfo | None = None
    sponsorblock_active: bool = True
    crossfade_enabled: bool = False
    loudness_normalization_enabled: bool = False
    # Gain (dB) yang dihitung untuk current_track saat di-load (lihat TrackLoader.load_track).
    # Disimpan di state supaya toggle_loudness_normalization() bisa langsung re-apply
    # filter `af` ke track yang sedang berjalan, tanpa perlu reload/re-resolve track.
    current_track_gain_db: float = 0.0

    # Queue (hanya aktif di QUEUE mode)
    queue: deque = field(default_factory=deque)
    # Radio (hanya aktif di RADIO mode) — TIDAK PERNAH dicampur dengan `queue`.
    # Radio harus independen dari Queue Mode (lihat Constitution).
    radio_queue: deque = field(default_factory=deque)
    history: deque = field(default_factory=lambda: deque(maxlen=50))

    # Lyrics
    lyrics_lines: list[str] = field(default_factory=list)
    lyrics_timestamps: list[float] = field(default_factory=list)
    lyrics_index: int = 0
    lyrics_offset: float = 0.0

    # Download
    download_progress: float | None = None  # 0.0–1.0, None = idle
