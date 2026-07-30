---
last_verified: 2026-07-22
sprint: Phase 8 (selesai) + Tier 2 (T10-T16) + Hardening
---

# AI_CONTEXT.md — Baca ini sebelum menyentuh kode apapun

## Ringkasan Project
LunaWave adalah music player berbasis YouTube yang jalan sebagai server lokal
(aiohttp + asyncio), diakses via browser. Audio diputar oleh MPV via IPC socket.
Platform utama: Termux (Android) + Windows.
Arsitektur: Hexagonal (Ports & Adapters). Frontend: Vanilla JS, no framework.

## Sprint Aktif: Phase 8 (selesai) + Tier 2 (T10-T16) + Hardening
- Sprint Phase 8 dan Tier 2 telah diselesaikan (termasuk Fitur A: Discover Personalization, Fitur B: Redesain Login, Fitur C: Radio "Night Dial").
- Hardening dan stabilisasi codebase terus berlanjut.
- Lihat `docs/PATCHLOG.md` untuk detail patch terbaru.

## File yang TIDAK BOLEH disentuh tanpa izin eksplisit
- `engine/playback/controller.py` — risiko tinggi, closure kompleks
- `server/handlers/websocket.py` — jangan pecah dulu tanpa persetujuan eksplisit atau sprint plan yang jelas
- ~~`web/static/index.html` — tidak dipecah, ini keputusan final~~ **SUDAH TIDAK BERLAKU** (PATCH-2026-07-24-220): sesuai RFC `docs/rfc/frontend_refactor/task_breakdown_frontend_tooling.yaml` (gate F8.1/F8.2), `index.html` + `main.js` sudah dipindah ke `web/static/pages/app/` dengan persetujuan eksplisit pemilik project. `client.html`/`client.js`/`chat.js` -> `web/static/pages/client/`, `admin-logs.html`/`admin-logs.js` -> `web/static/pages/admin-logs/`. Lihat `docs/architecture/frontend.md` untuk struktur lengkap.

## Batasan teknis yang tidak boleh dilanggar
- Tidak boleh ganti aiohttp ke framework lain
- Tidak boleh tambah JS framework (React, Vue, dll)
- Tidak boleh ganti SQLite ke DB lain
- Tidak boleh refactor 2 tahap sekaligus dalam 1 commit
- Setiap file yang dipindah WAJIB ada backward-compat alias, KECUALI migrasi yang menyelesaikan seluruh caller dalam satu pass yang sama (semua pemanggil terverifikasi ikut diupdate sebelum commit) — lihat PATCH-2026-07-24-220 untuk migrasi entry point frontend yang sengaja tanpa alias atas instruksi eksplisit pemilik project.
- **Gunakan `web.AppKey` untuk semua app state baru** — jangan pakai `app["string"]` (deprecated, NotAppKeyWarning). Lihat konstanta di `server/app.py` (PLAYBACK_CONTROLLER, STATE, YTDLP, dll.)
- **Session token selalu di-hash SHA-256 sebelum masuk DB** — gunakan `core.security.hash_token()`, jangan simpan raw token. `persistence.session_repo` sudah handle ini transparan.
- **Waspada Zombie Threads**: `ThreadPoolExecutor` (seperti saat membungkus `yt-dlp` atau `ffprobe`) yang hang dapat menyebabkan *non-daemon thread* tersangkut, membuat Python gagal *exit* (membuat CI/CD *hang* meski *test coverage* lulus). Eksekusi `os._exit()` pada `pytest_unconfigure` di `tests/conftest.py` menangani isu ini, jadi jangan dihapus.

## Alur kerja AI yang benar

### Sebelum mulai
1. Baca file ini
2. Baca `docs/STATUS.md` — cek kondisi file yang akan disentuh
3. Baca `docs/PATCHLOG.md` — 2-3 entri terakhir
4. Gunakan `automation/find_owner.py` untuk orientasi cepat (lihat §Developer Scripts)
5. Baru kerjakan task

### Setelah selesai (wajib, jangan skip)
1. Jalankan `python automation/doctor.py` — satu perintah untuk semua health check (docs + arsitektur + struktur + keamanan)
   - Atau per-checker jika hanya ingin cek satu aspek (lihat §Developer Scripts)
2. Jalankan `python automation/generate_file_index.py` — jika ada file/class/fungsi baru atau berubah
3. Jalankan `python automation/generate_report.py` — jika ada penambahan/penghapusan file
4. **Catat di Patchlog**: Tambahkan entry ke `docs/PATCHLOG.md` (WAJIB ikuti format v2 *field-based*. Gunakan `python automation/patchlog.py add` dengan *flag* wajib seperti `--type`, `--area`, `--title`, `--reason`, `--files`, `--root-cause`, `--solution`, `--notes`. Setelah itu, verifikasi dengan `python automation/patchlog.py verify --json`).
5. **Update Status Proyek**: Update `docs/STATUS.md` secara manual jika kondisi file berubah, atau jika ada pergeseran status fitur di tabel "Status Fitur".
6. **Update Changelog**: Update `CHANGELOG.md` secara manual (di bawah bagian `[Unreleased]`) JIKA DAN HANYA JIKA tugas yang baru saja diselesaikan adalah peluncuran fitur baru, perbaikan bug krusial (bukan sekadar *tech debt* internal), atau ada *breaking change* yang memengaruhi *user*.

## Output Generated — Kemana Hasilnya Disimpan

Scripts generator **tidak membuat file baru**. Mereka meng-inject hasil ke dalam
dokumen yang sudah ada, hanya di antara marker:

```
<!-- BEGIN:GENERATED -->
...blok ini ditimpa otomatis setiap kali script dijalankan...
<!-- END:GENERATED -->
```

**Jangan pernah edit teks di antara marker ini secara manual** — akan ditimpa.
**Jangan hapus marker-nya** — script tidak akan tau harus inject ke mana.

| Script | Meng-update bagian mana |
|--------|------------------------|
| `generate_file_index.py` | Blok `BEGIN:GENERATED` di `docs/FILE_INDEX.md` |
| `generate_report.py` | Blok `BEGIN:GENERATED` di `docs/REPORT.md` §Statistik Project |
| `architecture_lint.py` | Tidak menulis file — stdout + exit code |
| `verify_docs.py` | Tidak menulis file — stdout + exit code |
| `verify_structure.py` | Tidak menulis file — stdout + exit code |
| `verify_security.py` | Tidak menulis file — stdout + exit code |
| `doctor.py` | Tidak menulis file — aggregasi output semua checker ke satu dashboard |
| `run_all.py` | Jalankan semua generator + doctor.py sekaligus |
| `find_owner.py` | Tidak menulis file — hanya print ke stdout |
| `call_graph.py` | Tidak menulis file — hanya print ke stdout |
| `event_graph.py` | Tidak menulis file — hanya print ke stdout |
| `hotspot.py` | Tidak menulis file — hanya print ke stdout |
| `impact.py` | Tidak menulis file — hanya print ke stdout |
| `patchlog.py` | Tidak menulis file — hanya print ke stdout |
| `test_locator.py` | Tidak menulis file — hanya print ke stdout |

Bagian dokumen **di luar marker** (narasi, rekomendasi, keputusan) adalah
wilayah manual — AI boleh edit, tapi harus prepend ke `PATCHLOG.md` setelahnya.

## Automation Tools

Project ini punya tooling di `automation/` untuk membantu orientasi dan menjaga docs tetap sinkron.
**Selalu gunakan ini sebelum membaca puluhan file secara manual.**

### Orientasi cepat — gunakan ini dulu sebelum baca kode

```bash
# Peta relasi SELURUH repo dalam 1 file — baca ini SEKALI di awal sesi
# supaya paham hubungan antar file tanpa panggil tool berkali-kali.
# Regenerate dulu kalau sudah lama (bagian dari run_all.py):
python automation/repo_map.py
cat docs/DEPENDENCY_GRAPH.json    # nodes, edges (import graph), events, orphan candidates
```

```bash
# Siapa yang bertanggung jawab atas sebuah modul, class, atau fungsi?
# Jawab: layer arsitektur, callers, dependencies, status di STATUS.md, ADR terkait
# Menerima path file, nama class, ATAU nama fungsi — resolusi otomatis.
python automation/find_owner.py DownloadManager
python automation/find_owner.py server/handlers/auth.py
python automation/find_owner.py hash_token    # cari berdasarkan nama fungsi
```

```bash
# Cek kesehatan project secara menyeluruh sebelum mulai kerja
python automation/doctor.py
```

### Setelah edit kode

```bash
# Cara paling mudah — jalankan semua checker sekaligus
python automation/doctor.py

# Atau per-aspek jika ingin cek satu hal saja:
python automation/architecture_lint.py   # import boundary
python automation/verify_docs.py         # frontmatter, PATCHLOG, coverage docstring
python automation/verify_structure.py    # file besar, pending items
python automation/verify_security.py     # credential & DB files di .gitignore

# Regenerate docs setelah ada perubahan file/fungsi
python automation/generate_file_index.py
python automation/generate_report.py

# Atau regenerate + semua check sekaligus
python automation/run_all.py
```

### Kapan pakai doctor.py vs checker individual

| Situasi | Pakai |
|---------|-------|
| Orientasi awal / cek kondisi repo | `doctor.py` |
| Setelah edit kode — validasi menyeluruh | `doctor.py` |
| Debug satu aspek saja (mis. docs) | `verify_docs.py --verbose` |
| CI / pre-commit (strict mode) | `doctor.py --strict` atau `architecture_lint.py` |
| Tambah checker baru ke dashboard | Tambah entri ke `CHECKERS` di `doctor.py` |

### JSON contract antar checker dan doctor.py

Semua checker (`verify_docs`, `architecture_lint`, `verify_structure`, `verify_security`) mengimplementasikan kontrak ini:
- Flag `--json` → cetak satu objek JSON ke stdout
- Schema wajib:
```json
{
  "checker": "nama_checker",
  "repository_status": "PASS|WARN|FAIL",
  "score": 0,
  "pass": 0, "warn": 0, "fail": 0,
  "checks": [
    {
      "name": "Nama Cek", "status": "PASS|WARN|FAIL",
      "message": "...", "count": 0, "items": [],
      "current": null, "total": null, "percentage": null, "weight": null
    }
  ]
}
```
- Exit code: `0` = tidak ada FAIL, `1` = ada FAIL

`doctor.py` hanya membaca JSON ini — tidak punya logika validasi sendiri. Untuk tambah checker baru, cukup implementasikan kontrak di atas lalu daftarkan di `CHECKERS` list di `doctor.py`.

### Struktur internal automation/ (untuk AI yang perlu memodifikasi tooling)

`automation/` kini punya dua sub-package internal:
- **`shared/`** — utilitas bersama: `check_result.py` (dataclass `CheckResult` + fungsi `_score`/`_overall_status`), `skip_dirs.py` (`SKIP_DIRS` + `walk_py_files`), `generated_block.py` (`replace_marker_block`)
- **`verify_docs/`** — pecahan dari `verify_docs.py` monolitik: `helpers.py`, `checks_docs.py`, `checks_coverage.py`, `checks_files.py`, `render.py`

Semua checker mengimport `CheckResult` dari `shared.check_result`. CLI dan exit code identik dengan sebelum refactor.


## Kontrak Output untuk AI Agent

Semua tool di automation/ yang mendukung --json WAJIB dipanggil dengan flag
itu ketika dipanggil oleh AI agent (bukan manusia interaktif).

| Tugas | Tool | Mode AI (--json) |
|---|---|---|
| Peta relasi seluruh repo (1x per sesi) | `automation/repo_map.py` | Tulis `docs/DEPENDENCY_GRAPH.json` (baca langsung, tidak perlu `--json`) |
| Cek kesehatan repo sebelum mulai | `automation/doctor.py` | `doctor.py --json` — agregasi SEMUA checker jadi 1 objek (`overall_status`, `aggregate_score`, `checkers[]`) |
| Cari owner/dependency file/class/fungsi | `automation/find_owner.py` | `find_owner.py <target> --json` — path file, class, atau fungsi, dibaca dari index ter-cache (bukan rescan penuh) |
| Mendapatkan konteks lengkap file/fitur | `automation/context_pack.py` | Endpoint utama (ownership + deps + reverse_deps + event flow + test + patchlog history + status notes sekaligus) |
| Cek entry PATCHLOG.md gagal parse | `automation/patchlog.py verify` | Deteksi entry manual berformat rusak yang riwayatnya hilang dari context_pack/find_owner |
| Cek satu aspek spesifik | `verify_docs.py --json`, dst. | sudah ada |

Catatan: `doctor.py --json` dan `repo_map.py` ditambahkan di PATCH-2026-07-17-076
untuk menghilangkan kebutuhan panggil tiap checker satu-satu.

## Pointer ke detail
| Butuh info tentang | Cara tercepat |
|--------------------|---------------|
| File mana yang relevan untuk task ini | `python automation/find_owner.py <nama_class_atau_file>` |
| Peta relasi seluruh file (import graph + event graph) | `docs/DEPENDENCY_GRAPH.json` ← auto-generated oleh `repo_map.py` |
| Semua file & fungsinya | `docs/FILE_INDEX.md` ← auto-generated, selalu akurat |
| Kondisi per-file & sprint target | `docs/STATUS.md` |
| Struktur folder detail | `docs/architecture/folder_structure.md` |
| Arsitektur ideal & Blueprint | `docs/architecture/overview.md` |
| Layer diagram & data flow | `docs/architecture/layer_diagram.md`, `docs/architecture/data_flow.md` |
| Aturan dependency antar layer | `docs/architecture/dependency_rules.md` |
| Detail backend (engine, persistence) | `docs/backend/services.md`, `docs/backend/persistence.md` |
| Detail frontend (JS, CSS) | `docs/frontend/ui_architecture.md` |
| Strategi & target testing | `docs/testing/testing_strategy.md` |
| Keputusan arsitektur | `docs/adr/` |
| Constraints teknis & lingkungan | `docs/CONSTRAINTS.md` |
| Temuan & status bug | `docs/REPORT.md` |
| Kesehatan project | `python automation/doctor.py` |

## Navigasi docs/ untuk AI

Struktur `docs/` menggunakan hierarki folder — tiap topik punya foldernya sendiri:

```
docs/
├── AI_CONTEXT.md            ← [BACA INI DULU] entry point wajib
├── INDEX.md                 ← orientasi proyek, modul, entry point, navigasi
├── STATUS.md                ← kondisi per-file, done/pending, sprint target
├── PATCHLOG.md              ← riwayat semua perubahan (append-only)
├── FILE_INDEX.md            ← inventaris lengkap semua file & fungsi [AUTO-GENERATED]
├── REPORT.md                ← statistik & analisis [AUTO-GENERATED]
├── CONSTRAINTS.md           ← batasan teknis & lingkungan (Termux, MPV, dll.)
│
├── architecture/            ← ARSITEKTUR — baca ini untuk memahami sistem
│   ├── overview.md          ← visi, filosofi, prinsip desain
│   ├── folder_structure.md  ← peta folder lengkap + fungsi tiap folder
│   ├── backend.md           ← peta modul Python layer per layer
│   ├── frontend.md          ← peta modul JS & CSS
│   ├── domain.md            ← domain model hexagonal (core, ports, events)
│   ├── data_flow.md         ← alur data dari UI → backend → MPV
│   ├── layer_diagram.md     ← diagram layer + dependency rules visual
│   ├── dependency_rules.md  ← aturan import antar layer (ditegakkan CI)
│   └── technology_stack.md  ← stack & alasan pilihan teknologi
│
├── backend/                 ← IMPLEMENTASI BACKEND
│   ├── services.md          ← engine, services, plugins
│   ├── persistence.md       ← SQLite, repositories, data layer
│   ├── api.md               ← HTTP & WebSocket API
│   ├── background_jobs.md   ← download manager, radio prefetch
│   └── caching.md           ← cache resolver & MP3 cache
│
├── frontend/                ← IMPLEMENTASI FRONTEND
│   ├── ui_architecture.md   ← peta modul JS & strategi CSS
│   ├── pwa.md               ← PWA, manifest, service worker
│   ├── state_management.md  ← store.js & state sync
│   └── routing.md           ← event routing & WS message routing
│
├── testing/                 ← TESTING
│   ├── README.md            ← quick start
│   ├── testing_strategy.md  ← filosofi & coverage target
│   ├── unit_testing.md      ← panduan & tabel unit test
│   └── integration_testing.md ← integration test scenarios
│
├── devops/                  ← CI/CD & TOOLING
│   ├── ci_cd.md             ← pipeline CI/CD
│   ├── tooling.md           ← config file & pre-commit
│   ├── deployment.md        ← cara deploy & run
│   └── release.md           ← release workflow & SemVer
│
├── security/                ← KEAMANAN
│   ├── security.md          ← vulnerability reporting
│   └── threat_model.md      ← threat model & secret management
│
├── development/             ← ONBOARDING & STANDAR
│   ├── coding_standard.md   ← standar kode & type checking
│   ├── onboarding.md        ← setup dari nol
│   └── project_structure.md ← peta risiko perubahan
│
├── opensource/              ← OPEN SOURCE
│   ├── contributing.md      ← cara berkontribusi
│   ├── CHANGELOG.md         ← changelog versi
│   └── readiness.md         ← open source checklist
│
└── adr/                     ← ARCHITECTURE DECISION RECORDS
    ├── 0001-mpv-ipc-over-subprocess.md
    ├── 0002-sqlite-over-json-cache.md
    ├── 0003-hexagonal-ports-protocol.md
    ├── 0004-command-bus-single-writer.md
    ├── 0005-websocket-single-channel.md
    ├── 0006-vanilla-js-over-framework.md
    ├── 0007-crossfade.md
    ├── 0008-admin-credentials-in-sqlite.md
    └── 0009-radio-mode-typography.md
```
