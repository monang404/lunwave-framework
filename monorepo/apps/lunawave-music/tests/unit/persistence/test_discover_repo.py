"""
Module: tests.unit.persistence.test_discover_repo

Purpose:
    Unit tests for DiscoverRepository (persistence/discover_repo.py) —
    mirrors it 1:1 per coding_standard.md Prinsip #2.

    Uses the in-memory Database facade from the `db` fixture (conftest.py)
    so every query actually executes against real SQLite, no mocking.

Responsibilities:
    - Cover get_bandit_ranked_artists, get_unheard_artists,
      get_taste_spectrum, get_top_genre, get_genre_artists_enriched,
      get_artist_detail — including empty-history / no-conn edge cases.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""


async def _make_artist(
    db, id, nama, kategori="band", tahun_aktif="2020s", alpha=1, beta=1, clicks=0
):
    await db.conn.execute(
        """INSERT INTO artists (id, nama, kategori, tahun_aktif, reward_alpha, reward_beta, click_count)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (id, nama, kategori, tahun_aktif, alpha, beta, clicks),
    )
    await db.conn.commit()


async def _make_genre(db, id, nama_genre):
    await db.conn.execute("INSERT INTO genres (id, nama_genre) VALUES (?, ?)", (id, nama_genre))
    await db.conn.commit()


async def _link_genre(db, artist_id, genre_id):
    await db.conn.execute(
        "INSERT INTO artist_genres (artist_id, genre_id) VALUES (?, ?)", (artist_id, genre_id)
    )
    await db.conn.commit()


async def _make_song(db, artist_id, judul, youtube_id, duration=200):
    await db.conn.execute(
        "INSERT INTO songs (artist_id, judul, youtube_id, duration) VALUES (?, ?, ?, ?)",
        (artist_id, judul, youtube_id, duration),
    )
    await db.conn.commit()


class TestGetBanditRankedArtists:
    async def test_excludes_untouched_artists(self, db):
        await _make_artist(db, 1, "Untouched", alpha=1, beta=1)
        result = await db.discover.get_bandit_ranked_artists(10)
        assert result == []

    async def test_ranks_by_posterior_mean_desc(self, db):
        await _make_artist(db, 1, "High Match", alpha=9, beta=1)  # 0.9
        await _make_artist(db, 2, "Low Match", alpha=2, beta=8)  # 0.2
        result = await db.discover.get_bandit_ranked_artists(10)
        assert [r["nama"] for r in result] == ["High Match", "Low Match"]
        # T3.3: repo returns raw reward_alpha/reward_beta only. match_pct
        # itself is computed by services.discover_ranking.compute_match_pct,
        # exercised directly in tests/unit/services/test_discover_ranking.py
        # and end-to-end via DiscoverService in test_discover_service.py.
        assert result[0]["reward_alpha"] == 9
        assert result[0]["reward_beta"] == 1
        assert result[1]["reward_alpha"] == 2
        assert result[1]["reward_beta"] == 8
        assert "match_pct" not in result[0]

    async def test_enriches_with_cover_and_genres(self, db):
        await _make_artist(db, 1, "Artist A", alpha=5, beta=1)
        await _make_genre(db, 1, "rock")
        await _link_genre(db, 1, 1)
        await _make_song(db, 1, "Song 1", "yt1")
        result = await db.discover.get_bandit_ranked_artists(10)
        assert result[0]["cover"] == "https://i.ytimg.com/vi/yt1/mqdefault.jpg"
        assert result[0]["genres"] == ["rock"]


class TestGetUnheardArtists:
    async def test_returns_only_fully_untouched_artists(self, db):
        await _make_artist(db, 1, "Untouched", alpha=1, beta=1, clicks=0)
        await _make_artist(db, 2, "Clicked", alpha=1, beta=1, clicks=3)
        await _make_artist(db, 3, "Bandit Touched", alpha=2, beta=1, clicks=0)
        result = await db.discover.get_unheard_artists(10)
        assert [r["nama"] for r in result] == ["Untouched"]


class TestGetTasteSpectrum:
    async def test_empty_history_returns_empty_list(self, db):
        assert await db.discover.get_taste_spectrum() == []

    async def test_returns_raw_score_rows_sorted_desc(self, db):
        """T3.3: repo returns raw {genre, score} rows, sorted score
        descending, filtered to score > 0 — no percentage normalization
        or "Lainnya" bucketing here anymore. That's
        services.discover_ranking.build_taste_spectrum's job, exercised
        directly in tests/unit/services/test_discover_ranking.py and
        end-to-end via DiscoverService in test_discover_service.py.
        """
        await _make_artist(db, 1, "Rock Artist")
        await _make_artist(db, 2, "Jazz Artist")
        await _make_artist(db, 3, "Blues Artist")
        await _make_genre(db, 1, "rock")
        await _make_genre(db, 2, "jazz")
        await _make_genre(db, 3, "blues")
        await _link_genre(db, 1, 1)
        await _link_genre(db, 2, 2)
        await _link_genre(db, 3, 3)

        await db.conn.execute(
            "INSERT INTO tracks (video_id, title, artist, duration, play_count, is_favorite) "
            "VALUES ('v1', 'T1', 'Rock Artist', 180, 10, 0)"
        )
        await db.conn.execute(
            "INSERT INTO tracks (video_id, title, artist, duration, play_count, is_favorite) "
            "VALUES ('v2', 'T2', 'Jazz Artist', 180, 5, 0)"
        )
        await db.conn.execute(
            "INSERT INTO tracks (video_id, title, artist, duration, play_count, is_favorite) "
            "VALUES ('v3', 'T3', 'Blues Artist', 180, 1, 0)"
        )
        await db.conn.commit()

        result = await db.discover.get_taste_spectrum()
        assert result == [
            {"genre": "rock", "score": 10},
            {"genre": "jazz", "score": 5},
            {"genre": "blues", "score": 1},
        ]

    async def test_unmatched_track_artist_name_not_counted(self, db):
        """Caveat didokumentasikan di module docstring: tracks.artist yang
        tidak match ke artists.nama (mis. lagu dari pencarian bebas) tidak
        ikut kehitung."""
        await _make_artist(db, 1, "Real Artist")
        await _make_genre(db, 1, "rock")
        await _link_genre(db, 1, 1)
        await db.conn.execute(
            "INSERT INTO tracks (video_id, title, artist, duration, play_count) "
            "VALUES ('v1', 'T1', 'Some YouTube Uploader', 180, 10)"
        )
        await db.conn.commit()
        assert await db.discover.get_taste_spectrum() == []


class TestGetTopGenre:
    async def test_returns_none_when_history_empty(self, db):
        assert await db.discover.get_top_genre() is None

    async def test_returns_top_genre_name(self, db):
        await _make_artist(db, 1, "Rock Artist")
        await _make_genre(db, 1, "rock")
        await _link_genre(db, 1, 1)
        await db.conn.execute(
            "INSERT INTO tracks (video_id, title, artist, duration, play_count) "
            "VALUES ('v1', 'T1', 'Rock Artist', 180, 10)"
        )
        await db.conn.commit()
        assert await db.discover.get_top_genre() == "rock"


class TestGetGenreArtistsEnriched:
    async def test_returns_enriched_rows_for_genre(self, db):
        await _make_artist(db, 1, "Artist A")
        await _make_artist(db, 2, "Artist B")
        await _make_genre(db, 1, "rock")
        await _link_genre(db, 1, 1)
        await _link_genre(db, 2, 1)
        await _make_song(db, 1, "Song A", "yta")

        result = await db.discover.get_genre_artists_enriched("rock", limit=10)
        names = {r["nama"] for r in result}
        assert names == {"Artist A", "Artist B"}
        by_name = {r["nama"]: r for r in result}
        assert by_name["Artist A"]["cover"] == "https://i.ytimg.com/vi/yta/mqdefault.jpg"
        assert by_name["Artist B"]["cover"] is None

    async def test_returns_empty_for_unknown_genre(self, db):
        assert await db.discover.get_genre_artists_enriched("nonexistent", limit=10) == []


class TestGetArtistDetail:
    async def test_returns_none_for_unknown_artist(self, db):
        assert await db.discover.get_artist_detail("Nobody") is None

    async def test_returns_full_detail_with_songs_and_genres(self, db):
        await _make_artist(db, 1, "Artist A", kategori="solo", tahun_aktif="2010s")
        await _make_genre(db, 1, "pop")
        await _link_genre(db, 1, 1)
        await _make_song(db, 1, "Song 1", "yt1", duration=100)
        await _make_song(db, 1, "Song 2", "yt2", duration=200)

        detail = await db.discover.get_artist_detail("Artist A")
        assert detail["nama"] == "Artist A"
        assert detail["kategori"] == "solo"
        assert detail["genres"] == ["pop"]
        assert detail["cover"] == "https://i.ytimg.com/vi/yt1/mqdefault.jpg"
        assert [s["video_id"] for s in detail["songs"]] == ["yt1", "yt2"]
        assert detail["songs"][0]["thumbnail"] == "https://i.ytimg.com/vi/yt1/mqdefault.jpg"

    async def test_caps_songs_at_ten(self, db):
        await _make_artist(db, 1, "Prolific Artist")
        for i in range(15):
            await _make_song(db, 1, f"Song {i}", f"yt{i}")
        detail = await db.discover.get_artist_detail("Prolific Artist")
        assert len(detail["songs"]) == 10
