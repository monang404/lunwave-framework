# Project Structure & Risk Map

> Peta risiko seluruh perubahan struktural yang direncanakan di Blueprint v2.
> Ini adalah **klasifikasi murni** — bukan urutan pengerjaan. Boleh dikerjakan bagian mana saja duluan.
>
> Untuk melihat struktur folder target lengkap, lihat → [../architecture/folder_structure.md](../architecture/folder_structure.md)

---

## Aturan Dasar

**File lama harus tetap jalan sampai file baru terbukti jalan.**

Setiap perubahan struktural harus:
1. Dikerjakan di branch terpisah
2. Ditest setelah selesai (minimal smoke test manual)
3. Dicatat di `docs/PATCHLOG.md`

---

## Risiko Nol — Pindah File, Logika Tidak Berubah

Operasi murni: cut-paste file ke lokasi baru, update import. Tidak ada logika yang berubah.

| Perubahan | Dari | Ke | Catatan |
|---|---|---|---|
| Pindah script export | `data/export_to_sqlite.py` | `automation/export_to_sqlite.py` | Update import jika ada |
| Pindah schema SQL | `cache/schema.sql` | `persistence/schema.sql` | Update path referensi |
| Pisah konstanta command | `core/command_bus.py` | `core/commands.py` (baru) | Pindah konstanta saja, bukan logika |
| Pisah connection manager | `server/websocket.py` | `server/connection_manager.py` (baru) | Cut-paste class saja |

---

## Risiko Rendah — 1 File Dipecah, Logika Tidak Berubah

Satu file dipecah menjadi beberapa file. Logika tidak berubah — hanya dipisah per concern. Import di file lain perlu diupdate.

| File Asal | File Baru | Catatan |
|---|---|---|
| `server/websocket.py` | `ws_playback.py` + `ws_queue.py` + `ws_discovery.py` + `ws_download.py` | Update semua import di `server/app.py` |
| `config.py` | `config.py` + `config_security.py` | Pisah config security-related |
| `plugins/lyrics.py` | `lyrics_fetcher.py` + `lyrics_parser.py` + `lyrics_sync.py` | Pisah per concern |
| `static/utils.js` | `utils/format.js` + `utils/toast.js` | Update semua `import` di JS |
| `static/audio.js` | `audio/playback-sync.js` + `audio/visualizer.js` | Hati-hati closure state audio |

---

## Risiko Sedang — Folder Baru, Banyak Import Berubah

Membutuhkan pembuatan folder baru dan update banyak import di seluruh codebase. Perlu test lebih teliti setelah selesai.

### Backend

| Perubahan | Detail |
|---|---|
| Buat `adapters/` | Pindah `mpv_controller.py` → `adapters/mpv/` dan `ytdlp_client.py` → `adapters/ytdlp/` |
| Pecah `cache/db.py` | Pisah ke `persistence/` — update semua referensi |
| Pecah `radio_engine.py` | Menjadi `engine/radio/{prefetcher,artist_selector,track_filter,engine}.py` |

### Frontend

| Perubahan | Detail |
|---|---|
| Pecah `render/discover.js` | Menjadi `discover-tab.js` + `radio-tab.js` |
| Pindah render dari `ws.js` | `renderFullState` dan `renderHeader` pindah ke `render/full-state.js` |
| Pecah `launcher/gui/gui.py` | Menjadi `app.py` + `ui_builder.py` + `status_panel.py` + `log_panel.py` |

---

## Risiko Tinggi — Closure Kompleks, Banyak Referensi Silang

Perubahan ini membutuhkan pemahaman mendalam tentang state dan referensi silang. **Test manual setiap tombol/fitur setelah selesai.**

| Perubahan | Risiko Utama |
|---|---|
| Pecah `engine/playback/controller.py` → `queue_ops.py` + `mode_ops.py` | Closure state playback, referensi silang antar method |
| Pecah `player-events.js` → 6 file kecil | Event listener chain yang saling bergantung — test manual tiap tombol |

### Checklist untuk Perubahan Risiko Tinggi

- [ ] Buat branch khusus: `refactor/<nama-perubahan>`
- [ ] Buat test unit untuk file asal *sebelum* dipecah (ini proof-of-behavior)
- [ ] Pecah file
- [ ] Test unit harus tetap hijau setelah dipecah
- [ ] Test manual semua fitur yang terkait
- [ ] Catat di `PATCHLOG.md`

---

## Opsional — Prioritas Paling Rendah (CSS)

| Perubahan | Kondisi |
|---|---|
| Pecah `components/player-bar.css` | **Hanya kalau** cascade-nya bisa dipisah bersih tanpa side effect |
| Pecah `components/cards.css` | **Hanya kalau** per jenis card benar-benar independen |

Jangan dipecah hanya demi "terlihat rapi". Pecah hanya kalau ada kebutuhan nyata (misalnya file sudah sangat besar atau ada conflict CSS antar komponen).

---

## Progress Tracking

Gunakan tabel ini untuk track status perubahan yang sedang dikerjakan:

| Perubahan | Risiko | Status | Branch | Catatan |
|---|---|---|---|---|
| `data/export_to_sqlite.py` → `automation/` | Nol | ⬜ Belum | — | |
| `cache/schema.sql` → `persistence/` | Nol | ⬜ Belum | — | |
| Pecah `server/websocket.py` | Rendah | ⬜ Belum | — | |
| Buat `adapters/` | Sedang | ⬜ Belum | — | |
| Pecah `radio_engine.py` | Sedang | ⬜ Belum | — | |
| Pecah `controller.py` | Tinggi | ⬜ Belum | — | |
| Pecah `player-events.js` | Tinggi | ⬜ Belum | — | |

---

## Referensi Terkait

- Folder structure target → [../architecture/folder_structure.md](../architecture/folder_structure.md)
- Coding standard & god file threshold → [coding_standard.md](coding_standard.md)
- Dependency rules yang harus tetap valid setelah refactor → [../architecture/dependency_rules.md](../architecture/dependency_rules.md)
