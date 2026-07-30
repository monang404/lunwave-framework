---
title: Proposal Tooling & Governance Frontend — LunaWave
version: 1.0
tanggal: 2026-07-23
status: DRAFT — untuk direview
target rilis: LunaWave (usulan, non-breaking, bertahap per fase)
---

# Proposal Tooling & Governance Frontend
### Menutup Blind Spot: Backend Termonitor Penuh, Frontend Nol Tooling

> **Ringkasan satu paragraf:** Backend LunaWave sudah punya lapisan governance
> yang matang — `.importlinter` menegakkan boundary antar layer, dan
> `automation/` (call_graph, repo_map, hotspot, architecture_lint, dsb)
> berfungsi sebagai "mata dan telinga" untuk developer maupun AI agent yang
> bekerja di kode. Frontend (`web/static/js/`, 40 file) sama sekali tidak
> punya tooling setara — dependency antar file murni implisit lewat urutan
> `<script>` tag dan global scope. Proposal ini merinci temuan audit, risiko
> yang timbul, dan rencana penutupan gap secara bertahap tanpa mengubah
> arsitektur inti (tetap vanilla JS, tanpa framework — sesuai batasan
> `AI_CONTEXT.md`).

---

## 1. Latar Belakang

Sejak migrasi dari CLI Termux ke arsitektur client-server web-based,
kompleksitas frontend bertambah signifikan (40 file JS, ~6.000 baris),
tetapi tooling pendukungnya tidak ikut berkembang seiring backend. Saat ini:

- Backend: setiap perubahan boundary antar `core`/`adapters`/`engine`/`server`
  dst. divalidasi otomatis oleh `.importlinter`, dan tersedia script analisis
  (`automation/call_graph.py`, `automation/repo_map.py`,
  `automation/hotspot.py`, `automation/architecture_lint.py`) yang bisa
  dipakai AI agent atau developer untuk orientasi cepat sebelum menyentuh
  kode.
- Frontend: tidak ada satupun padanan dari tools di atas. Satu-satunya
  "sumber kebenaran" dependency antar file adalah urutan 33 `<script>` tag
  di `web/static/index.html` (baris 895–931), yang sifatnya manual dan tidak
  tervalidasi oleh alat apapun.

## 2. Kondisi Saat Ini (As-Is) — Temuan Audit

| Aspek | Backend | Frontend |
|---|---|---|
| Deklarasi dependency | `import` eksplisit antar modul | `<script>` tag, global scope, tanpa `import`/`export` |
| Validasi boundary | `.importlinter` (9 contract, dijalankan di CI) | Tidak ada |
| Dependency graph | `automation/call_graph.py`, `automation/repo_map.py` | Tidak ada — tidak bisa di-generate karena tidak ada graph modul yang eksplisit |
| Static lint | `pre-commit` + linting Python | Tidak ada config ESLint di repo sama sekali |
| Test coverage | `pytest`, 131 file test untuk kode backend | `vitest`, 4 file test (`store.test.js`, `ws-routing.test.js`, `pause-race.test.js`, `format.test.js`) untuk 40 file source |
| Cache-busting asset | N/A | Manual dan tidak konsisten — sebagian `<script>` punya query `?v=3`/`?v=6`, sebagian tidak |

Detail tambahan:
- Gaya modul saat ini adalah IIFE (`(function () { "use strict"; ... })()`)
  yang menaruh fungsi/state ke global scope, bukan modul ES asli.
- `store.js` dan `ws.js` adalah dua file paling banyak "diandalkan" file lain
  (setara peran `core/state.py` di backend), tapi tidak ada cara otomatis
  untuk memverifikasi siapa saja yang bergantung padanya selain `grep`
  manual.

## 3. Risiko yang Ditimbulkan

1. **Silent breakage lewat urutan script.** Memindah posisi satu
   `<script>` tag bisa membuat file lain gagal karena global yang
   dibutuhkan belum ter-load — dan ini baru kelihatan sebagai error runtime
   di browser, bukan tertangkap sebelum commit.
2. **Tidak ada static check untuk global scope.** Nama variabel/fungsi yang
   bentrok antar 40 file, atau pemakaian variabel yang belum didefinisikan,
   tidak tertangkap oleh tool apapun sebelum dijalankan manual di browser.
3. **Test coverage timpang di titik paling kritis.** `store.js`/`ws.js`
   adalah pusat state dan komunikasi — risiko regresi di sini berdampak
   luas, tapi rasio test-nya justru paling rendah dibanding ukuran
   tanggung jawabnya.
4. **Onboarding AI agent ke frontend lebih berisiko dari backend.** Tidak
   ada "peta" (graph/lint) yang bisa dibaca AI agent sebelum menyentuh file
   JS, berbeda dengan backend yang punya `automation/find_owner.py` dkk.
   untuk orientasi cepat.

## 4. Desain yang Diusulkan (To-Be)

Diusulkan 4 fase, berurutan, masing-masing berdiri sendiri dan bisa
dihentikan di fase manapun tanpa meninggalkan kode dalam keadaan rusak.

### Fase 1 — Pasang ESLint (murah, tanpa ubah arsitektur)

- Tambah `.eslintrc` (atau `eslint.config.js` — flat config) dengan
  `env: { browser: true }`, `no-undef: error`, `no-unused-vars: warn`.
- Jalankan sebagai tambahan hook baru di `.pre-commit-config.yaml` yang
  sudah ada, dan sebagai step baru di `.github/workflows/ci.yml`.
- **Tidak menyentuh** `index.html` maupun struktur file JS manapun. Ini
  murni menambah lapisan deteksi di atas kode yang sudah ada.

### Fase 2 — Perkuat Test Coverage di Titik Paling Kritis

- Prioritas: `store.js` dan `ws.js` dulu (paling banyak dependents),
  disusul `render/player.js` dan `audio/playback-sync.js` (sudah pernah
  jadi sumber race condition, lihat `docs/rfc/radio_toggle/radio_toggle.md`
  §3).
- Tidak menyentuh kode produksi, murni menambah file `*.test.js` baru di
  `tests/frontend/`.

### Fase 3 — Migrasi Bertahap ke ES Modules ⚠️ (menyentuh file locked)

- Mulai dari **leaf module** dulu (tidak punya dependent lain):
  `utils/format.js`, `utils/toast.js` → baru merambat ke `store.js`,
  `ws.js`, lalu modul `render/*` dan `events/*`.
- Tiap file yang dimigrasi wajib mempertahankan **backward-compat alias**
  selama masa transisi (pola yang sama yang sudah jadi aturan wajib di
  `AI_CONTEXT.md` untuk file yang dipindah), supaya file yang belum
  dimigrasi tetap bisa jalan berdampingan dengan yang sudah ES module.
- **`web/static/index.html` ada di daftar file locked di `AI_CONTEXT.md`
  ("tidak dipecah, ini keputusan final").** Fase ini butuh mengubah
  `<script>` menjadi `<script type="module">`, sehingga **wajib berhenti
  dan meminta persetujuan eksplisit sebelum eksekusi fase ini**, konsisten
  dengan governance yang sudah berlaku di project.

### Fase 4 — Dependency Graph Tooling

- Setelah sebagian modul sudah pakai `import`/`export` asli, pasang
  `madge` atau `dependency-cruiser` untuk generate graph dependency
  otomatis — padanan frontend dari `automation/call_graph.py`/`repo_map.py`.
- Idealnya dibungkus sebagai script baru di `automation/` (mis.
  `automation/frontend_graph.py` sebagai wrapper), supaya konsisten dengan
  cara backend mengakses tooling-nya, dan AI agent bisa memakai satu
  konvensi yang sama untuk kedua sisi.

## 5. Non-Negotiable / Governance

- Tidak menambah framework JS (React, Vue, dll.) — proposal ini murni
  tooling + modularisasi native, sejalan dengan batasan teknis di
  `AI_CONTEXT.md`.
- Fase 3 wajib mendapat persetujuan eksplisit sebelum `index.html`
  disentuh, sesuai aturan file governance-locked yang sudah berlaku.
- Setiap fase dicatat sebagai entri terpisah di `docs/PATCHLOG.md` —
  tidak digabung jadi satu patch besar (selaras dengan aturan "jangan
  refactor 2 tahap sekaligus dalam 1 commit").
- Setiap file yang dipindah/di-split selama migrasi ES module wajib ada
  backward-compat alias, mengikuti aturan yang sudah ada.

## 6. Estimasi Dampak & Effort

| Fase | Risiko regresi | Effort relatif | Bisa berhenti di sini? |
|---|---|---|---|
| 1. ESLint | Sangat rendah | Rendah | Ya |
| 2. Test coverage | Rendah | Rendah–sedang | Ya |
| 3. Migrasi ES Modules | Sedang (mitigasi via alias + urutan leaf-first) | Sedang–tinggi | Ya, bisa berhenti di modul manapun |
| 4. Dependency graph tooling | Rendah | Rendah | Ya |

## 7. Keputusan yang Perlu Persetujuan User

1. Urutan prioritas file mana yang dimigrasi ke ES module lebih dulu
   setelah `store.js`/`ws.js` — apakah ikut urutan `<script>` tag saat ini,
   atau berdasar jumlah dependent terbanyak?
2. Pilihan tool graph di Fase 4: `madge` (lebih ringan) vs
   `dependency-cruiser` (lebih kaya fitur, bisa reuse pola rule dari
   `.importlinter`)?
3. Persetujuan eksplisit untuk menyentuh `web/static/index.html` di Fase 3
   — kapan boleh dieksekusi, dan apakah perlu sesi terpisah/dedicated
   seperti pola di `radio_toggle/task_breakdown_radio.yaml`.

## Referensi

- `AI_CONTEXT.md` — daftar file locked & batasan teknis
- `.importlinter` — contract layering backend, jadi acuan pola untuk
  `dependency-cruiser` di Fase 4
- `.pre-commit-config.yaml`, `.github/workflows/ci.yml` — titik integrasi
  ESLint di Fase 1
- `web/static/index.html` (baris 895–931) — urutan `<script>` tag saat ini
- `tests/frontend/` — lokasi test vitest yang sudah ada
- `docs/rfc/radio_toggle/radio_toggle.md` §3 — riwayat race condition di
  `playback-sync.js`, relevan untuk prioritas Fase 2
