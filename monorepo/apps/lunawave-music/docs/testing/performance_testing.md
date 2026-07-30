# Performance Testing

> **Status: Future Work**
>
> Dokumen ini adalah placeholder eksplisit. Blueprint v2 belum mendefinisikan strategi performance testing secara detail. File ini dibuat agar tidak ada entri kosong dalam struktur dokumentasi.

---

## Konteks

LunaWave adalah aplikasi music player self-hosted dengan satu pengguna aktif secara tipikal. Bottleneck performa yang paling mungkin adalah:

1. **Latency WebSocket** — waktu dari command dikirim sampai respons state diterima
2. **MPV IPC roundtrip** — waktu dari command ke MPV sampai konfirmasi
3. **yt-dlp resolve time** — waktu resolve URL stream sebelum playback mulai
4. **SQLite query** — terutama pada library besar (ribuan track)
5. **Radio prefetch timing** — apakah track berikutnya selesai di-prefetch sebelum track saat ini habis

---

## Kandidat Benchmark (Masa Depan)

| Metrik | Target | Tool |
|---|---|---|
| WS command → state update | < 100ms | `time` + asyncio measurement |
| MPV IPC roundtrip | < 50ms | Custom timing in `adapters/mpv/ipc.py` |
| yt-dlp resolve (cached) | < 200ms | Cache hit timing |
| SQLite query (1000 tracks) | < 10ms | `pytest-benchmark` |
| Radio prefetch completion | > 10 detik sebelum track habis | Integration test dengan timer |

---

## Prioritas Saat Ini

**Rendah.** Selesaikan unit tests dan integration tests terlebih dahulu.
Performance testing baru relevan ketika:

- Coverage unit test mencapai > 80%
- Radio mode berjalan stabil tanpa bug
- Library track melebihi 1000 entri dalam penggunaan nyata

---

## Referensi Terkait

- Testing strategy keseluruhan → [testing_strategy.md](testing_strategy.md)
- Integration tests (termasuk radio flow) → [integration_testing.md](integration_testing.md)
- Cache architecture → [../backend/caching.md](../backend/caching.md)
- Radio prefetcher → [../backend/background_jobs.md](../backend/background_jobs.md)
