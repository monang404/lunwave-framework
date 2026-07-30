# ADR-0006: Vanilla JavaScript, Bukan React / Vue / Svelte

**Status:** Accepted
**Date:** 2024

---

## Konteks

LunaWave membutuhkan frontend yang berjalan di browser Android (Termux environment) dan dapat menerima update real-time via WebSocket. Opsi framework yang lazim digunakan: React, Vue 3, atau Svelte. Semua ketiganya membutuhkan build step (Vite/Webpack) dan menghasilkan bundle yang harus diserve sebagai static file. Alternatifnya adalah vanilla JavaScript — tidak ada build step, tidak ada dependency npm.

## Keputusan

Frontend LunaWave ditulis dalam **vanilla JavaScript (ES2022+)** tanpa framework, tanpa bundler, tanpa npm dependency runtime. File `.js` diserve langsung dari `web/static/js/` oleh aiohttp.

## Alasan

LunaWave adalah personal tool yang dijalankan di Termux — environment dengan resource terbatas dan tanpa Node.js terpasang secara default. Framework modern membutuhkan build step yang tidak kompatibel dengan workflow ini. Vanilla JS dengan ES modules berjalan langsung di browser modern tanpa kompilasi. State management cukup ditangani dengan `store.js` (plain object + observer pattern) karena state bersumber dari satu `full_state` broadcast — tidak perlu reaktivitas kompleks seperti yang diberikan Vue/React. Kompleksitas framework tidak sebanding dengan kebutuhan satu pengguna, satu layar.

## Konsekuensi

- Tidak ada `node_modules`, tidak ada `package.json` runtime (hanya `devDependencies` untuk Vitest)
- DOM manipulation dilakukan secara eksplisit — lebih verbose, tapi tidak ada magic dan mudah di-debug
- Testing JS difokuskan ke pure function (`utils/format.js`, logic di `store.js`) via Vitest tanpa JSDOM yang berat
- Jika di masa depan UI complexity meningkat signifikan (draggable playlist, animasi kompleks), pertimbangkan migrasi ke Svelte (paling ringan, kompilasi ke vanilla JS)
- File > 200 baris harus dipecah manual — tidak ada tree-shaking otomatis dari bundler

## Referensi

- Struktur frontend: `architecture/frontend.md`
- State management: `frontend/state_management.md`
- Testing frontend: `testing/frontend_testing.md`
- Lihat juga: ADR-0005 (WebSocket single channel)
