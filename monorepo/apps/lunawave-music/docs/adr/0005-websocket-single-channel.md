# ADR-0005: Satu Channel WebSocket untuk Semua State Broadcast

**Status:** Accepted
**Date:** 2024

---

## Konteks

LunaWave perlu mengirimkan pembaruan state secara real-time dari server ke semua browser yang terhubung: posisi playback, status queue, progress download, dan mode radio. Pendekatan yang lazim di aplikasi besar adalah membagi state ke beberapa channel (topic/namespace) agar client hanya subscribe ke yang relevan. Dua opsi dipertimbangkan: (1) multi-channel — setiap domain state punya channel WS sendiri; (2) single-channel — satu koneksi WS, semua state dikirim sebagai satu objek JSON.

## Keputusan

LunaWave menggunakan **satu channel WebSocket** untuk semua komunikasi antara server dan client. Server melakukan broadcast `full_state` — seluruh state aplikasi — setiap kali ada perubahan apapun. Client menerima satu objek JSON dan merender ulang sesuai perubahan.

## Alasan

Untuk personal music player dengan satu pengguna aktif (Termux, layar tunggal), kompleksitas multi-channel tidak memberikan manfaat nyata. Full-state broadcast menyederhanakan frontend secara drastis: tidak perlu menggabungkan state dari banyak sumber, tidak ada partial-update yang menyebabkan inconsistency. Jika state berubah, client selalu mendapat gambaran lengkap — tidak pernah melihat state yang stale dari channel lama. Bandwidth bukan constraint pada localhost.

## Konsekuensi

- `server/broadcast_service.py` selalu serialize seluruh `AppState` — tidak pernah partial
- `ws.js` di frontend memiliki satu entry point `renderFullState(state)` yang menangani semua pembaruan UI
- Menambah domain state baru (contoh: lyrics sync) cukup tambah field ke `AppState` — tidak perlu channel baru
- Jika di masa depan LunaWave jadi multi-user atau multi-room, arsitektur ini perlu direvisi untuk mengurangi broadcast yang tidak perlu
- `server/connection_manager.py` mengelola daftar koneksi aktif; broadcast iterates semua koneksi

## Referensi

- Implementasi: `server/broadcast_service.py`, `server/connection_manager.py`
- Frontend: `js/ws.js`, `js/render/full-state.js`
- State definition: `core/state.py`
- Lihat juga: ADR-0004 (CommandBus), `architecture/data_flow.md`
