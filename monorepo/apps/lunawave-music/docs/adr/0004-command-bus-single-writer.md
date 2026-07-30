# ADR-0004: CommandBus dengan Pola Single-Writer

**Status:** Accepted
**Date:** 2024

---

## Konteks

LunaWave memiliki banyak sumber command yang berjalan konkuren: WebSocket handler (dari browser), radio engine (auto-next track), dan download manager (notifikasi selesai). Semua sumber ini bisa mengubah state playback pada waktu bersamaan. Dua pendekatan dipertimbangkan: (1) akses langsung — setiap komponen memanggil method engine secara langsung; (2) command bus — semua command dikirim melalui satu saluran terpusat.

## Keputusan

Semua mutasi state dialirkan melalui **`CommandBus`** di `core/command_bus.py`. Tidak ada komponen yang memanggil method engine secara langsung dari luar. CommandBus menggunakan `asyncio.Queue` — satu producer boleh banyak, satu consumer (single-writer).

## Alasan

Akses langsung ke engine dari banyak coroutine konkuren menyebabkan race condition: dua command bisa mengubah state di antara `await` yang sama, menghasilkan state yang tidak konsisten. Pola single-writer via `asyncio.Queue` memastikan command diproses satu per satu secara berurutan, tanpa perlu lock eksplisit. Ini juga menjaga dependency direction tetap bersih — `server/` tidak perlu import `engine/` secara langsung.

## Konsekuensi

- Semua command harus didefinisikan sebagai konstanta `CMD_*` di `core/commands.py`
- `command_router.py` di `engine/` adalah satu-satunya subscriber CommandBus yang memproses command
- Latency satu hop bertambah (antrian), tapi tidak terasa pada skala personal project
- Test command flow cukup: publish ke CommandBus → assert effect via EventBus, tanpa mock engine secara langsung
- Debugging lebih mudah: log seluruh antrian command untuk mereproduksi urutan yang menyebabkan bug

## Referensi

- Implementasi: `core/command_bus.py`, `core/commands.py`
- Consumer: `engine/command_router.py`
- Test: `tests/unit/core/test_command_bus.py`, `tests/unit/engine/test_command_router.py`
- Lihat juga: ADR-0003 (Hexagonal Ports), ADR-0005 (WebSocket single channel)
