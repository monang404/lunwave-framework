"""
Module: data.export_to_sqlite

Purpose:
    Export artist, genre, and song data from a JSON file into a SQLite DB.

Inputs:
    artists_enriched.json in the current working directory.

Outputs:
    lunawave.db SQLite database file in the current working directory.

Side Effects:
    Drops and recreates artists, genres, artist_genres, and songs tables.

CLI:
    python data/export_to_sqlite.py

Responsibilities:
    - Implement the core functionality described in the purpose.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

import json
import os
import sqlite3


def create_tables(cursor):
    # Hapus tabel lama jika ada agar schema baru bisa diterapkan
    cursor.execute("DROP TABLE IF EXISTS songs")
    cursor.execute("DROP TABLE IF EXISTS artist_genres")
    cursor.execute("DROP TABLE IF EXISTS genres")
    cursor.execute("DROP TABLE IF EXISTS artists")

    # Tabel Artists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS artists (
        id INTEGER PRIMARY KEY,
        nama TEXT NOT NULL,
        kategori TEXT,
        tahun_aktif TEXT
    )
    """)

    # Tabel Genres
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS genres (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_genre TEXT UNIQUE NOT NULL
    )
    """)

    # Tabel Relasi Artist - Genre (Banyak-ke-Banyak)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS artist_genres (
        artist_id INTEGER,
        genre_id INTEGER,
        PRIMARY KEY (artist_id, genre_id),
        FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
        FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE CASCADE
    )
    """)

    # Tabel Songs
    # youtube_id unik PER-ARTIST (bukan global): lagu kolaborasi/duet
    # sah dimiliki oleh lebih dari satu artis (mis. "Separuh Aku" oleh
    # Peterpan/NOAH/Ariel NOAH). Constraint global sebelumnya diam-diam
    # membuang lagu itu dari katalog semua artis kecuali yang pertama
    # ditemukan di JSON.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        artist_id INTEGER,
        judul TEXT NOT NULL,
        youtube_id TEXT NOT NULL,
        duration INTEGER DEFAULT 0,
        FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE,
        UNIQUE (artist_id, youtube_id)
    )
    """)


def main():
    json_file = "artists_enriched.json"
    db_file = "lunawave.db"

    if not os.path.exists(json_file):
        print(f"Error: File {json_file} tidak ditemukan!")
        return

    print(f"Membaca data dari {json_file}...")
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    print(f"Menghubungkan ke database {db_file}...")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Buat tabel
    create_tables(cursor)

    total_artists = 0
    total_songs = 0
    total_genres = set()

    print("Mengekspor data ke SQLite, mohon tunggu sebentar...")

    for artist in data.get("artists", []):
        artist_id = artist["id"]

        # 1. Insert Artist (REPLACE jika ID sudah ada, supaya memperbarui data)
        cursor.execute(
            """
        INSERT OR REPLACE INTO artists (id, nama, kategori, tahun_aktif)
        VALUES (?, ?, ?, ?)
        """,
            (artist_id, artist["nama"], artist["kategori"], artist["tahun_aktif"]),
        )
        total_artists += 1

        # 2. Insert Genres
        for genre_name in artist.get("genre", []):
            total_genres.add(genre_name)
            # Insert genre (IGNORE jika genre sudah ada di database)
            cursor.execute(
                """
            INSERT OR IGNORE INTO genres (nama_genre)
            VALUES (?)
            """,
                (genre_name,),
            )

            # Ambil genre_id-nya
            cursor.execute("SELECT id FROM genres WHERE nama_genre = ?", (genre_name,))
            genre_id = cursor.fetchone()[0]

            # Insert ke tabel relasi (IGNORE jika relasi ini sudah pernah dimasukkan)
            cursor.execute(
                """
            INSERT OR IGNORE INTO artist_genres (artist_id, genre_id)
            VALUES (?, ?)
            """,
                (artist_id, genre_id),
            )

        # 3. Insert Songs
        for lagu in artist.get("lagu_populer", []):
            youtube_id = lagu.get("youtube_id")
            if youtube_id:  # Hanya masukkan yang punya ID YouTube valid
                duration = lagu.get("durasi_detik", 0)
                # Insert lagu (IGNORE jika (artist_id, youtube_id) sudah ada —
                # kolom ini unik per-artis, bukan global, supaya lagu
                # kolaborasi tetap muncul di katalog tiap artis pemiliknya)
                cursor.execute(
                    """
                INSERT OR IGNORE INTO songs (artist_id, judul, youtube_id, duration)
                VALUES (?, ?, ?, ?)
                """,
                    (artist_id, lagu["judul"], youtube_id, duration),
                )

                # Cek apakah baris benar-benar berhasil dimasukkan (bukan duplikat yang di-ignore)
                if cursor.rowcount > 0:
                    total_songs += 1
                else:
                    # Jika lagu sudah ada utk artis ini (IGNORE trigger), UPDATE durasinya jika tadinya 0!
                    cursor.execute(
                        """
                    UPDATE songs SET duration = ? WHERE artist_id = ? AND youtube_id = ? AND duration = 0
                    """,
                        (duration, artist_id, youtube_id),
                    )

    # Simpan semua perubahan ke database (Commit)
    conn.commit()
    conn.close()

    print("\n" + "=" * 40)
    print("EKSPOR SELESAI!")
    print(f"Total Artis diekspor : {total_artists}")
    print(f"Total Genre unik     : {len(total_genres)}")
    print(f"Total Lagu diekspor  : {total_songs}")
    print("=" * 40)
    print(f"Database Anda telah siap di file '{db_file}'! ✨")


if __name__ == "__main__":
    main()
