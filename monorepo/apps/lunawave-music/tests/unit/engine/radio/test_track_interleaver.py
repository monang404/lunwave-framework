"""
Module: tests.unit.engine.radio.test_track_interleaver

Purpose:
    Unit tests for interleaving tracks by artist.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    - core.state
    - engine.radio.track_interleaver

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from core.state import TrackInfo
from engine.radio.track_interleaver import _normalize_title, interleave_by_artist


def make_track(artist: str, title: str) -> TrackInfo:
    return TrackInfo(video_id="id", title=title, artist=artist, duration=200)


def test_normalize_title():
    assert _normalize_title("Song Name (Official Video) [HD]") == "song name"
    assert _normalize_title("Acoustic Cover") == ""
    assert _normalize_title("Real Song (Feat. Artist)") == "real song"
    assert _normalize_title("Hello World (Live Performance)") == "hello world"


def test_interleave_by_artist_empty():
    assert interleave_by_artist([]) == []


def test_interleave_by_artist_single():
    t1 = make_track("A", "Song 1")
    assert interleave_by_artist([t1]) == [t1]


def test_interleave_by_artist_multiple():
    t1 = make_track("A", "Song A1")
    t2 = make_track("A", "Song A2")
    t3 = make_track("B", "Song B1")
    t4 = make_track("C", "Song C1")

    result = interleave_by_artist([t1, t2, t3, t4])

    assert len(result) == 4
    # The first element should not be the same artist as the second, etc.
    # Because A has 2 songs, B has 1, C has 1, they should be well interleaved.
    assert result[0].artist != result[1].artist
    assert result[1].artist != result[2].artist
