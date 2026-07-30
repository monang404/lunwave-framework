# ADR-0001: MPV Dikontrol via IPC Socket, Bukan Subprocess Direct

**Status:** Accepted
**Date:** 2024

---

## Konteks

LunaWave perlu mengontrol playback audio secara real-time: play, pause, seek, skip, volume, dan menerima event posisi dari player. Dua pendekatan utama tersedia: (1) subprocess — spawn `mpv` dengan argument CLI, kill dan re-spawn untuk setiap command; atau (2) IPC socket — spawn `mpv` sekali dengan `--input-ipc-server`, kirim command JSON ke socket yang persisten.

## Keputusan

MPV dikontrol via **IPC socket** (`--input-ipc-server`). MPV di-spawn sekali saat server start, dan semua command (play, pause, seek, volume) dikirim sebagai JSON ke Unix domain socket yang persisten.

## Alasan

Subprocess approach mengharuskan kill-and-respawn untuk setiap track baru, yang menyebabkan gap audio, kehilangan state (volume, mode), dan tidak memungkinkan real-time event seperti posisi playback. IPC socket memberikan komunikasi bidireksional: LunaWave bisa mengirim command dan menerima event (`time-pos`, `eof-reached`, `pause`) secara asinkron tanpa gap.

## Konsekuensi

- MPV harus di-spawn dengan flag `--input-ipc-server=/tmp/lunawave-mpv.sock`
- Adapter MPV harus menangani reconnect jika socket terputus
- `pkill -f mpv` diperlukan (bukan `pkill mpv`) untuk match full path command
- Test unit untuk adapter MPV membutuhkan mock Unix socket, bukan MPV asli

## Referensi

- Implementasi: `adapters/mpv/connection.py`, `adapters/mpv/ipc.py`
- Test: `tests/unit/adapters/mpv/test_ipc.py`
