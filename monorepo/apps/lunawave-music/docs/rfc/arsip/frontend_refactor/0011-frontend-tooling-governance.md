# ADR-0011: Tooling & Governance Frontend (ESLint, Urutan Migrasi ES Module, Dependency Graph)

**Status:** Accepted
**Date:** 2026-07-23
**RFC Sumber:** `docs/rfc/frontend_tooling/proposal_frontend_tooling.md`

---

## Konteks

RFC di atas mengidentifikasi bahwa backend LunaWave punya governance matang
(`.importlinter`, `automation/*`) sedangkan frontend (`web/static/js/`, 40
file, vanilla JS lewat `<script>` tag global scope) tidak punya tooling
setara. RFC tersebut mengusulkan 4 fase perbaikan tapi menyisakan 3
keputusan terbuka. ADR ini menutup ketiganya sekaligus, sehingga eksekusi
bisa langsung berjalan tanpa jeda menunggu keputusan produk di tengah jalan.

## Keputusan

### 1. Linting — Flat config ESLint, bukan `.eslintrc`

Pakai `eslint.config.js` (flat config), bukan format lama `.eslintrc.*`.
Alasan: proyek ini baru mulai dari nol untuk lint JS, jadi tidak ada utang
config lama yang perlu dipertahankan format-nya, dan flat config adalah arah
resmi ESLint ke depan. Rule wajib di fase awal: `no-undef: error`,
`no-unused-vars: warn`, `env: browser + es2021`.

### 2. Urutan migrasi ke ES Module — leaf-first berdasarkan jumlah dependent, bukan urutan `<script>` tag

Urutan file di `index.html` saat ini adalah urutan *load*, bukan urutan
*ketergantungan* — dua hal itu tidak sama, dan mengikuti urutan `<script>`
apa adanya berisiko memindahkan file yang justru punya banyak dependent di
awal. Urutan migrasi final, ditentukan dari jumlah file lain yang
bergantung padanya (paling sedikit dependent duluan):

1. `utils/format.js`, `utils/toast.js` — leaf murni, tanpa dependent internal.
2. `config.js`, `dom.js` — dependent rendah, dipakai tapi tidak bergantung
   balik ke modul lain.
3. `store.js`, `ws.js` — inti state & komunikasi, migrasi dilakukan sebagai
   sesi *dedicated* sendiri (tidak digabung task lain), karena dampak
   regresi paling luas jika salah.
4. `render/*.js`, `events/*.js` — bergantung pada `store.js`/`dom.js`,
   dimigrasi setelah keduanya stabil sebagai ES module.
5. `audio/playback-sync.js`, `platform/*.js`, `portal.js` — terakhir,
   karena riwayat kerapuhan `playback-sync.js` (lihat
   `docs/rfc/radio_toggle/radio_toggle.md` §3) membuatnya paling aman
   disentuh setelah pola migrasi teruji di modul-modul sebelumnya.
6. `main.js` — migrasi penutup, karena ini entry point yang mengorkestrasi
   semua modul lain.

Setiap file yang sudah dimigrasi wajib mempertahankan backward-compat alias
sampai seluruh caller-nya juga bermigrasi, mengikuti aturan yang sama yang
sudah berlaku untuk file backend yang dipindah.

### 3. Tool dependency graph — `dependency-cruiser`, bukan `madge`

Dipilih `dependency-cruiser` karena bisa didefinisikan dengan rule berbasis
config (`.dependency-cruiser.js`) yang secara filosofi setara dengan
`.importlinter` di backend — artinya begitu ES module sudah cukup luas,
boundary frontend (misal: "`render/*` tidak boleh import `events/*` secara
langsung") bisa ditegakkan otomatis, bukan sekadar divisualisasikan. `madge`
hanya menghasilkan graph visual tanpa lapisan enforcement, jadi tidak
sejalan dengan pola governance yang sudah dianut project ini.

### 4. Perubahan `web/static/index.html` di Fase 3 — disetujui, dengan syarat

Menyentuh `index.html` untuk mengubah `<script>` menjadi
`<script type="module">` **disetujui**, dengan syarat mengikuti pola sesi
*dedicated* yang sudah dipakai di
`docs/rfc/radio_toggle/task_breakdown_radio.yaml`:

- Dikerjakan dalam sesi tersendiri, tidak dicampur task lain di sesi yang
  sama (`parallel_ok: false`).
- Sebelum sesi berjalan, wajib grep ulang seluruh selector/ID yang dipakai
  file JS lain terhadap `index.html` (pola yang sama seperti aturan sesi 7
  di `task_breakdown_radio.yaml`), karena kode bisa berubah sejak RFC/ADR
  ini ditulis.
- Satu entri `docs/PATCHLOG.md` khusus untuk perubahan ini, terpisah dari
  entri migrasi modul JS individual.

## Alasan Ringkas

Urutan leaf-first meminimalkan radius ledakan tiap langkah migrasi — kalau
ada yang salah di modul awal (misal `utils/format.js`), dampaknya kecil dan
mudah di-rollback, sementara `store.js`/`ws.js`/`main.js` yang paling
berisiko justru dikerjakan setelah pola migrasinya sudah terbukti aman di
modul-modul kecil. Pemilihan `dependency-cruiser` menjaga konsistensi
filosofi governance antara backend dan frontend (deteksi otomatis, bukan
cuma visual). Syarat untuk menyentuh `index.html` menyalin persis pola
governance yang sudah pernah berhasil dipakai project ini di redesign radio
toggle, jadi tidak memperkenalkan proses baru yang belum teruji.

### 5. Operasionalkan doktrin arsitektur yang sudah ada — jangan buat baru, terjemahkan yang lama

`docs/architecture/frontend.md` sudah mendefinisikan **State Flow
Frontend** secara eksplisit (WS masuk → `ws.js` → `render/*`; User Action →
`events/*` → `store.js` → WS send). Doktrin ini **tidak dibuat ulang**, tapi
diterjemahkan langsung menjadi rule `.dependency-cruiser.js` begitu Fase 4
berjalan, minimal:

- `render/*` dilarang import `events/*` secara langsung (arah harus lewat
  `store.js`, sesuai diagram).
- `events/*` dilarang import `render/*` secara langsung untuk alasan yang
  sama.
- Hanya `ws.js` yang boleh melakukan WebSocket send/receive — modul lain
  wajib lewat dia, tidak boleh buka koneksi sendiri.
- `utils/*` tidak boleh import apapun selain modul lain di `utils/*`
  (harus tetap leaf, sesuai peran leaf-first di §2).

Begitu `docs/architecture/frontend.md` diperbarui di masa depan, rule ini
wajib disinkronkan pada patch yang sama — dokumen prosa dan rule
enforcement diperlakukan sebagai satu sumber kebenaran, tidak boleh
menyimpang.

### 6. Type safety — JSDoc + `// @ts-check`, bukan migrasi ke TypeScript

Backend punya `mypy` (`pyproject.toml`); frontend saat ini nol type
checking. Diputuskan: pakai **JSDoc annotation + `// @ts-check`** di setiap
file (dicek lewat `tsc --checkJs --noEmit` sebagai step CI baru), **bukan**
migrasi penuh ke TypeScript. Alasan: ini memberi type-checking nyata tanpa
build step — konsisten dengan alasan inti ADR-0006 ("tidak ada build step,
tidak ada dependency npm runtime"). Urutan penerapan mengikuti urutan
migrasi ES module di §2 (satu file, satu langkah — anotasi JSDoc ditambah
bersamaan saat file itu dikonversi jadi ES module, bukan proyek terpisah).

### 7. Visual regression check untuk kelas bug yang sudah pernah terjadi

Riwayat `docs/rfc/radio_toggle/radio_toggle.md` §2 menunjukkan bug nyata
(ukuran kartu berubah antar state) yang murni disebabkan CSS layout —
kelas bug yang **tidak** tertangkap oleh ESLint, test unit, atau boundary
modul manapun di atas. Diputuskan: tambah **Playwright screenshot diff**
sebagai step CI terpisah (bukan bagian dari Vitest), dibatasi ke 3
komponen dengan riwayat/risiko layout paling tinggi:

1. Radio hero card (`#radio-toggle-btn` / `.radio-featured`) — sumber bug
   §2 di atas.
2. Player bar (`render/player.js`) — komponen paling sering berubah
   ukuran/state (playing, paused, buffering).
3. Now-playing panel (`render/now-playing.js`) — konten dinamis
   (judul/artis panjang) paling berisiko memicu reflow tak terduga,
   pola yang sama seperti akar masalah §2 radio hero.

Screenshot baseline disimpan di repo (`tests/frontend/__screenshots__/`),
diperbarui manual lewat command eksplisit (`--update-snapshots`) — tidak
pernah auto-update di CI, supaya perubahan visual selalu direview sebagai
bagian dari code review, bukan lewat tanpa disadari.

## Konsekuensi

- Fase 1 (ESLint) dan Fase 2 (test coverage) dari RFC bisa mulai dieksekusi
  segera tanpa menunggu apapun — keduanya tidak menyentuh file locked.
- Fase 3 mengikuti urutan migrasi di §2 secara mengikat; anotasi JSDoc
  (§6) ditambahkan pada langkah yang sama, bukan proyek terpisah.
- Fase 4 (`dependency-cruiser`) tidak lagi sekadar "pasang tool" — rule-nya
  sudah ditentukan di §5, jadi begitu Fase 3 cukup jauh, Fase 4 tinggal
  dieksekusi tanpa perlu keputusan desain baru.
- Visual regression (§7) berjalan independen dari 4 fase RFC — bisa mulai
  kapan saja karena tidak bergantung pada migrasi ES module, dan tidak
  menyentuh file locked (hanya menambah test baru).
- `docs/architecture/frontend.md` dan `.dependency-cruiser.js` wajib
  disinkronkan setiap ada perubahan boundary — dokumen prosa tidak lagi
  boleh menyimpang dari rule yang ditegakkan otomatis.
- `task_breakdown_frontend_tooling.yaml` (jika dibuat menyusul) harus
  mereferensikan ADR ini sebagai sumber keputusan tunggal, mencakup semua
  7 poin di atas — tidak perlu lagi menyertakan blok "open questions".
- RFC (`docs/rfc/frontend_tooling/proposal_frontend_tooling.md`) bagian §7
  dianggap **superseded** oleh ADR ini secara keseluruhan, termasuk
  cakupan tambahan (type safety, visual regression) yang tidak ada di RFC
  asli.

## Referensi

- `docs/rfc/frontend_tooling/proposal_frontend_tooling.md` — RFC sumber
- `docs/rfc/radio_toggle/task_breakdown_radio.yaml` — pola sesi dedicated
  & governance-locked yang dijadikan acuan §4
- `docs/rfc/radio_toggle/radio_toggle.md` §2 — riwayat bug CSS layout yang
  mendasari keputusan §7
- `docs/architecture/frontend.md` — doktrin State Flow Frontend yang
  dioperasionalkan di §5
- `AI_CONTEXT.md` — daftar file locked & batasan teknis
- `.importlinter` — pola enforcement backend yang direplikasi lewat
  `dependency-cruiser` di frontend
- `pyproject.toml` (`[tool.mypy]`) — acuan paritas type-checking backend
  yang mendasari §6
