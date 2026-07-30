"""tests/unit/core/test_ports.py — mirrors core/ports.py

Priority: Rendah — these are structural Protocols with no runtime
behaviour of their own. We just make sure our test fakes (and the real
in-repo implementations) actually satisfy the ports they claim to.

Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

from music.domain.ports import AudioPlayerPort, MediaExtractorPort
from tests.fakes.fake_audio_player import FakeAudioPlayer
from tests.fakes.fake_media_extractor import FakeMediaExtractor


def test_fake_audio_player_has_all_audio_player_port_methods():
    required = ["connect", "close", "play", "pause", "resume", "stop", "set_volume", "seek"]
    for name in required:
        assert hasattr(FakeAudioPlayer, name), f"FakeAudioPlayer missing {name}()"
    assert hasattr(FakeAudioPlayer(), "is_connected")


def test_fake_media_extractor_has_all_media_extractor_port_methods():
    required = ["search", "extract_info", "get_stream_url", "download_mp3", "cancel_download"]
    for name in required:
        assert hasattr(FakeMediaExtractor, name), f"FakeMediaExtractor missing {name}()"


def test_track_repository_implements_track_repository_port():
    from persistence.track_repo import TrackRepository

    required = [
        "upsert_track",
        "update_stream_url_only",
        "get_track",
        "increment_play_count",
        "set_loudness",
        "set_last_position",
    ]
    for name in required:
        assert hasattr(TrackRepository, name), (
            f"TrackRepository missing {name}() required by TrackRepositoryPort"
        )


def test_session_repository_implements_session_repository_port():
    from persistence.session_repo import SessionRepository

    required = ["create_session", "verify_session", "delete_session", "cleanup_sessions"]
    for name in required:
        assert hasattr(SessionRepository, name), (
            f"SessionRepository missing {name}() required by SessionRepositoryPort"
        )


def test_artist_repository_implements_artist_repository_port():
    from persistence.artist_repo import ArtistRepository

    required = [
        "get_all_artists",
        "get_artist_songs_strict",
        "record_completion",
        "record_skip",
        "get_reward_stats",
    ]
    for name in required:
        assert hasattr(ArtistRepository, name), (
            f"ArtistRepository missing {name}() required by ArtistRepositoryPort"
        )


def test_discover_repository_implements_discover_repository_port():
    from persistence.discover_repo import DiscoverRepository

    required = [
        "get_bandit_ranked_artists",
        "get_unheard_artists",
        "get_top_genre",
        "get_genre_artists_enriched",
        "get_taste_spectrum",
        "get_artist_detail",
    ]
    for name in required:
        assert hasattr(DiscoverRepository, name), (
            f"DiscoverRepository missing {name}() required by DiscoverRepositoryPort"
        )


def test_ports_are_defined_as_protocol_classes():
    import typing

    assert typing.Protocol in AudioPlayerPort.__mro__
    assert typing.Protocol in MediaExtractorPort.__mro__
