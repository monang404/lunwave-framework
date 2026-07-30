"""
Module: tests.unit.persistence.test_artist_repo

Purpose:
    Unit tests for the ArtistRepository class.

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Main thread (async event loop).
"""


async def test_increment_artist_and_genre_click(db):
    await db.conn.execute("INSERT INTO artists (id, nama, kategori) VALUES (1, 'Artist A', 'band')")
    await db.conn.execute("INSERT INTO genres (id, nama_genre) VALUES (1, 'rock')")
    await db.conn.commit()

    await db.artists.increment_artist_click("Artist A")
    await db.genres.increment_genre_click("rock")

    async with db.conn.execute("SELECT click_count FROM artists WHERE nama='Artist A'") as cur:
        row = await cur.fetchone()
        assert row["click_count"] == 1

    async with db.conn.execute("SELECT click_count FROM genres WHERE nama_genre='rock'") as cur:
        row = await cur.fetchone()
        assert row["click_count"] == 1


async def test_get_all_artists_filters_by_kategori(db):
    await db.conn.execute(
        "INSERT INTO artists (id, nama, kategori) VALUES (1, 'Solo Singer', 'individu')"
    )
    await db.conn.execute("INSERT INTO artists (id, nama, kategori) VALUES (2, 'The Band', 'band')")
    await db.conn.commit()

    all_artists = await db.artists.get_all_artists()
    assert set(all_artists) == {"Solo Singer", "The Band"}

    band_only = await db.artists.get_all_artists(kategori="band")
    assert band_only == ["The Band"]
