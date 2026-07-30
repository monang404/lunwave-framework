# Rencana Perbaikan Frontend LunaWave — Menuju Clean & Sesuai Vision

**Dasar:** `docs/rfc/frontend_refactor/audit_dan_visi_struktur_web.md`, `docs/adr/0011-frontend-tooling-governance.md`, `docs/rfc/frontend_refactor/task_breakdown_frontend_tooling.yaml`

**Status saat ini (setelah PATCH-223):** Sesi 1–9 RFC sudah dieksekusi dan terverifikasi jalan (vitest 20/20, eslint 0 error, tsc 0 error, depcruise 0 error). Sesi 10–11 belum dikerjakan. Dokumen ini memetakan semua yang masih tersisa supaya struktur & wiring benar-benar bersih dan sesuai vision, bukan cuma "0 error".

---

## 1. Ringkasan temuan

| Area | Status | Jumlah |
|---|---|---|
| eslint error | Bersih | 0 |
| eslint warning | Perlu dibereskan | 70 |
| tsc error | Bersih | 0 |
| depcruise error | Bersih | 0 |
| depcruise warning — circular-dependencies | Perlu dibereskan | 124 |
| depcruise warning — no-render-imports-events | Perlu dibereskan | 5 |
| depcruise warning — no-events-imports-render | Perlu dibereskan | 15 |
| `.gitignore` | Hilang total | — |
| Test backend stale (path lama) | 2 file | 2 |
| Sesi RFC belum jalan | Sesi 10, 11 | 2 sesi |

Total: **145 warning tersisa** (0 error) + 2 test gagal + 1 file konfigurasi hilang + 2 sesi RFC.

---

## 2. Perbaikan cepat, risiko rendah

### 2.1 `.gitignore`
Tidak ada sama sekali di repo — `verify_security.py` FAIL sejak audit pertama. Buat dengan minimal: credential files (`.env`, `*.key`, `secrets/`), file DB (`*.db`, `*.sqlite`), `node_modules/`, `__pycache__/`, `.cache/`.

### 2.2 Dua test backend stale
`tests/unit/server/handlers/test_http.py::test_serve_index_returns_file_response` dan `test_log_dashboard.py::test_serve_log_dashboard_returns_file_response` masih assert path lama (`static/admin-logs.html`), padahal `server/handlers/log_dashboard.py` sudah serve dari `pages/admin-logs/admin-logs.html` sejak sesi 6. Perbaiki assertion-nya ke path baru — kode produksi sudah benar, cuma test-nya yang basi.

### 2.3 eslint warning (70 total, 3 kategori)
- **`no-unused-vars` (54)** — mayoritas variabel `e` di `catch (e) {}` yang tidak dipakai. Ganti jadi `catch {}` (optional catch binding, aman di target browser modern) atau pakai `_e` kalau perlu tetap eksplisit. File terbanyak: `utils/cover-art.js` (9), `ws.js` (7), `services/auth.js` (6), `tests/frontend/ws-routing.test.js` (6).
- **`no-empty` (9)** — block `catch {}` kosong tanpa komentar. Tambah komentar singkat kenapa error di-swallow (mis. `// best-effort, aman diabaikan`) supaya lolos rule sekaligus jujur soal intent-nya.
- **`no-case-declarations` (7)**, semua di `ws.js` — `let`/`const` langsung di dalam `case` tanpa block `{}`. Bungkus tiap case yang punya deklarasi dengan `{ }`.

Estimasi: mostly mechanical, aman dikerjakan dalam satu sesi, tidak mengubah behavior runtime.

---

## 3. Perbaikan struktural — circular dependencies (124 warning)

Ini bagian paling besar dan **bukan sekadar cosmetic**: `.dependency-cruiser.js` sendiri menyatakan "This project is designed to be free of circular dependencies", jadi 124 warning ini adalah penyimpangan nyata dari vision, bukan false positive.

**Sumber utama (dari hasil depcruise):** siklus berpusat di `audio/playback-sync.js` yang saling impor dengan:
- `render/player.js` ↔ `playback-sync.js`
- `render/now-playing.js` → `dom.js` → `services/auth.js` → `playback-sync.js`
- `audio/visualizer.js` ↔ `playback-sync.js`

**Akar masalah:** `playback-sync.js` kemungkinan meng-import modul render untuk memicu re-render setelah event audio, sementara render meng-import balik untuk memanggil kontrol playback — pola "saling panggil langsung" alih-alih lewat satu arah (event bus / callback injection).

**Rencana perbaikan (butuh sesi dedicated, risk medium):**
1. Petakan seluruh 124 edge siklus per modul (`npx depcruise --config .dependency-cruiser.js web/static/shared/js web/static/pages -T json`, filter `rule.name === 'circular-dependencies'`) — daftar pasangan file lengkap.
2. Untuk tiap siklus, tentukan arah yang "benar" secara arsitektur (biasanya: `audio/*` tidak boleh tahu tentang `render/*` secara langsung).
3. Putus siklus dengan salah satu pola:
   - **Callback/dependency injection** — `playback-sync.js` menerima fungsi render lewat parameter/init, bukan `import` langsung.
   - **Event bus** — modul audio `dispatch` event custom, modul render `listen`. Ini sejalan dengan solusi yang sudah disebut di komentar `.dependency-cruiser.js` untuk masalah render/events yang mirip (lihat §4).
4. Jalankan `npx depcruise` setelah tiap file dibenahi untuk lihat progress berkurang, bukan sekali di akhir.
5. Regression test penuh (vitest + manual playback check) karena ini menyentuh jalur audio real-time.

**Catatan:** jangan dikerjakan bersamaan dengan sesi lain — sama seperti sesi 3 & 9 di RFC, ini butuh sesi tersendiri karena mengubah banyak titik impor sekaligus.

---

## 4. Perbaikan struktural — render/events cross-import (20 warning)

`.dependency-cruiser.js` sendiri sudah punya catatan resmi soal ini (komentar panjang di file config): rule ini sengaja **diturunkan dari error ke warn** pada PATCH-2026-07-24 karena ~20 call site adalah arsitektur lama yang sudah ada sebelum refactor, bukan regresi baru, dan perbaikan sungguhan butuh **event bus satu-arah antara render dan events** — perubahan arsitektur besar yang sudah ditandai out-of-scope untuk sesi recovery sebelumnya.

**Rekomendasi:** jangan buru-buru dipaksa jadi 0 dengan tambal sulam (mis. import dinamis untuk akal-akalan lolos linter) — itu menyembunyikan masalah, bukan menyelesaikannya. Kalau target "0 warning" benar-benar wajib, satu-satunya jalan sesuai vision project sendiri adalah bangun event bus (`shared/js/events/bus.js` atau serupa) sebagai satu-satunya jalur komunikasi dua arah render↔events, lalu migrasi 20 call site itu satu per satu. Ini pekerjaan besar, sebaiknya jadi sesi RFC baru (bukan bagian dari F2–F3), dengan proposal/RFC sendiri sebelum eksekusi — konsisten dengan cara project ini biasa bekerja (lihat gate index.html di sesi 8).

---

## 5. Sesi RFC yang belum jalan

### Sesi 10 — Visual regression pasca migrasi (F10.1)
Bandingkan screenshot Playwright sekarang vs baseline sesi 7 (sebelum migrasi index.html/pages). Kalau ada selisih visual tak terduga, itu sinyal bug di sesi 8, bukan sesuatu yang ditambal di sesi 10.

### Sesi 11 — Sinkronisasi dokumentasi & cleanup penutup (F11.1–F11.3)
- **F11.1**: update `docs/architecture/frontend.md` supaya peta modul & diagram state flow cocok struktur `pages/+shared/+media/` — cek dengan `python automation/verify_docs.py --json` (saat ini sudah PASS, tapi perlu di-re-run setelah §2–§4 selesai karena file berubah lagi).
- **F11.2**: grep `DEPRECATED_ALIAS` di seluruh `web/static/` — **sudah nol saat ini**, tidak ada kerja tersisa di sini kecuali ada alias baru muncul dari perbaikan di atas.
- **F11.3**: `python automation/generate_file_index.py` lalu tulis entry PATCHLOG penutup yang merangkum seluruh 11 sesi (entry terpisah dari entry per-fitur, sesuai `patchlog_group` di RFC).

---

## 6. Urutan eksekusi yang disarankan

1. `.gitignore` (§2.1) — 5 menit, zero risk
2. Dua test stale (§2.2) — 10 menit, zero risk
3. eslint 70 warning (§2.3) — 1 sesi, low risk, mekanis
4. Sesi 10 — visual regression check (perlu Playwright + browser, jalankan sebelum lanjut supaya baseline valid)
5. Circular dependencies (§3) — 1 sesi dedicated, medium risk, butuh regression test penuh
6. render/events cross-import (§4) — **usulkan sebagai RFC/sesi baru terpisah**, jangan dipaksa masuk sesi ini
7. Sesi 11 — sinkronisasi docs & PATCHLOG penutup, dikerjakan terakhir setelah semua struktur stabil

Langkah 1–4 aman dikerjakan langsung. Langkah 5 butuh konfirmasi Anda dulu (menyentuh jalur audio real-time). Langkah 6 sebaiknya jadi keputusan produk terpisah sebelum dieksekusi, mengikuti kebiasaan project ini (approval eksplisit seperti gate index.html di sesi 8).

---

## 7. Definisi "selesai" untuk dokumen ini

- `npx eslint .` → 0 error, 0 warning
- `npx tsc -p tsconfig.json` → 0 error
- `npx depcruise ...` → 0 error, 0 warning (atau warning yang tersisa punya RFC/keputusan tertulis eksplisit, bukan dibiarkan diam-diam)
- `python automation/doctor.py` → 5/5 PASS, skor 100/100 di semua kategori
- `pytest tests/unit tests/integration` → semua pass (kecuali yang memang di-skip environment, seperti tkinter)
- `docs/architecture/frontend.md` cocok 1:1 dengan struktur nyata (`verify_docs.py` bersih)
- Nol path/reference lama tersisa di kode (sudah tercapai per PATCH-223)
