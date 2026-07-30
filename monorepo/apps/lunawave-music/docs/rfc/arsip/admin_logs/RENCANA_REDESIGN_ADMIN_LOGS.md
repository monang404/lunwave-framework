---
title: Rencana Redesign UI — /admin/logs (Observability Dashboard) LunaWave
version: 1.0
tanggal: 2026-07-28
status: DRAFT — untuk direview sebelum dieksekusi agent
konteks: lanjutan dari docs/rfc/arsip/redesign_logging/proposal_redesign_logging.md (sudah diimplementasi)
---

# Rencana Redesign `/admin/logs`

## 0. TL;DR

Halaman `/admin/logs` **bukan halaman kosong yang perlu dibangun ulang** —
ini sudah hasil redesign sebelumnya (lihat RFC arsip `redesign_logging`)
dan struktur dasarnya (4 tab, responsive breakpoints, dark aesthetic
premium) sudah cukup solid. Yang saya temukan setelah audit langsung ke
kode adalah **satu bug taksonomi konkret** dan **beberapa gap
IA (information architecture) + ergonomi mobile** yang masih bisa
dirapikan. Saya **tidak menyarankan memecah jadi routing terpisah** —
alasannya di §3.

Cakupan rencana ini: perbaikan bertahap (bisa dieksekusi sebagai RFC
kecil per fase, sesuai gaya kerja proyek ini), bukan rombak total.

---

## 1. Temuan Audit

### 1.1 BUG — Dropdown kategori log sudah basi (stale), tidak sinkron dengan sumber kebenaran

`core/log_categories.py` adalah **satu-satunya** daftar kategori yang sah
(closed list, 15 kategori):

```
lifecycle, session, auth, command, event, playback, queue, radio,
download, resolve, cache, persistence, external, security, system
```

Tapi dropdown `#filterCategory` di `admin-logs.html` masih memakai daftar
lama (kemungkinan sisa taksonomi sebelum redesign logging standard):

```
lifecycle, http, session, command, playback, queue, discovery,
download, lyrics, db, cache, metrics, security, app, unknown
```

Akibatnya:
- **7 kategori nyata tidak bisa difilter sama sekali** lewat dropdown:
  `auth`, `event`, `radio`, `resolve`, `persistence`, `external`,
  `system` — padahal ini termasuk kategori paling penting untuk admin
  (`auth`, `security`-adjacent, `system`).
- **7 opsi di dropdown adalah kategori hantu** yang sudah tidak pernah
  ditulis oleh logger manapun: `http`, `discovery`, `lyrics`, `db`,
  `metrics`, `app`, `unknown` — memilihnya akan selalu menghasilkan
  list kosong, membingungkan admin yang tidak tahu ini basi.

Menariknya, bagian lain dashboard (Metrics Matrix, Top Categories di
panel kanan) **tidak** kena bug ini — keduanya (`dashboard-stats.js`)
sudah menurunkan daftar kategori secara dinamis dari `log_stats.categories`
hasil parsing log sungguhan, bukan hardcode. Jadi cukup satu titik yang
perlu diperbaiki: `<select id="filterCategory">`.

**Rekomendasi:** jangan tempel ulang daftar baru secara manual (supaya
tidak basi lagi di redesign berikutnya). Dua opsi:
- **A (cepat, disarankan):** backend expose kategori via endpoint kecil
  yang sudah ada datanya (`get_logs_stats` bisa menambahkan
  `available_categories: list(ALL_CATEGORIES)` dari
  `core.log_categories`), lalu `admin-logs.js` merender `<option>`
  secara dinamis saat init. Satu sumber kebenaran, dropdown otomatis
  ikut kalau kategori berubah di masa depan.
- **B (paling sederhana):** render `<option>` langsung dari
  `core.log_categories.ALL_CATEGORIES` di sisi server (server tetap
  Python, tinggal string-template kecil di `log_dashboard.py` sebelum
  serve HTML, atau taruh sebagai inline `<script>const CATEGORIES=[...]</script>`
  yang di-generate sekali dari test/build step) — lebih murah dari A,
  tapi opsi A lebih tahan terhadap drift jangka panjang.

### 1.2 Inkonsistensi penamaan (Inggris vs Indonesia)

Label 4 tab masih Inggris (`Live Tail`, `Metrics Matrix`, `System
Dashboard`, `User Info`), sedangkan hampir seluruh isi halaman (heading,
tombol, placeholder, pesan error) sudah Indonesia. Ini bukan bug
fungsional, tapi mengganggu "rapi terstruktur" yang diminta — kesan
setengah-jadi. Rencana penamaan baru di §4.

### 1.3 IA empat tab terasa seperti gabungan 2 domain berbeda

- **Domain "log"**: Live Tail, Metrics Matrix — soal isi `lunawave.log`.
- **Domain "runtime/observability"**: System Dashboard (CPU/RAM/uptime/
  katalog), User Info (sesi WebSocket aktif + chat admin↔klien) — ini
  bukan tentang baris log, tapi kondisi server saat ini.

Ini sebenarnya **disengaja** oleh RFC sebelumnya (judulnya eksplisit
"Dashboard Observability", bukan cuma "Dashboard Logging") — jadi bukan
salah desain, tapi **nama halaman belum mengikuti cakupannya**. Header
masih bertuliskan "LunaWave Logs" padahal isinya lebih luas dari log.

---

## 2. Pertanyaan inti: relevankah nama "logs"? Perlu routing baru per fungsi?

**Rekomendasi: TIDAK dipecah ke routing terpisah (`/admin/logs`,
`/admin/dashboard`, `/admin/users` sebagai halaman berbeda).** Tetap satu
route (`/admin/logs`), tetap satu HTML/SPA dengan tab.

Alasan teknis (bukan preferensi gaya semata):

1. **Live tail WebSocket dipakai bersama.** Satu koneksi WS
   (`connectWs`) melayani log-tail, health, chat admin — kalau dipecah
   jadi 4 halaman terpisah, tiap halaman perlu buka WS baru, ulang
   auth token (`X-Metrics-Token` / localStorage), dan histori live-tail
   putus setiap kali admin pindah "halaman". Sebagai tab, state jalan
   terus di background.
2. **Header status bar (DB/MPV/uptime/RAM/koneksi) relevan di semua
   tab** — kalau dipecah, itu harus diduplikasi 4x atau admin kehilangan
   konteks saat pindah halaman.
3. **Auth gate sama untuk semuanya** (`require_local_or_token`,
   localhost-only atau token) — satu route lebih mudah diaudit
   keamanannya dibanding 4 endpoint yang harus dijaga konsisten.
4. Biaya reload halaban penuh tiap pindah tab tidak sepadan dengan
   manfaatnya untuk kasus pakai "admin sedang debugging live" — SPA tab
   lebih cocok untuk sesi pemantauan yang biasanya dibuka lama (tab
   browser dibiarkan terbuka berjam-jam).

**Yang saya usulkan sebagai gantinya (dapat manfaat "routing per
fungsi" tanpa ongkos di atas):** tab-tab tetap satu halaman, tapi dibuat
**deep-linkable** lewat URL hash — `/admin/logs#live`,
`/admin/logs#dashboard`, `/admin/logs#matrix`, `/admin/logs#users`.
Efeknya: bisa share link langsung ke tab tertentu, refresh browser tetap
di tab yang sama, back/forward browser jalan wajar — dapat rasa
"routing per fungsi" tanpa pecah state WS/auth. Perubahan kecil di
`admin-logs.js` (baca `location.hash` saat init + update saat klik tab),
tidak menyentuh backend/routing aiohttp sama sekali.

**Rename tanpa pecah route:** ganti judul header dari "LunaWave Logs"
jadi **"LunaWave Observability"** (atau "Pusat Pemantauan LunaWave") agar
namanya mengikuti isi sesungguhnya — URL `/admin/logs` boleh tetap sama
(kompatibilitas dengan bookmark/dokumentasi/`start.sh` banner yang sudah
mencetak URL ini), cuma label yang diperbarui.

---

## 3. Rencana penamaan tab (final)

| Urutan baru | Label lama | Label baru | Alasan urutan |
|---|---|---|---|
| 1 | System Dashboard | **Ringkasan** | Overview-first — pola umum tools observability (Grafana/Datadog): admin buka halaman ini pertama untuk cek "sehat atau tidak" sebelum menyelam ke detail baris log. |
| 2 | Live Tail | **Log Langsung** | Drill-down pertama begitu tahu ada yang tidak beres. |
| 3 | Metrics Matrix | **Matriks Log** | Analisis pola/frekuensi, dipakai setelah tahu area masalahnya. |
| 4 | User Info | **Sesi Pengguna** | Domain berbeda (siapa yang connect), tetap berguna berdampingan tapi bukan prioritas pertama. |

Catatan: mengubah *urutan tab* (Ringkasan jadi default/pertama alih-alih
Live Tail) adalah perubahan default landing view. Kalau workflow admin
selama ini justru selalu buka Live Tail duluan, urutan lama juga sah —
ini satu keputusan kecil yang saya asumsikan berdasarkan pola observability
tools pada umumnya; gampang di-swap kalau preferensi berbeda.

---

## 4. Rencana visual/ergonomi per breakpoint

Baseline saat ini sudah cukup baik (breakpoint 1024px, 860px, 700px,
640px, 380px sudah ada dan masing-masing punya penanganan khusus:
kolom tabel jadi kartu di mobile, panel kanan pindah ke bawah, dsb).
Perbaikan yang diusulkan bersifat penyempurnaan, bukan bongkar:

- **Desktop (>1024px):** layout 2 kolom (log + panel statistik) tetap
  dipertahankan — sudah bagus untuk layar lebar. Tambahan: sinkronkan
  legend warna kategori (chip di setiap log-line) dengan urutan yang
  sama seperti di panel "Top Categories" kanan, supaya mata cepat
  mencocokkan warna ↔ makna.
- **Tablet (640–1024px):** sudah oke (padding & lebar panel menyesuaikan).
  Tidak ada perubahan struktural yang mendesak.
- **Mobile (<640px):** ini titik dengan potensi perbaikan terbesar.
  Tab-header sekarang berupa deretan tab horizontal di bagian atas
  (butuh scroll horizontal atau memepet teks di layar sempit). Usul:
  ubah jadi **bottom tab bar** khusus di mobile (ikon + label pendek,
  fixed di bawah, area jempol) — pola native app yang lebih ergonomis
  untuk admin yang mengecek log dari HP saat jauh dari komputer
  (skenario yang masuk akal untuk Termux/Android sebagai salah satu
  target platform LunaWave). Filter (`select` level/kategori/pencarian)
  yang sekarang di atas log-container tetap di tempatnya, hanya tab
  switcher yang pindah ke bawah.
- **Semua ukuran layar:** tambahkan *empty state* yang jelas untuk
  `logContainer` saat filter tidak menghasilkan apa-apa ("Tidak ada log
  yang cocok dengan filter ini — coba longgarkan kategori/level") alih-alih
  area kosong tanpa penjelasan; ini juga sekaligus jaring pengaman kalau
  bug §1.1 belum sempat diperbaiki dan admin lain memilih kategori hantu.

---

## 5. Rencana eksekusi bertahap (agent-ready)

Disusun sebagai checklist kecil per fase, sesuai pola kerja proyek ini
(satu fase = satu sesi/commit, dicatat di `PATCHLOG.md`):

1. **Fase 1 — Fix taksonomi (§1.1).** Perbaikan bug murni, non-breaking,
   scope kecil: sinkronkan `#filterCategory` dengan
   `core/log_categories.ALL_CATEGORIES` (pilih opsi A atau B di §1.1).
   Tambah test: assert opsi dropdown == `ALL_CATEGORIES` (mencegah drift
   ini terulang).
2. **Fase 2 — Rename label & header (§2, §3).** Ganti teks tab + judul
   header, murni copy change, tidak menyentuh logika. Termasuk cek
   `tests/frontend/admin/admin-logs.test.js` kalau ada assertion string
   label lama yang perlu diperbarui.
3. **Fase 3 — Deep-link hash routing (§2).** Tambah baca/tulis
   `location.hash` di `admin-logs.js`, tanpa ubah backend.
4. **Fase 4 — Empty state (§4).** Tambah kondisi render saat hasil
   filter kosong di `log-tail.js`.
5. **Fase 5 — Bottom tab bar mobile (§4).** Perubahan CSS + sedikit
   markup untuk breakpoint `<640px`; perlu uji visual manual di beberapa
   lebar layar (375px, 414px, 480px) karena ini murni CSS/UX, sulit
   ditangkap test otomatis.

Fase 1 dan 2 bisa langsung dieksekusi (temuan konkret, risiko rendah).
Fase 3–5 sebaiknya direview dulu asumsinya (urutan tab default, apakah
bottom-nav benar-benar diinginkan) sebelum jadi task agent.

---

## 6. Yang sengaja TIDAK diubah

- Palet warna & dark aesthetic — sudah konsisten dengan `tokens.css`
  proyek, tidak ada indikasi ini masalah.
- Struktur data API (`/api/logs/tail`, `/api/logs/stats`) — semua
  temuan di atas murni presentasi, tidak perlu bongkar kontrak backend
  di luar penambahan opsional `available_categories` (§1.1 opsi A).
- Panel chat admin↔klien (`dash-chat-panel`) — di luar cakupan
  permintaan (bukan bagian dari "logs"), tidak disentuh.
