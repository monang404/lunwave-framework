"""tests/unit/core/test_state.py — mirrors core/state.py
Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

from collections import deque

from music.domain.state import MusicPlayerState as AppState
from music.domain.state import AudioOutput, PlaybackMode, PlayerStatus, TrackInfo


def test_track_info_requires_core_fields():
    track = TrackInfo(video_id="abc123", title="Song", artist="Artist", duration=180)
    assert track.video_id == "abc123"
    assert track.title == "Song"
    assert track.artist == "Artist"
    assert track.duration == 180


def test_track_info_optional_fields_default_to_none_or_zero():
    track = TrackInfo(video_id="abc123", title="Song", artist="Artist", duration=180)
    assert track.thumbnail is None
    assert track.local_path is None
    assert track.stream_url is None
    assert track.view_count is None
    assert track.stream_url_ts is None
    assert track.play_count is None
    assert track.last_played is None
    assert track.is_favorite == 0


def test_app_state_defaults():
    state = AppState()
    assert state.status is PlayerStatus.IDLE
    assert state.playback_mode is PlaybackMode.QUEUE
    assert state.audio_output is AudioOutput.BROWSER
    assert state.current_track is None
    assert state.position == 0.0
    assert state.duration == 0.0
    assert state.volume == 80
    assert state.sponsorblock_active is True
    assert state.is_online is True
    assert state.download_progress is None
    assert state.active_tab == "home"


def test_app_state_queue_and_radio_queue_are_independent_deques():
    state = AppState()
    assert isinstance(state.queue, deque)
    assert isinstance(state.radio_queue, deque)
    state.queue.append("track-1")
    assert list(state.radio_queue) == []
    assert list(state.queue) == ["track-1"]


def test_app_state_history_has_max_length_50():
    state = AppState()
    assert state.history.maxlen == 50
    for i in range(60):
        state.history.append(i)
    assert len(state.history) == 50
    # oldest entries were evicted, most recent kept
    assert list(state.history)[-1] == 59
    assert list(state.history)[0] == 10


def test_each_app_state_instance_has_independent_mutable_containers():
    """Regression guard: dataclass mutable defaults must use default_factory,
    otherwise all instances would share the same deque/list."""
    state_a = AppState()
    state_b = AppState()
    state_a.queue.append("only-in-a")
    assert list(state_b.queue) == []
    state_a.lyrics_lines.append("only-in-a")
    assert state_b.lyrics_lines == []


def test_audio_output_is_str_enum():
    assert AudioOutput.DEVICE == "device"
    assert AudioOutput.BROWSER == "browser"


def test_playback_mode_and_player_status_members_are_distinct():
    assert PlaybackMode.QUEUE != PlaybackMode.RADIO
    assert (
        len(
            {
                PlayerStatus.IDLE,
                PlayerStatus.LOADING,
                PlayerStatus.PLAYING,
                PlayerStatus.PAUSED,
                PlayerStatus.ERROR,
            }
        )
        == 5
    )
