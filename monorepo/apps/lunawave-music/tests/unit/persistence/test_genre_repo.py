"""
Module: tests.unit.persistence.test_genre_repo

Purpose:
    Unit tests for the GenreRepository class.

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


async def test_get_genre_artists_returns_only_artists_in_that_genre(db):
    await db.conn.execute("INSERT INTO artists (id, nama) VALUES (1, 'Rock Artist')")
    await db.conn.execute("INSERT INTO artists (id, nama) VALUES (2, 'Jazz Artist')")
    await db.conn.execute("INSERT INTO genres (id, nama_genre) VALUES (1, 'rock')")
    await db.conn.execute("INSERT INTO genres (id, nama_genre) VALUES (2, 'jazz')")
    await db.conn.execute("INSERT INTO artist_genres (artist_id, genre_id) VALUES (1, 1)")
    await db.conn.execute("INSERT INTO artist_genres (artist_id, genre_id) VALUES (2, 2)")
    await db.conn.commit()

    result = await db.genres.get_genre_artists("rock", limit=10)
    assert result == ["Rock Artist"]
