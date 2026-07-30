---
title: Audit & Visi Struktur Folder web/ — LunaWave
version: 1.0
tanggal: 2026-07-23
status: DRAFT — untuk direview
terkait: ADR-0011 (frontend-tooling-governance), ADR-0006 (vanilla-js-over-framework)
---

# Audit & Visi Struktur Folder `web/`

> **Ringkasan satu paragraf:** `web/` bukan aplikasi satu halaman — ada 3
> entry point nyata (`index.html`, `client.html`, `admin-logs.html`) yang
> masing-masing memuat kombinasi JS/CSS berbeda, tapi struktur folder saat
> ini sama sekali tidak merefleksikan itu: semua file JS/CSS ditumpuk flat
> tanpa pemisahan "khusus satu halaman" vs "dipakai bersama". Ditambah satu
> aset 580KB yang ternyata **tidak dipakai di manapun**, dan satu folder
> top-level (`web/asset`) yang namanya beda sendiri dari konvensi
> (`web/static`). Dokumen ini memetakan kondisi nyata, lalu mengusulkan
> struktur target — dengan catatan eksplisit di titik manapun perubahan itu
> menyentuh file locked (`index.html`).

---

## 1. Peta Kondisi Saat Ini (As-Is)

### 1.1 Temuan Utama #1 — Ini Multi-Page App, Tapi Foldernya Single-Page

Server benar-benar men-serve 3 HTML berbeda (`server/handlers/http.py`,
`server/handlers/log_dashboard.py`):

| Entry point | Dipakai untuk | Jumlah `<script>` | Jumlah `<link rel=stylesheet>` |
|---|---|---|---|
| `index.html` | Admin mode (kontrol penuh) | 33 | 24 |
| `client.html` | Client / "dengar saja" mode | 9 | 10 |
| `admin-logs.html` | Dashboard log admin | 1 | 3 + inline `<style>` |

Ketiganya **saling overlap sebagian** (contoh: `store.js`, `dom.js`,
`utils/format.js`, `tokens.css`, `base/*.css` dipakai di lebih dari satu
entry point) tapi juga punya file yang **eksklusif** milik satu entry point
(`client.js`, `chat.js` hanya untuk `client.html`; `admin-logs.js` hanya
untuk `admin-logs.html`; `main.js`, `render/discover-*.js`,
`render/radio-*.js` hanya untuk `index.html`).

Struktur folder saat ini (`js/audio`, `js/events`, `js/render`, dst.) sudah
bagus untuk mengelompokkan **berdasarkan jenis tanggung jawab**, tapi **nol**
pengelompokan berdasarkan **entry point mana yang memakainya**. Akibatnya,
untuk tahu "kalau saya ubah file ini, halaman mana saja yang kena", satu-
satunya cara adalah grep manual ke 3 file HTML.

### 1.2 Temuan Utama #2 — File "Yatim" di Root `js/`

9 file duduk langsung di `web/static/js/` tanpa subfolder, padahal semua
tetangganya sudah dikelompokkan rapi ke `audio/`, `events/`, `platform/`,
`render/`, `services/`, `utils/`:

```
js/admin-logs.js   ← entry-only (admin-logs.html)
js/chat.js         ← entry-only (client.html)
js/client.js       ← entry-only (client.html)
js/config.js       ← shared
js/dom.js          ← shared
js/main.js         ← entry-only (index.html)
js/portal.js       ← shared (login portal, dipakai index.html)
js/store.js        ← shared, paling banyak dependent
js/ws.js           ← shared, paling banyak dependent
```

Ini bukan salah nama, tapi memang belum ada tempat yang tepat untuknya —
karena foldernya (`audio/`, `events/`, dst.) dipetakan by *tipe tanggung
jawab*, sedangkan 9 file ini butuh dipetakan by *scope pemakaian* (entry-
only vs shared). Dua sistem klasifikasi berbeda, dan baru salah satunya
yang punya rumah.

### 1.3 Temuan Utama #3 — Aset Mati & Folder yang Namanya Nyeleneh

- `web/asset/logos/lunawave_master.png` (**580KB**, satu file) — sudah
  dicek dengan grep menyeluruh ke seluruh repo (`.html`, `.css`, `.js`,
  `.py`, `.json`, `.md`): **tidak direferensikan di manapun.** Ini aset
  mati, kemungkinan sisa sebelum `icons/icon-192.png` & `icon-512.png`
  dibuat untuk PWA.
- Folder ini juga namanya `web/asset` (singular) — sendirian sebagai
  sibling dari `web/static` (plural), padahal secara fungsi dia juga aset
  statis. Tidak ada alasan arsitektural untuk dua top-level folder asset
  yang terpisah.

### 1.4 Temuan Utama #4 — Font Terbelah di Dua Lokasi Tanpa Alasan Jelas

```
web/static/css/vendor/fonts/tabler-icons.{ttf,woff,woff2}   ← icon font
web/static/fonts/fraunces/...                                ← display font
web/static/fonts/space-grotesk/...                            ← body font
```

Icon font (vendor, pihak ketiga) masuk akal dipisah ke `css/vendor/`.
Tapi dua web font lain (`fraunces`, `space-grotesk`) — yang sama-sama
"font", sama-sama dipakai lewat `@font-face` — punya rumah yang berbeda
dari font vendor tanpa alasan fungsional, cuma karena ditambah di waktu
berbeda.

### 1.5 Sisi yang Sudah Baik (Tidak Perlu Diubah)

- Struktur CSS (`base/`, `layout/`, `components/`, `platform/`, `vendor/`)
  sudah rapi dan konsisten — mengikuti prinsip "jangan refactor besar-
  besaran, tambah bukan pecah" yang sudah didokumentasikan di
  `docs/architecture/frontend.md`.
- `tokens.css` di root `css/` masuk akal di sana (bukan komponen spesifik,
  dipakai semua layer) — bukan inkonsistensi, itu keputusan desain yang
  benar.
- Pemisahan `icons/` (PWA icon) dari `asset/logos/` menunjukkan niat yang
  benar (pisahkan aset fungsional dari aset branding) — masalahnya cuma
  di eksekusi lokasi top-level-nya, bukan konsepnya.

---

## 2. Struktur Ideal yang Diusulkan (To-Be)

```
web/
└── static/
    ├── pages/                      # 🆕 entry-point-only code
    │   ├── app/                    #    untuk index.html (admin mode)
    │   │   ├── index.html
    │   │   └── main.js
    │   ├── client/                 #    untuk client.html
    │   │   ├── client.html
    │   │   ├── client.js
    │   │   └── chat.js
    │   └── admin-logs/             #    untuk admin-logs.html
    │       ├── admin-logs.html
    │       └── admin-logs.js
    │
    ├── shared/                     # 🆕 dipakai ≥2 entry point
    │   ├── js/
    │   │   ├── store.js
    │   │   ├── dom.js
    │   │   ├── ws.js
    │   │   ├── config.js
    │   │   ├── portal.js
    │   │   ├── audio/
    │   │   ├── events/
    │   │   ├── platform/
    │   │   ├── render/
    │   │   ├── services/
    │   │   └── utils/
    │   └── css/
    │       ├── tokens.css
    │       ├── base/
    │       ├── layout/
    │       ├── components/
    │       ├── platform/
    │       ├── portal.css
    │       └── vendor/
    │
    ├── media/                       # 🆕 gabungan asset/ + icons/ + fonts/
    │   ├── logos/                  #    (setelah lunawave_master.png
    │   │                           #     di-audit ulang: hapus jika
    │   │                           #     memang tidak dipakai)
    │   ├── icons/
    │   └── fonts/
    │       ├── vendor/             #    tabler-icons (pindah dari css/vendor/fonts)
    │       ├── fraunces/
    │       └── space-grotesk/
    │
    ├── manifest.json
    └── sw.js
```

**Prinsip di balik struktur ini:**

1. **Satu pertanyaan, satu jawaban.** "File ini dipakai halaman mana?" —
   kalau ada di `pages/<nama>/`, jawabannya satu halaman itu saja. Kalau
   ada di `shared/`, jawabannya lebih dari satu, dan perubahan di sana
   wajib dicek dampaknya ke semua pemakai (persis pola yang sudah kamu
   biasakan di backend lewat `automation/impact.py`).
2. **Struktur by-concern yang sudah bagus (`render/`, `events/`, dst.)
   dipertahankan apa adanya** — cuma dipindah ke bawah `shared/js/`,
   bukan didesain ulang. Ini bukan refactor isi file, murni relokasi.
3. **Satu folder aset, satu konvensi penamaan** (`media/`, bukan
   `asset` vs `static/icons` vs `static/fonts` yang terpisah tanpa alasan).

---

## 3. ⚠️ Titik Gesekan dengan Governance yang Sudah Ada

Realisasi struktur di atas **memindahkan file yang dirujuk dari
`index.html`, `client.html`, dan `admin-logs.html`** — otomatis berarti
path di dalam ketiga file itu perlu diperbarui (`src=`, `href=`).

- `web/static/index.html` ada di daftar **file locked** di `AI_CONTEXT.md`
  ("tidak dipecah, ini keputusan final"). Ini butuh **persetujuan eksplisit
  sebelum dieksekusi**, sama seperti syarat yang sudah ditetapkan di
  **ADR-0011 §4** untuk perubahan `type="module"`.
- `client.html` dan `admin-logs.html` **tidak** ada di daftar locked —
  keduanya boleh direstrukturisasi lebih bebas tanpa approval tambahan.

**Rekomendasi:** jangan buka `index.html` dua kali untuk dua alasan
berbeda. Gabungkan reorganisasi folder ini ke **sesi dedicated yang sama**
dengan migrasi ES Module di ADR-0011 Fase 3 — satu sesi, satu approval,
dua perubahan yang secara alami saling terkait (memindahkan file *dan*
mengubah jadi ES module keduanya sama-sama mengubah `<script>` tag).

---

## 4. Rencana Migrasi Bertahap (Tidak Sekali Jalan)

| Langkah | Menyentuh `index.html`? | Bisa jalan sekarang? |
|---|---|---|
| 1. Audit ulang & hapus `lunawave_master.png` jika benar tidak dipakai | Tidak | Ya |
| 2. Gabungkan `web/asset/` → `web/static/media/logos/` (kalau ada sisa) | Tidak (asal tidak direferensikan) | Ya |
| 3. Satukan font vendor + webfont ke `web/static/media/fonts/` | Ya (update `@font-face` src, bukan HTML) — cek dulu apakah referensi ada di CSS saja | Ya, independen |
| 4. Reorganisasi `client.html` + file eksklusifnya ke `pages/client/` | Ya, tapi `client.html` **tidak locked** | Ya, independen |
| 5. Reorganisasi `admin-logs.html` + `admin-logs.js` ke `pages/admin-logs/` | Ya, tapi **tidak locked** | Ya, independen |
| 6. Reorganisasi `index.html` + `main.js` ke `pages/app/`, pindahkan sisa shared modules ke `shared/` | **Ya, locked** | Digabung ke sesi ADR-0011 Fase 3 |

Langkah 1–5 bisa dikerjakan kapan saja tanpa menunggu apapun. Langkah 6
adalah satu-satunya yang perlu approval eksplisit dan sebaiknya menunggu
momentum yang sama dengan migrasi ES module.

---

## 5. Follow-up yang Disarankan

- Audit "dead CSS/JS" yang sesungguhnya (kelas CSS yang tidak pernah
  dipanggil, fungsi JS yang tidak pernah dipanggil) butuh alat coverage
  runtime (mis. Chrome DevTools Coverage tab atau `purgecss --dry-run`) —
  di luar cakupan audit statis ini, tapi layak jadi item terpisah setelah
  struktur folder ini beres, supaya baseline "apa yang sebenarnya dipakai"
  lebih akurat.
- Setelah struktur `pages/` vs `shared/` berdiri, rule `dependency-cruiser`
  di ADR-0011 §5 bisa diperluas: tambah rule "`pages/*` tidak boleh saling
  import satu sama lain" — mencegah `client.js` diam-diam bergantung ke
  sesuatu di `pages/app/`.

---

## Referensi

- `server/handlers/http.py`, `server/handlers/log_dashboard.py` — routing
  3 entry point
- `AI_CONTEXT.md` — status locked `index.html`
- `ADR-0011-frontend-tooling-governance.md` §4, §5 — governance & rule
  boundary yang direplikasi/diperluas di sini
- `docs/architecture/frontend.md` — peta modul & prinsip CSS konservatif
  yang jadi dasar keputusan §1.5 dan §2
