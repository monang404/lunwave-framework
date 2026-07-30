"""
Module: engine.radio.artist_bandit

Purpose:
    Thompson Sampling (Beta-Bernoulli) untuk memilih artis radio berdasarkan
    histori selesai/skip, dengan eksplorasi otomatis untuk artis yang
    datanya masih sedikit.

Responsibilities:
    - Sampling k artis dari daftar kandidat berdasar skor Beta(alpha, beta).

Depends on:
    None (stateless, semua data alpha/beta masuk sebagai argumen)

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless — aman dipanggil dari mana saja.
"""

import random
from dataclasses import dataclass


@dataclass
class ArtistStat:
    name: str
    alpha: float = 1.0  # jumlah selesai (+prior)
    beta: float = 1.0  # jumlah skip (+prior)


def sample_artists(candidates: list[ArtistStat], k: int) -> list[str]:
    """Thompson Sampling: sample satu angka dari Beta(alpha, beta) tiap
    kandidat, urutkan turun, ambil k nama teratas.

    Artis dengan histori bagus (alpha tinggi relatif beta) cenderung dapat
    angka sampling tinggi, tapi artis dengan data sedikit (alpha=beta=1,
    varians besar) tetap punya peluang terpilih — di situlah eksplorasi
    terjadi secara alami.
    """
    if not candidates:
        return []
    scored = [(random.betavariate(c.alpha, c.beta), c.name) for c in candidates]
    scored.sort(reverse=True)
    return [name for _, name in scored[:k]]
