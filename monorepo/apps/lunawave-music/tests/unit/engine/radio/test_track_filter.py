"""
Module: tests.unit.engine.radio.test_track_filter

Purpose:
    Auto-generated test scaffold.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.state
    - engine.radio.track_filter

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from collections import deque

from core.state import AppState, TrackInfo
from engine.radio.track_filter import TrackFilter


def make_track(vid: str, artist: str = "A") -> TrackInfo:
    return TrackInfo(video_id=vid, title=f"Title {vid}", artist=artist, duration=100)


def test_filter_empty_list():
    state = AppState()
    tf = TrackFilter(state)
    assert tf.filter_tracks([]) == []


def test_filter_duplicates_in_candidates():
    state = AppState()
    tf = TrackFilter(state)

    t1 = make_track("v1", "A")
    t2 = make_track("v1", "A")  # Duplicate video_id
    t3 = make_track("v2", "B")

    filtered = tf.filter_tracks([t1, t2, t3])
    assert len(filtered) == 2
    assert [t.video_id for t in filtered] == ["v1", "v2"]


def test_filter_recently_played_and_queue():
    state = AppState()
    state.current_track = make_track("c1")
    state.radio_queue = deque([make_track("q1"), make_track("q2")])
    state.history = deque([make_track("h1"), make_track("h2")])

    tf = TrackFilter(state)

    candidates = [
        make_track("c1"),  # current
        make_track("q2"),  # in queue
        make_track("h1"),  # in history
        make_track("new1"),  # valid
        make_track("new2", "B"),  # valid
    ]

    filtered = tf.filter_tracks(candidates)
    assert len(filtered) == 2
    assert [t.video_id for t in filtered] == ["new1", "new2"]


def test_filter_artist_quota():
    state = AppState()
    # Already 2 songs by artist A in queue
    state.radio_queue = deque([make_track("q1", "A"), make_track("q2", "A")])

    tf = TrackFilter(state)
    tf.max_per_artist = 3

    candidates = [
        make_track("c1", "A"),  # Should be accepted (total 3)
        make_track("c2", "A"),  # Should be filtered out (would be 4)
        make_track("c3", "B"),  # Should be accepted
    ]

    filtered = tf.filter_tracks(candidates)
    assert len(filtered) == 2
    assert [t.video_id for t in filtered] == ["c1", "c3"]


def test_filter_dedup_by_normalized_title_different_video_ids():
    """PATCH-2026-07-16-001: dua video_id beda tapi title sama secara
    semantik (upload duplikat) harus di-dedup lewat normalized title,
    bukan cuma video_id."""
    state = AppState()
    state.history = deque(
        [TrackInfo(video_id="h1", title="Song (Official Video)", artist="A", duration=100)]
    )

    tf = TrackFilter(state)

    candidates = [
        TrackInfo(video_id="v_new", title="Song (Lyrics)", artist="A", duration=100),
        TrackInfo(video_id="v_ok", title="Another Song", artist="B", duration=100),
    ]

    filtered = tf.filter_tracks(candidates)
    assert [t.video_id for t in filtered] == ["v_ok"]


def test_filter_dedup_title_within_candidate_batch():
    """Dua kandidat dalam batch yang sama, title semantik sama tapi
    video_id beda -- hanya yang pertama yang lolos."""
    state = AppState()
    tf = TrackFilter(state)

    candidates = [
        TrackInfo(video_id="v1", title="Song (Official Music Video)", artist="A", duration=100),
        TrackInfo(video_id="v2", title="Song (Lyric Video)", artist="A", duration=100),
        TrackInfo(video_id="v3", title="Different Track", artist="B", duration=100),
    ]

    filtered = tf.filter_tracks(candidates)
    assert [t.video_id for t in filtered] == ["v1", "v3"]


def test_filter_does_not_cross_exclude_empty_normalized_titles():
    """Guard: title yang jadi string kosong setelah normalize (semua kata
    adalah noise word, mis. "Acoustic Cover") TIDAK boleh saling exclude
    satu sama lain -- itu bukan lagu yang sama, cuma kebetulan title-nya
    tidak punya kata bermakna."""
    state = AppState()
    state.history = deque(
        [TrackInfo(video_id="h1", title="Acoustic Cover", artist="A", duration=100)]
    )

    tf = TrackFilter(state)

    candidates = [
        TrackInfo(video_id="v_new", title="Live Performance", artist="B", duration=100),
    ]

    filtered = tf.filter_tracks(candidates)
    assert [t.video_id for t in filtered] == ["v_new"]


def test_filter_max_track_duration():
    """Bug #3 fix: track dengan duration > MAX_TRACK_DURATION (600 detik)
    dibuang dari radio queue. Batas 600 inklusif (tetap lolos). Duration
    belum diketahui (0) TIDAK dianggap terlalu panjang, tetap lolos."""
    state = AppState()
    tf = TrackFilter(state)

    candidates = [
        TrackInfo(video_id="short", title="Short Song", artist="A", duration=599),
        TrackInfo(video_id="exact", title="Exact Cap Song", artist="B", duration=600),
        TrackInfo(video_id="long", title="Hour Long Mix", artist="C", duration=3600),
        TrackInfo(video_id="unknown", title="Unknown Duration Song", artist="D", duration=0),
    ]

    filtered = tf.filter_tracks(candidates)
    assert [t.video_id for t in filtered] == ["short", "exact", "unknown"]
