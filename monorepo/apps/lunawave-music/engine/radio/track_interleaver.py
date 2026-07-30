"""
Module: engine.radio.track_interleaver

Purpose:
    Interleaves tracks from different artists to create a balanced radio queue.

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

import random
import re

_TITLE_NOISE_WORDS = frozenset(
    {
        "official",
        "music",
        "video",
        "audio",
        "lyric",
        "lyrics",
        "mv",
        "cover",
        "live",
        "performance",
        "hd",
        "hq",
        "remastered",
        "remaster",
        "full",
        "version",
        "ver",
        "feat",
        "ft",
        "original",
        "soundtrack",
        "ost",
        "karaoke",
        "instrumental",
        "acoustic",
        "akustik",
        "konser",
    }
)


def normalize_title(title: str) -> str:
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    words = [w for w in t.split() if w not in _TITLE_NOISE_WORDS]
    return " ".join(words).strip()


# Alias backward-compat: dulu private, sekarang dipakai lintas modul
# (engine/radio/track_filter.py) untuk dedup title di radio queue.
_normalize_title = normalize_title


def interleave_by_artist(tracks: list) -> list:
    """Round-robin interleaving: kelompokkan track per artis (urutan asli tiap
    kelompok tetap dipertahankan), lalu ambil bergiliran satu-satu dari kelompok
    artis yang berbeda (urutan artis di-shuffle tiap 'putaran' agar tidak selalu
    artis yang sama duluan). Menjamin tidak ada 2 track artis sama berturut-turut
    kecuali kalau track dari artis itu memang lebih banyak dari separuh batch.
    """
    if len(tracks) <= 1:
        return tracks

    groups: dict[str, list] = {}
    for t in tracks:
        groups.setdefault(t.artist, []).append(t)

    result = []
    last_artist = None
    # Tiap putaran: acak urutan artis yang masih punya sisa lagu, lalu ambil 1
    # lagu dari tiap artis di urutan itu. Kalau artis pertama di putaran baru
    # kebetulan sama dengan artis terakhir di putaran sebelumnya (bisa terjadi
    # karena tiap putaran di-shuffle ulang dari nol), tukar posisinya dulu
    # supaya tidak ada 2 lagu artis sama yang nempel persis di batas putaran.
    while groups:
        artists = list(groups.keys())
        random.shuffle(artists)
        if len(artists) > 1 and artists[0] == last_artist:
            swap_idx = random.randint(1, len(artists) - 1)
            artists[0], artists[swap_idx] = artists[swap_idx], artists[0]
        for artist in artists:
            queue = groups[artist]
            result.append(queue.pop(0))
            if not queue:
                del groups[artist]
            last_artist = artist
    return result
