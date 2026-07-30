"""
Module: tests.unit.server.test_serializers

Purpose:
    Unit tests for data serialization and deserialization routines.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.state
    - server.serializers

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from core.state import AppState, PlaybackMode, PlayerStatus, TrackInfo
from server.serializers import dict_to_track, state_to_dict, track_to_dict


def test_track_to_dict():
    assert track_to_dict(None) is None

    t = TrackInfo(video_id="v1", title="Title", artist="Artist", duration=100, is_favorite=1)
    d = track_to_dict(t)
    assert d["video_id"] == "v1"
    assert d["title"] == "Title"
    assert d["is_favorite"] is True


def test_dict_to_track():
    d = {"video_id": "v1", "title": "Title", "duration": 100, "is_favorite": True}
    t = dict_to_track(d)
    assert t.video_id == "v1"
    assert t.title == "Title"
    assert getattr(t, "is_favorite", 0) == 1

    assert dict_to_track({"title": "Only Title"}) is None


def test_state_to_dict():
    state = AppState()
    state.status = PlayerStatus.PLAYING
    state.playback_mode = PlaybackMode.RADIO
    state.lyrics_lines = ["Line 1"]

    d = state_to_dict(state)
    assert d["status"] == "PLAYING"
    assert d["playback_mode"] == "RADIO"
    assert d["lyrics_lines"] == ["Line 1"]

    # PATCH-059: field baru wajib ada di payload state
    assert "playback_speed" in d
    assert d["playback_speed"] == 1.0  # default
    assert "loop_mode" in d
    assert d["loop_mode"] == "off"  # default
    assert "crossfade_enabled" in d
    assert d["crossfade_enabled"] is False  # default

    # Verifikasi nilai non-default ikut ter-serialize
    state.playback_speed = 1.5
    state.loop_mode = "track"
    state.crossfade_enabled = True
    d2 = state_to_dict(state)
    assert d2["playback_speed"] == 1.5
    assert d2["loop_mode"] == "track"
    assert d2["crossfade_enabled"] is True

    d_no_lyrics = state_to_dict(state, include_lyrics=False)
    assert "lyrics_lines" not in d_no_lyrics
