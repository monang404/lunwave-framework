# Desain Ulang `start.py` / `launcher` — Design Brief

**Status:** Draft — desain saja, belum ada rencana implementasi
**Scope:** Hanya tampilan (`launcher/gui/*`, `start.py` tetap sebagai entry point tipis). Tidak menyentuh `server_lifecycle.py`, `process.py`, `network.py`, `dep_checker.py`, `preflight.py`, `updater.py` — semua logic backend launcher dianggap tetap benar, murni reskin + kemungkinan migrasi framework GUI.
**Referensi visual:** `launcher-redesign-mockup.html` (buka di browser, ada state switcher: Stopped / Starting / Running / Conflict).

---

## 1. Kenapa tampilan sekarang terasa "anak magang"

Bukan soal warna dasarnya (dark + gold sebenarnya cocok dengan identitas LunaWave / motif "Night Dial"), tapi eksekusinya:

1. **Emoji sebagai ikon** (`▶ ■ ↺ ⬡ 📋 🔑 🌐 ⚙️ ☠ 🚀`) — render-nya beda-beda tiap OS/font, tidak bisa diberi warna/stroke konsisten, dan langsung terasa "prototype", bukan produk jadi.
2. **Tidak ada sistem spacing.** `ui_builder.py` pakai angka ad-hoc di semua tempat (`pady=14`, `pady=12`, `pady=10`, `pady=6`, `pady=4`, `padx=16`, `padx=15`...) — tidak ada grid yang konsisten, jadi mata merasakan "acak" walau tidak sadar kenapa.
3. **Semua Frame punya bobot visual yang sama.** Status, tombol, admin credentials, quick links, dependency check — enam `Frame` berturut-turut dengan padding/warna card yang mirip, tidak ada hierarki mana yang penting dilihat duluan.
4. **Tombol "Kill Conflict Process" muncul/hilang dari layout** (`pack()` / `pack_forget()` di tengah status bar) — bikin layout "loncat" saat state berubah, kesan tidak stabil.
5. **Status cuma titik warna + teks.** Tidak ada state transisi (langsung dari "Checking..." ke "RUNNING"/"STOPPED" tanpa perasaan proses berjalan).
6. **Font tunggal (Segoe UI) untuk semua peran** — judul, label, tombol, PID, port — tanpa perbedaan berat/skala yang tegas, sehingga tidak ada "suara" tipografi yang jelas.

Kesimpulannya: paletnya sudah oke, yang kurang adalah *sistem* (grid, tipografi, ikonografi, state machine visual) yang biasanya membedakan tampilan "developer tool serius" (Docker Desktop, JetBrains Toolbox, Tailscale) dari tampilan "hasil ngoding cepat".

---

## 2. Design tokens

### 2.1 Warna

| Token | Hex | Pemakaian |
|---|---|---|
| `bg` | `#0B0B0F` | Base window |
| `bg-surface` | `#131318` | Titlebar, console, info bar |
| `bg-elevated` | `#1A1A21` | Card (hero, tombol default) |
| `bg-elevated-2` | `#1F1F27` | Hover state elevated |
| `border` | `#26262E` | Hairline default |
| `border-strong` | `#34343E` | Hairline hover/focus |
| `accent` (brand, gold — motif bulan/Night Dial) | `#F2B544` | Primary action, logo, link hover |
| `success` | `#34D399` | Running |
| `danger` | `#F87171` | Stop / kill action |
| `warn` | `#F5A524` | Conflict — **sengaja beda dari `accent`** meski sama-sama kuning, supaya "brand color" dan "status warning" tidak saling tumpang tindih secara semantik (lihat §6, poin keputusan) |
| `text-1 / text-2 / text-3` | `#F5F5F7 / #A0A3AD / #63656F` | Hierarki teks |

Dasar pemilihan: tetap di keluarga dark+gold yang sudah jadi identitas LunaWave (konsisten dengan "Night Dial" di web UI), tapi warna semantik (success/danger/warn) dibuat lebih lembut (bukan hex mentah `#22C55E`/`#EF4444` ala Bootstrap) supaya tidak "berteriak" di sebelah gold.

### 2.2 Tipografi

- **UI (judul, label, tombol, body):** Inter — 700/600 untuk judul & label penting, 500 untuk tombol, 400 untuk body/sub.
- **Data/monospace (port, PID, uptime, log console):** JetBrains Mono — dipilih karena LunaWave sendiri adalah dev tool untuk solo developer; font monospace developer-tool-coded ini memperkuat identitas "console/manager", bukan sekadar font default.
- Skala tetap: 16.5 / 15 / 13 / 12.5 / 11.5 / 10 px — dipakai konsisten, tidak ada ukuran "nyempil" di antara itu.

### 2.3 Spacing

Grid 4px, dipakai dalam kelipatan 8 (8 / 12 / 16 / 20 / 22) untuk semua padding/gap. Tidak ada lagi angka spacing yang unik per komponen seperti sekarang.

### 2.4 Ikonografi

Ganti total emoji → ikon vektor monoline (gaya Lucide/Feather, `stroke`, bukan `fill`), semuanya `stroke-width` konsisten. Di implementasi PySide6 nanti, ini berarti bundling SVG icon set (Lucide MIT-licensed cocok) alih-alih emoji font.

---

## 3. Struktur layout baru

```
┌─────────────────────────────────────────────────────────┐
│ Titlebar: ● ● ●   LunaWave Server Manager   [Termux tag] │
├─────────────────────────────────────────────────────────┤
│ [logomark]  LunaWave                                     │
│             Server Manager                               │
│                                                            │
│ ┌─ Status Hero ──────────────────────────────────────┐   │
│ │ (●) Running                    Port  PID  Uptime    │   │
│ │     Sehat — merespons normal   8765  482… 02:14:07   │   │
│ └──────────────────────────────────────────────────────┘   │
│                                                            │
│ [Conflict banner — hanya tampil saat state = conflict]    │
│                                                            │
│ [ Start ][ Stop ][ Restart ][ Open Portal ][ Logs ]        │
│                                                            │
│ [Admin: admin ·●●●● · Reset]  [Environment: ✓ libs, MPV]   │
│                                                            │
│ ○ Client Portal  ○ Admin Console  ○ Health  ○ Metrics      │
│                                                            │
│ ┌─ Console ───────────────────────────────────  6 lines ┐ │
│ │ [14:02:11] Python libraries: OK                        │ │
│ │ [14:02:11] MPV Audio Player: OK                         │ │
│ │ [14:02:41] Server ready — listening on :8765            │ │
│ │                                                          │ │
│ └──────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ LunaWave v0.9.4                                  RUNNING  │
└─────────────────────────────────────────────────────────┘
```

Perubahan struktural dari sekarang:

- **Status jadi satu "hero" jelas** (ikon state dalam ring + label + sub-status + stats port/PID/uptime sejajar), bukan baris tipis di atas.
- **Tombol "Kill Conflict Process" pindah jadi banner khusus** yang hanya muncul saat conflict, dengan alasan jelas ("Port :8765 dipakai PID 51022") — tidak lagi nyelip di status bar dan bikin layout "loncat".
- **Admin credentials + Environment check digabung jadi satu baris compact** berdampingan (dua info-bar kecil), bukan dua card penuh yang bersaing dengan Console untuk perhatian.
- **Console mendapat porsi vertikal terbesar** (flex, bukan fixed) — ini yang paling sering dilihat saat troubleshooting, jadi paling proporsional untuk diberi ruang.
- **State "Starting…"** ditambahkan (baru, tidak ada di versi sekarang) — mengisi celah antara klik Start dan status Running, supaya user tidak melihat UI "diam" tiba-tiba berubah.
- **Environment tag** (`Termux · HyperOS` / `Windows`) di titlebar — informatif, dan murah untuk diimplementasikan karena deteksi `sys.platform` sudah ada di `network.py`/`process.py`, tinggal ditampilkan.

---

## 4. State machine visual (mengikuti logic yang sudah ada di `app.py::_refresh_status`)

| State | Start | Stop | Restart | Open | Logs | Port field | Banner |
|---|---|---|---|---|---|---|---|
| Stopped | aktif | nonaktif | nonaktif | nonaktif | nonaktif | bisa diedit | — |
| Starting *(baru)* | nonaktif | nonaktif | nonaktif | nonaktif | nonaktif | terkunci | — |
| Running | nonaktif | aktif | aktif | aktif | aktif | terkunci | — |
| Conflict | nonaktif | nonaktif | nonaktif | aktif | nonaktif | bisa diedit | tampil, isi "Kill PID x" |

Tabel ini sengaja disamakan persis dengan logic disabled/enabled yang sudah ada di `_refresh_status()` — desain baru tidak mengubah state machine, cuma mengubah representasinya. Ini penting supaya nanti proses implementasi (baik tetap Tkinter maupun pindah PySide6) hanya soal styling ulang, bukan menulis ulang logic.

---

## 5. Soal migrasi ke PySide6

Kamu sudah menyinggung kemungkinan ganti total ke PySide6 — beberapa catatan awal (bukan rencana implementasi, itu menyusul kalau kamu minta):

**Kenapa PySide6 masuk akal untuk desain ini:**
- QSS (styling PySide6) jauh lebih dekat ke CSS dibanding opsi styling Tkinter yang serba manual per-widget — token di §2 bisa dipetakan hampir 1:1 ke file `.qss`.
- Native SVG icon rendering (`QIcon` dari file `.svg`) — tidak perlu trik font/emoji seperti sekarang.
- `QSplitter` untuk area Console yang bisa di-resize user, sesuatu yang janggal diimplementasikan manual di Tkinter.
- Custom widget (state ring dengan pulse animation, banner conditional) lebih natural dengan `QPropertyAnimation` dibanding `Canvas` + manual redraw ala `_dot` sekarang.
- High-DPI handling lebih baik out of the box — relevan karena kamu jalan di Android (Termux) dan Windows dengan scaling berbeda-beda.

**Yang perlu diketahui sebelum implementasi (flag saja, belum diputuskan):**
- Struktur modul saat ini (`ui_builder.py`, `app.py`, `popups.py`, `log_view.py`, `auth_panel.py`) sudah dipisah per tanggung jawab — pola ini bisa dipertahankan, cuma isinya ganti dari `tk.Frame`/`tk.Label` ke `QWidget`/`QLabel` custom class per bagian (hero, banner, toolbar, console).
- `server_lifecycle.py`, `network.py`, `process.py`, dll — nol perubahan, karena itu backend logic, bukan GUI.
- `_safe_after` (guard supaya callback dari thread lain tidak crash saat window sudah ditutup) perlu padanan di Qt — Qt sudah punya mekanisme signal/slot cross-thread (`QMetaObject.invokeMethod` atau custom `Signal`) yang sebenarnya lebih aman dari pendekatan `after()` sekarang, jadi ini kemungkinan jadi *penyederhanaan*, bukan tambahan kerja.
- Tes yang ada sekarang (`tests/unit/launcher/gui/test_app.py`, `test_auth_panel.py`) kemungkinan besar perlu ditulis ulang total karena assertion-nya kemungkinan terikat ke API Tkinter — perlu diaudit saat masuk fase implementasi.

---

## 6. Keputusan yang perlu kamu konfirmasi sebelum masuk fase implementation plan

1. **Warna conflict (`warn` = `#F5A524`) terpisah dari `accent` (`#F2B544`)** — oke dipakai dua kuning yang mirip tapi beda peran (brand vs status), atau lebih suka conflict pakai warna non-kuning (misal biru/ungu) supaya jelas beda dari brand color?
2. **Environment tag di titlebar** (`Termux · HyperOS` / `Windows`) — mau ditampilkan, atau terlalu ramai untuk window sekecil ini?
3. **State "Starting…"** — setuju ditambahkan sebagai state baru (butuh sedikit logic tambahan di `server_lifecycle.py`/`app.py` nantinya), atau tetap 3 state saja (Stopped/Running/Conflict) seperti sekarang?
4. **Framework:** tetap Tkinter dengan restyle penuh (achievable, tapi beberapa hal di §5 jadi lebih sulit — misalnya splitter dan pulse animation), atau lanjut ke PySide6 sepenuhnya seperti yang kamu sebutkan?
5. **Custom titlebar** (`● ● ●` di mockup itu dekoratif) — mau frameless window dengan titlebar custom (lebih premium, tapi lebih banyak kerja lintas-platform terutama di Termux), atau titlebar native OS tetap dipakai dan body window saja yang di-restyle?

Setelah ini dikonfirmasi, saya bisa susun implementation plan (task breakdown per file, urutan migrasi, strategi testing) seperti pola RFC yang biasa kamu pakai.
