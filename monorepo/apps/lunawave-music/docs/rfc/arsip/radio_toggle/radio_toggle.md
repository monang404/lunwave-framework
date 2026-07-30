# RFC: Redesain Radio Toggle ("Night Dial") + Fix Bug Ukuran On/Off

**Status:** Draft — belum diimplementasikan
**Konteks:** Baseline diambil dari `lunawave-develop.zip` (restore setelah sesi sebelumnya menyebabkan regresi baru: tombol "on" makin kecil + `playback_sync` sering error). Desain baru diambil dari mockup `lunawave-hero-creative-v8.html` ("Night Dial" — bulan sabit sebagai tuner radio berbasis fase bulan astronomis nyata).

---

## 1. Ringkasan Masalah

Ada dua masalah yang harus diselesaikan bersamaan:

1. **Bug lama (baseline):** ukuran kartu "Featured Station Hero" (`#radio-toggle-btn`, class `.radio-featured`) berbeda antara state off dan on — state on tampak lebih kecil.
2. **Regresi sesi lalu (sudah di-revert):** percobaan fix sebelumnya membuat bug ukuran makin parah *dan* memunculkan bug baru: `playback_sync` sering error. Karena sudah di-restore ke baseline, diagnosis di bawah untuk poin ini bersifat **hipotesis berbasis arsitektur** (tidak ada diff sesi itu untuk dianalisis langsung) — ditandai eksplisit di §3.

Tujuan RFC ini: akar masalah #1 dijelaskan by design (dapat diverifikasi dari kode baseline), dan desain baru diadopsi dengan cara yang secara struktural mencegah #1 dan #2 terulang.

---

## 2. Root Cause Bug #1 (ukuran on/off beda) — dari kode baseline

File terkait: `web/static/index.html` (markup, baris ~298–322), `web/static/css/components/cards.css` (baris 21–253), `web/static/js/render/radio-tab.js`.

**Struktur box saat ini:**

```css
.radio-featured {
  min-height: 160px;      /* bukan height tetap */
  padding: var(--s8) var(--s6);
  display: flex; align-items: center; justify-content: center;
}
.radio-centerpiece { height: 64px; }   /* ini FIXED, aman */
```

`.radio-featured` **tidak punya `height` tetap**, hanya `min-height: 160px`. Tinggi aktual mengikuti konten (`.radio-featured-inner` adalah flex column). Konten yang variabel adalah teks subtitle:

```js
// radio-tab.js
if (isRadio) {
    dom.rtSub.textContent = (store.status === "LOADING")
        ? "Mencari stasiun..."
        : "24/7 Nonstop Music";      // 19 karakter
} else {
    dom.rtSub.textContent = "Aktifkan untuk putar otomatis";  // 30 karakter
}
```

Pada lebar kartu yang sempit (mobile — konteks utama app ini), string off (`"Aktifkan untuk putar otomatis"`, 30 karakter) jauh lebih berpotensi wrap ke 2 baris dibanding string on (`"24/7 Nonstop Music"`, 19 karakter). Ketika off wrap ke 2 baris, tinggi total `.radio-featured-inner` bertambah → kartu off jadi lebih tinggi dari `min-height`. Ketika on, subtitle 1 baris → kartu on jatuh tepat ke `min-height: 160px` → **terlihat lebih kecil**.

Kontributor sekunder (tidak mengubah box size, tapi menambah kesan "mengecil"):
- `.radio-featured.on` menambahkan `box-shadow: 0 8px 32px rgba(242,181,68,0.08)` yang bocor keluar batas kartu — efek glow di luar kartu bisa membuat mata membaca proporsi kartu sebagai lebih kecil relatif terhadap glow-nya.
- `.centerpiece-icon-wrap` dan `.centerpiece-icon` dianimasikan dengan `transform: scale(1.08)` saat on (`pulse-antenna`) — ini transform visual (tidak mereflow layout), tapi berjalan bersamaan dengan reflow dari poin subtitle di atas sehingga user mempersepsikannya sebagai satu gerakan "mengecil".

**Kesimpulan:** ini bukan bug animasi CSS yang salah, melainkan **layout yang content-driven tanpa height tetap**, dikombinasikan dengan dua string subtitle yang panjangnya jauh berbeda. Ini juga menjelaskan kenapa masalah terasa tidak konsisten antar device — murni fungsi dari lebar viewport vs panjang teks di font yang dipakai.

---

## 3. Hipotesis Regresi Sesi Sebelumnya (⚠️ tidak terverifikasi langsung, baseline sudah di-restore)

Karena kode sesi itu tidak ada lagi untuk diperiksa, ini adalah dugaan berbasis pola arsitektur project, bukan fakta yang dikonfirmasi dari diff:

- **"Makin kecil":** kemungkinan perbaikan sebelumnya menambah lebih banyak konten dinamis (badge, teks status baru) ke dalam kartu tanpa memberi `.radio-featured` height tetap — memperparah akar masalah §2, bukan menghilangkannya.
- **`playback_sync` sering error:** kemungkinan animasi baru (loop `requestAnimationFrame` untuk efek visual) diikat ke path kode yang sama dengan progress clock (`web/static/js/render/player.js` — `startProgressClock()`/`tick()`, sudah berjalan terus-menerus ~60fps untuk posisi playback) atau ke `store.position` / `resetAnchorClock()` / `setPositionAnchor()`. Kalau loop animasi baru membaca/menulis state yang sama dengan anchor clock, atau dipanggil dari `renderRadio()` yang di-trigger berkali-kali per detik (mis. lewat WS `full-state`), race condition antar dua rAF loop bisa menjelaskan symptom "sering error" di `playback-sync.js`.

**Implikasi untuk desain baru:** wajib isolasi total antara loop animasi hero baru dan sistem playback-sync — lihat §5.4 dan §6 (Aturan Integrasi Non-Negotiable).

---

## 4. Kenapa Desain "Night Dial" (v8) Cocok Jadi Fix, Bukan Cuma Reskin

Dibanding markup lama, desain baru di `lunawave-hero-creative-v8.html` punya karakteristik yang langsung menghilangkan akar masalah §2:

| Aspek | Baseline lama | Desain baru (v8) |
|---|---|---|
| Tinggi kartu | `min-height: 160px` (content-driven) | `height: 322px` **tetap**, tidak bergantung konten |
| Subtitle | Mengubah panjang teks 2 baris vs 1 baris → reflow | `.hero-sub { min-height: 14px }`, teks pendek konsisten, tidak pernah wrap dalam praktik |
| Tag "ON AIR" | Selalu di DOM, `opacity` di-toggle (masih ambil ruang layout kalau ada bug reflow lain) | `visibility: hidden` + `opacity: 0` + delay — benar-benar tidak render, tapi tetap `position: absolute` jadi **tidak memengaruhi flow** kartu sama sekali |
| Animasi state on | `transform: scale()` pada elemen + reflow subtitle bersamaan | Seluruhnya `transform` / `opacity` / `filter` / atribut `d` path SVG — komentar di kode sumber mockup eksplisit menegaskan "tidak ada reflow yang mengganggu stabilitas layout" |
| Sumber loop animasi | CSS keyframes only | CSS keyframes (starfield, tick, glow) **+** 1 rAF loop JS mandiri untuk fase bulan (`stepCycle`/`stepTween`) — perlu diisolasi, lihat §5.4 |

Dengan `height` tetap dan tidak ada elemen yang bisa memicu wrap konten, kelas masalah di §2 **tidak bisa terjadi lagi secara struktural** — bukan hanya "diperbaiki untuk kasus ini".

---

## 5. Rencana Implementasi

### 5.1 Peta Elemen Lama → Baru

Kunci: **pertahankan `id="radio-toggle-btn"`, `data-on`, dan `id="rt-sub"` apa adanya.** Ini dipakai oleh kode lain yang tidak boleh disentuh tanpa alasan kuat:
- `web/static/js/platform/touch.js:18` — selector swipe-gesture guard `#radio-toggle-btn`
- `web/static/js/dom.js:54-56` — `dom.radioToggleBtn`, `dom.rtSub`
- `web/static/js/events/transport-events.js:91-99` — satu-satunya pemilik event click (role admin check, `wsSend("set_mode")`)
- `web/static/js/render/radio-tab.js` — satu-satunya pemilik penulisan class `on`/`off` dan `data-on`

| Elemen lama | Elemen baru (dari mockup) | Catatan |
|---|---|---|
| `#radio-toggle-btn.radio-featured` | `#radio-toggle-btn.radio-hero` (rename class internal, id tetap) | Ganti nama class `.hero` → `.radio-hero` supaya tidak bentrok dengan kemungkinan class generik `.hero` lain di project (grep dulu, lihat §5.2) |
| `.radio-live-badge` (LIVE, top-right) | `.onair-tag` (ON AIR, top-right) | Fungsinya sama; boleh ganti teks jadi "LIVE" saja atau ikut "ON AIR" — **keputusan produk, tanyakan ke user**, lihat §8 |
| `.centerpiece-icon` (`ti-broadcast`) + `.centerpiece-waves` kiri/kanan | `<svg class="dial-svg">` bulan + tuner ticks | Ganti total, bukan reskin icon |
| `.radio-featured-name` ("LunaWave") | `.hero-name` ("Radio Mode") | **Keputusan produk**: pakai "LunaWave" (branding) atau "Radio Mode" (fungsional)? Lihat §8 |
| `#rt-sub` | `#rt-sub` (id dipertahankan, class `.hero-sub`) | Teks tetap dikontrol oleh `radio-tab.js`, **bukan** oleh script mockup (lihat §5.3) |
| `#radio-toggle-wrap` (hidden, kompatibilitas) | tetap dipertahankan apa adanya, tidak disentuh | Di luar scope |

### 5.2 File yang Disentuh

```
web/static/index.html                          — ganti blok markup #radio-toggle-btn
web/static/css/components/cards.css             — hapus blok lama (baris ~1-253, section "RADIO TAB" bagian hero)
web/static/css/components/radio-hero.css        — [NEW] seluruh style hero baru, di-porting dari <style> mockup
web/static/js/render/radio-hero-moon.js         — [NEW] logika fase bulan + rAF loop, terisolasi
web/static/js/render/radio-tab.js               — tambah 1 baris pemanggilan hook animasi (lihat §5.3)
docs/PATCHLOG.md                                — entry patch setelah implementasi selesai & diverifikasi
```

Sebelum menghapus apa pun dari `cards.css`, jalankan ulang grep berikut untuk memastikan tidak ada dependensi lain yang terlewat (sudah dicek sekali untuk RFC ini, ulangi lagi saat eksekusi karena kode bisa berubah):

```bash
grep -rn "centerpiece\|radio-live-badge\|radio-featured" web/static/js/ web/static/index.html
```

Load order CSS: sisipkan `radio-hero.css` tepat setelah `cards.css` di `<head>` (index.html baris ~33), supaya token global (`tokens.css`) sudah termuat lebih dulu dan style hero baru bisa reuse variable existing alih-alih mendefinisikan ulang.

### 5.3 Integrasi JS — Aturan Pembagian Tanggung Jawab

Ini bagian paling kritis untuk mencegah regresi §3 terulang. Prinsipnya: **satu state, satu pemilik.**

**`radio-tab.js` (tidak berubah fungsinya, cuma nambah 1 hook):**
- Tetap satu-satunya pemilik `classList.add/remove("on"/"off")`, `dataset.on`, dan `dom.rtSub.textContent`.
- Tambah pemanggilan opsional ke modul animasi baru, mengikuti pola `typeof` check yang sudah jadi konvensi di codebase ini:

```js
function renderRadio() {
    const isRadio = store.playback_mode === 'RADIO';

    if (dom.radioToggleBtn) {
        // ...logika class on/off yang sudah ada, tidak berubah...
    }

    if (dom.rtSub) {
        // ...logika teks yang sudah ada, tidak berubah...
    }

    // NEW — hook satu arah, hanya kirim boolean, tidak ada state lain yang dibagi
    if (typeof setRadioHeroAnimState === "function") {
        setRadioHeroAnimState(isRadio);
    }
}
```

**`radio-hero-moon.js` (baru, self-contained):**
- Query elemen SVG sendiri via `document.getElementById` saat modul dimuat — **tidak** menambah entry ke `dom.js` supaya tidak ada 2 sumber kebenaran untuk elemen yang sama.
- Ekspos **hanya satu** fungsi publik: `setRadioHeroAnimState(isOn)`. Fungsi ini **tidak boleh**:
  - menyentuh `classList` dari `#radio-toggle-btn` (itu domain `radio-tab.js`)
  - membaca/menulis `store.*` apa pun
  - memanggil `resetAnchorClock()`, `setPositionAnchor()`, `wsSend()`, atau fungsi apa pun dari `playback-sync.js` / `player.js`
  - menulis ke `dom.rtSub.textContent` (di mockup, script demo melakukan ini untuk teks "Menyetel frekuensi..." dll — **ini harus dihapus saat porting**, karena akan race dengan `radio-tab.js` yang menulis elemen yang sama)
- **Hapus dari hasil porting:** `hero.addEventListener('click', ...)` dan `keydown` handler di script mockup — event click sudah dipegang penuh oleh `transport-events.js` (termasuk role-check admin dan `wsSend("set_mode")`). Kalau handler klik mockup ikut terbawa, toggle akan double-fire atau bypass guard admin.
- rAF loop (`stepCycle`/`stepTween`) memakai `let rafId` **lokal ke modul ini saja** (module-scope closure, bukan variabel global) — supaya mustahil bentrok nama/state dengan `_progressRafId` di `player.js`.

### 5.4 Isolasi dari `playback-sync.js` — Checklist Wajib

Sebelum PR/patch dianggap selesai, verifikasi eksplisit satu per satu (ini yang gagal diverifikasi di sesi sebelumnya, dugaan §3):

- [ ] `grep -n "requestAnimationFrame" web/static/js/render/radio-hero-moon.js` → hanya ada di dalam modul ini, `rafId` bukan `window.rafId` global.
- [ ] `radio-hero-moon.js` tidak mengimpor/memanggil apa pun dari `playback-sync.js` atau `player.js`.
- [ ] `renderRadio()` tetap hanya dipanggil dari 4 tempat yang sudah ada (`ws.js:261`, `full-state.js:28`, `transport-events.js:97,114`) — **tidak** ditambah pemanggilan baru dari dalam loop 60fps manapun.
- [ ] Uji manual: toggle radio ON, biarkan lagu jalan >2 menit, pantau console — tidak ada error dari `playback-sync.js` (khususnya sekitar `getInterpolatedPosition()`, `_progressRafId`).
- [ ] Uji manual: toggle radio ON/OFF berkali-kali cepat (spam click) — tidak ada `rafId` yang menumpuk (cek lewat `performance` tab / memory tidak naik terus).

### 5.5 Adaptasi Desain dari Mockup Standalone → Project

Mockup adalah file HTML standalone dengan asumsi yang tidak berlaku di project ini:

1. **Font eksternal.** Mockup memuat Google Fonts (`Fraunces`, `Space Grotesk`) via `<link>` ke `fonts.googleapis.com`. Project ini **tidak** memakai font eksternal (cek `tokens.css` — `--font: 'Inter', 'SF Pro Display', system-ui, sans-serif`, semua system font). LunaWave didesain untuk self-hosted/local network (lihat konteks Termux/offline di project ini). **Rekomendasi: drop `<link>` Google Fonts, ganti `--font-display` dan `--font-mono` di CSS baru supaya fallback ke `var(--font)` yang sudah ada**, kecuali user secara eksplisit mau font itu dan siap self-host filenya (taruh di `web/static/fonts/` + `@font-face`, bukan CDN).
2. **CSS variable baru vs reuse token existing.** Mockup mendefinisikan `--void`, `--moon-light`, `--moon-glow`, dst di scope `:root` lokalnya sendiri. Beberapa sudah punya padanan di `tokens.css`:
   - `--moon-glow: #F2B544` **identik** dengan `--accent: #F2B544` yang sudah ada → pakai `var(--accent)`, jangan definisikan ulang.
   - `--text-1`, `--text-2`, `--r-full` juga sudah ada di `tokens.css` dengan nilai yang sama/mirip → reuse, jangan duplikasi.
   - `--void` (`#0B0B10`) dan `--indigo-deep` (`#211C36`) memang baru, boleh ditambah scoped ke `radio-hero.css` saja (tidak perlu masuk `tokens.css` global kalau cuma dipakai di komponen ini).
3. **Fixed width mockup (`max-width:420px`) vs lebar app sebenarnya.** Mockup adalah halaman demo lebar tetap. Cek lebar container tab Radio di app sebenarnya (`#tab-radio` di dalam `.tab-panel`) sebelum commit ke `height: 322px` — kalau container lebih sempit dari yang diasumsikan mockup, rasio SVG `viewBox="0 0 172 172"` tetap aman (SVG scalable), tapi padding/posisi starfield (`top`/`left` dalam px absolut) mungkin perlu disesuaikan atau di-scale relatif.
4. **`role="button" tabindex="0" aria-pressed`** di elemen `.hero` pada mockup — baseline lama (`#radio-toggle-btn`) tidak punya atribut aksesibilitas ini sama sekali (cuma `style="cursor:pointer"`). Ini peningkatan a11y yang valid untuk dibawa masuk, tapi `aria-pressed` harus di-drive oleh `radio-tab.js` (sinkron dengan `dataset.on`), bukan oleh script mockup yang akan dihapus.
5. **`prefers-reduced-motion`.** Project sudah punya kill-switch global di `web/static/css/base/animations.css` yang mematikan semua CSS animation/transition. Itu otomatis mencakup starfield twinkle, tick pulse, dll di CSS baru — tidak perlu media query duplikat di `radio-hero.css`. Tapi rAF JS (`stepCycle`) **tidak** kena media query CSS, jadi baris `const reduceMotion = window.matchMedia(...)` dari mockup **wajib** dipertahankan di `radio-hero-moon.js`.

---

## 6. Aturan Integrasi Non-Negotiable (Ringkasan)

1. `radio-tab.js` tetap satu-satunya pemilik state on/off (class, `data-on`, teks subtitle).
2. `radio-hero-moon.js` hanya menerima boolean lewat `setRadioHeroAnimState(isOn)` — tidak baca/tulis `store`, tidak panggil `wsSend`, tidak sentuh anchor clock.
3. Hapus total click/keydown handler dari hasil porting mockup — klik tetap 100% milik `transport-events.js`.
4. `.radio-hero` (nama baru untuk `.radio-featured`) wajib `height` tetap, bukan `min-height` — ini yang menutup akar bug §2 secara struktural.
5. Tidak ada font/asset eksternal (CDN) ditambahkan tanpa persetujuan eksplisit — self-hosted app.

---

## 7. Rencana Pengujian

- [ ] Ukur tinggi kartu via DevTools di state off dan on — harus identik (karena `height` fixed, ini seharusnya trivial pass, tapi tetap diverifikasi visual).
- [ ] Coba subtitle terpanjang yang mungkin muncul ("Mencari stasiun...") dan terpendek, pastikan tidak overflow keluar card pada lebar viewport tersempit yang didukung (cek breakpoint di `platform/mobile.css`, `max-width: 480px` dan `600px`).
- [ ] Toggle lewat klik, lewat keyboard shortcut `R` (`keyboard-shortcut-events.js`), dan lewat swipe-gesture guard (`touch.js`) — pastikan ketiganya tidak berubah behavior.
- [ ] Non-admin user (role viewer) klik kartu — pastikan tetap tidak bisa toggle (guard di `transport-events.js` tidak boleh ter-bypass oleh handler baru).
- [ ] Checklist §5.4 (isolasi playback-sync) di atas — wajib semua tercentang sebelum dianggap selesai.
- [ ] Test dengan `prefers-reduced-motion: reduce` aktif di OS — starfield/tick/glow harus berhenti, rAF fase bulan harus fallback ke render statis (tanpa loop).
- [ ] Regenerasi/patch `docs/PATCHLOG.md` sesuai konvensi `PATCH-YYYY-MM-DD-NNN` setelah implementasi nyata (bukan bagian dari RFC ini).

---

## 8. Keputusan Produk yang Perlu Dikonfirmasi Sebelum Eksekusi

- **Label kartu:** pertahankan branding "LunaWave" (baseline) atau ganti ke "Radio Mode" (mockup)?
- **Badge status:** teks "LIVE" (baseline) atau "ON AIR" (mockup)? Fungsinya identik, cuma copy.
- **Font display (`Fraunces` italic serif untuk nama):** pakai font sistem existing (rekomendasi RFC ini, konsisten dengan §5.5 poin 1), atau self-host font baru demi look yang lebih distinctive dari mockup?
- **Ukuran final kartu:** `height: 322px` dari mockup diasumsikan untuk demo standalone — perlu dicek langsung di layout `#tab-radio` project sebelum dikunci, khususnya di viewport pendek (landscape mobile, ada `platform/landscape.css` terpisah yang mungkin perlu penyesuaian).

Setelah poin-poin ini dikonfirmasi, implementasi bisa langsung dieksekusi mengikuti §5 tanpa keputusan desain yang menggantung di tengah jalan.
