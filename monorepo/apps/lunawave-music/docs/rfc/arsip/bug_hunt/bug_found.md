# Audit LunaWave — Ringkasan Temuan

## Bug Fungsional

| # | Bug | Dampak | Lokasi |
|---|---|---|---|
| 1 | `queue_select` tidak menonaktifkan Radio Mode (beda dgn `_on_cmd_play_track`) → antrean manual macet, radio "nyalip" balik | 🔴 Tinggi | `engine/playback/queue_controller.py` |
| 2 | `wsSend` tidak clear `_pendingToggleTarget` untuk action `queue_select` → UI bisa macet di LOADING | 🟠 Sedang | `web/static/shared/js/ws/transport.js` |
| 3 | `MAX_TRACK_DURATION = 600` (cap 10 menit radio) dideklarasikan tapi tidak pernah dipakai di filter manapun | 🟠 Sedang-Tinggi | `engine/radio/radio_config.py` |
| 4 | `RADIO_SEARCH_SEM` semaphore dideklarasikan ("Bug #5 fix") tapi tidak pernah di-`acquire()` — dead code | 🟠 Sedang | `engine/radio/radio_config.py` |
| 5 | `shortestDelta()` salah arah tepat di titik `to-from == 0.5` (edge-case circular distance) — dibuktikan lewat test brute-force | 🟢 Rendah (kosmetik) | `render/radio-hero-moon.js` |

## Keamanan / Robustness Minor

| # | Bug | Dampak | Lokasi |
|---|---|---|---|
| 6 | CORS reflektif (`Access-Control-Allow-Origin` = header `Origin` apa pun) saat `ALLOWED_STREAM_ORIGIN` kosong | 🟢 Rendah | `server/handlers/audio_stream_handler.py` |
| 7 | `raise` di dalam `except` tanpa `from err`/`from None` (4 lokasi) — exception chain asli hilang | 🟢 Rendah | `ws_schemas.py`, `adapters/ytdlp/resolver.py` |
| 8 | `os.walk()` deklarasi `dirs` tapi tidak dipakai untuk pruning traversal | 🟢 Rendah | `ws_cache.py` |
| 9 | ~99 pola `try/except/pass` yang menelan exception diam-diam, tersebar luas | 🟢 Rendah | banyak file (`core/log_context.py`, `launcher/*`, dll) |

## Dokumentasi Stale (bukan bug eksekusi)

| # | Temuan | Lokasi |
|---|---|---|
| 10 | Komentar bilang `get_artist_detail` "unreachable", padahal sudah terdaftar di `DISCOVERY_CMDS` | `server/handlers/ws_discovery.py` |
| 11 | Komentar bilang file "belum di-load dari index.html", padahal sudah di-`import` di `main.js` | `render/radio-hero-moon.js` |

## Catatan Umum

Codebase secara keseluruhan matang (auth/session/rate-limit/CSWSH/SSRF benar, 847 unit test lulus, linter bersih). Bug yang ditemukan bertipe *logic drift* akibat refactor (langkah penting hilang saat kode dipindah) dan *dead protective code* (konstanta/mekanisme yang diklaim aktif tapi tidak tersambung) — bukan kerentanan kritis.

**Prioritas perbaikan disarankan:** #1 → #2 → #3 → #4.
