"""tests/unit/services/test_discover_service.py — mirrors services/discover_service.py

Menggunakan in-memory Database dari fixture `db` (conftest.py) sehingga
semua query SQL benar-benar dieksekusi tanpa mock.

Purpose:
    Auto-generated purpose.

Subscribes to:
    None

Publishes:
    None
"""

import pytest

from core.state import TrackInfo
from services.discover_service import DiscoverService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_track(video_id="v1", **kwargs):
    defaults = dict(title="T", artist="A", duration=180)
    defaults.update(kwargs)
    return TrackInfo(video_id=video_id, **defaults)


@pytest.fixture
def svc(db):
    """DiscoverService wired to the in-memory test Database's DiscoverRepository."""
    return DiscoverService(discover=db.discover)


# ---------------------------------------------------------------------------
# get_recent
# ---------------------------------------------------------------------------


class TestGetRecent:
    async def test_returns_empty_when_no_tracks(self, svc):
        result = await svc.get_recent(10)
        assert result == []

    async def test_returns_tracks_ordered_by_last_played_desc(self, svc, db):
        await db.tracks.upsert_track(make_track("v1"))
        await db.tracks.upsert_track(make_track("v2"))
        # increment play count sets last_played timestamp
        await db.tracks.increment_play_count("v1")
        await db.tracks.increment_play_count("v2")
        await db.tracks.increment_play_count("v1")  # v1 more recently played

        result = await svc.get_recent(10)
        ids = [t.video_id for t in result]
        assert ids[0] == "v1"

    async def test_respects_n_limit(self, svc, db):
        for i in range(5):
            await db.tracks.upsert_track(make_track(f"v{i}"))
        result = await svc.get_recent(3)
        assert len(result) <= 3

    async def test_returns_track_info_instances(self, svc, db):
        await db.tracks.upsert_track(make_track("v1", title="My Song"))
        result = await svc.get_recent(5)
        assert all(isinstance(t, TrackInfo) for t in result)

    async def test_returns_empty_when_db_has_no_conn(self):
        """Service must not crash when DB connection is absent."""

        class NoConnDB:
            pass  # no conn attribute

        svc = DiscoverService(discover=NoConnDB())
        result = await svc.get_recent(5)
        assert result == []


# ---------------------------------------------------------------------------
# get_favorites
# ---------------------------------------------------------------------------


class TestGetFavorites:
    async def test_returns_empty_when_no_tracks(self, svc):
        result = await svc.get_favorites(10)
        assert result == []

    async def test_returns_favorited_tracks(self, svc, db):
        await db.tracks.upsert_track(make_track("v1"))
        await db.tracks.upsert_track(make_track("v2"))
        await db.tracks.toggle_favorite("v1")

        result = await svc.get_favorites(10)
        ids = [t.video_id for t in result]
        assert "v1" in ids

    async def test_returns_tracks_with_play_count_too(self, svc, db):
        await db.tracks.upsert_track(make_track("v1"))
        await db.tracks.increment_play_count("v1")

        result = await svc.get_favorites(10)
        assert any(t.video_id == "v1" for t in result)

    async def test_favorites_ordered_before_play_count_tracks(self, svc, db):
        await db.tracks.upsert_track(make_track("played"))
        await db.tracks.increment_play_count("played")
        await db.tracks.upsert_track(make_track("fav"))
        await db.tracks.toggle_favorite("fav")

        result = await svc.get_favorites(10)
        ids = [t.video_id for t in result]
        assert ids.index("fav") < ids.index("played")

    async def test_respects_n_limit(self, svc, db):
        for i in range(5):
            await db.tracks.upsert_track(make_track(f"v{i}"))
            await db.tracks.increment_play_count(f"v{i}")
        result = await svc.get_favorites(2)
        assert len(result) <= 2


# ---------------------------------------------------------------------------
# get_cached
# ---------------------------------------------------------------------------


class TestGetCached:
    async def test_returns_only_tracks_with_local_path(self, svc, db):
        await db.tracks.upsert_track(make_track("v1"), local_path="/mp3/v1.mp3")
        await db.tracks.upsert_track(make_track("v2"))  # no local_path

        result = await svc.get_cached(10)
        ids = [t.video_id for t in result]
        assert "v1" in ids
        assert "v2" not in ids

    async def test_returns_empty_when_no_cached_tracks(self, svc, db):
        await db.tracks.upsert_track(make_track("v1"))
        result = await svc.get_cached(10)
        assert result == []

    async def test_respects_n_limit(self, svc, db):
        for i in range(5):
            await db.tracks.upsert_track(make_track(f"v{i}"), local_path=f"/mp3/v{i}.mp3")
        result = await svc.get_cached(2)
        assert len(result) <= 2


# ---------------------------------------------------------------------------
# get_featured_artists
# ---------------------------------------------------------------------------


class TestGetFeaturedArtists:
    async def test_returns_empty_when_no_artists(self, svc):
        result = await svc.get_featured_artists(5)
        assert result == []

    async def test_returns_artist_dicts(self, svc, db):
        await db.conn.execute(
            "INSERT INTO artists (id, nama, kategori) VALUES (1, 'Band X', 'band')"
        )
        await db.conn.commit()

        result = await svc.get_featured_artists(5)
        assert len(result) >= 1
        assert "nama" in result[0]
        assert "click_count" in result[0]

    async def test_returns_at_most_n_artists(self, svc, db):
        for i in range(10):
            await db.conn.execute(f"INSERT INTO artists (id, nama) VALUES ({i + 1}, 'Artist {i}')")
        await db.conn.commit()

        result = await svc.get_featured_artists(3)
        assert len(result) <= 3

    async def test_click_count_defaults_to_zero(self, svc, db):
        await db.conn.execute("INSERT INTO artists (id, nama) VALUES (1, 'New Artist')")
        await db.conn.commit()

        result = await svc.get_featured_artists(5)
        assert result[0]["click_count"] == 0


# ---------------------------------------------------------------------------
# get_featured_genres
# ---------------------------------------------------------------------------


class TestGetFeaturedGenres:
    async def test_returns_empty_when_no_genres(self, svc):
        result = await svc.get_featured_genres(5)
        assert result == []

    async def test_returns_genre_dicts_with_required_keys(self, svc, db):
        await db.conn.execute("INSERT INTO genres (id, nama_genre) VALUES (1, 'rock')")
        await db.conn.commit()

        result = await svc.get_featured_genres(5)
        assert len(result) >= 1
        assert "nama_genre" in result[0]
        assert "click_count" in result[0]
        assert "id" in result[0]

    async def test_returns_at_most_n_genres(self, svc, db):
        for i in range(8):
            await db.conn.execute(
                f"INSERT INTO genres (id, nama_genre) VALUES ({i + 1}, 'genre_{i}')"
            )
        await db.conn.commit()

        result = await svc.get_featured_genres(4)
        assert len(result) <= 4

    async def test_click_count_defaults_to_zero(self, svc, db):
        await db.conn.execute("INSERT INTO genres (id, nama_genre) VALUES (1, 'jazz')")
        await db.conn.commit()

        result = await svc.get_featured_genres(5)
        assert result[0]["click_count"] == 0


# ---------------------------------------------------------------------------
# Discover personalization (PATCH-2026-07-17-070)
# ---------------------------------------------------------------------------


class TestGetForYou:
    async def test_returns_empty_when_bandit_untouched(self, svc, db):
        await db.conn.execute(
            "INSERT INTO artists (id, nama, reward_alpha, reward_beta) VALUES (1, 'A', 1, 1)"
        )
        await db.conn.commit()
        assert await svc.get_for_you(10) == []

    async def test_returns_ranked_artists(self, svc, db):
        await db.conn.execute(
            "INSERT INTO artists (id, nama, reward_alpha, reward_beta) VALUES (1, 'A', 8, 2)"
        )
        await db.conn.commit()
        result = await svc.get_for_you(10)
        assert len(result) == 1
        assert result[0]["nama"] == "A"
        assert result[0]["match_pct"] == 80


class TestGetUnheard:
    async def test_returns_untouched_unclicked_artists(self, svc, db):
        await db.conn.execute(
            "INSERT INTO artists (id, nama, reward_alpha, reward_beta, click_count) "
            "VALUES (1, 'A', 1, 1, 0)"
        )
        await db.conn.commit()
        result = await svc.get_unheard(10)
        assert [r["nama"] for r in result] == ["A"]


class TestGetGenreAffinity:
    async def test_returns_none_genre_when_history_empty(self, svc):
        result = await svc.get_genre_affinity(10)
        assert result == {"genre": None, "artists": []}

    async def test_returns_top_genre_and_its_artists(self, svc, db):
        await db.conn.execute("INSERT INTO artists (id, nama) VALUES (1, 'A')")
        await db.conn.execute("INSERT INTO genres (id, nama_genre) VALUES (1, 'rock')")
        await db.conn.execute("INSERT INTO artist_genres (artist_id, genre_id) VALUES (1, 1)")
        await db.conn.execute(
            "INSERT INTO tracks (video_id, title, artist, duration, play_count) "
            "VALUES ('v1', 'T', 'A', 180, 5)"
        )
        await db.conn.commit()
        result = await svc.get_genre_affinity(10)
        assert result["genre"] == "rock"
        assert [a["nama"] for a in result["artists"]] == ["A"]


class TestGetTasteSpectrum:
    async def test_empty_history_returns_empty_list(self, svc):
        assert await svc.get_taste_spectrum() == []

    async def test_returns_normalized_spectrum(self, svc, db):
        await db.conn.execute("INSERT INTO artists (id, nama) VALUES (1, 'A')")
        await db.conn.execute("INSERT INTO genres (id, nama_genre) VALUES (1, 'rock')")
        await db.conn.execute("INSERT INTO artist_genres (artist_id, genre_id) VALUES (1, 1)")
        await db.conn.execute(
            "INSERT INTO tracks (video_id, title, artist, duration, play_count) "
            "VALUES ('v1', 'T', 'A', 180, 5)"
        )
        await db.conn.commit()
        result = await svc.get_taste_spectrum()
        assert result == [{"genre": "rock", "pct": 100}]


class TestGetArtistDetail:
    async def test_returns_none_for_unknown_artist(self, svc):
        assert await svc.get_artist_detail("Nobody") is None

    async def test_returns_detail_for_known_artist(self, svc, db):
        await db.conn.execute("INSERT INTO artists (id, nama, kategori) VALUES (1, 'A', 'solo')")
        await db.conn.commit()
        result = await svc.get_artist_detail("A")
        assert result["nama"] == "A"
        assert result["songs"] == []
