---
title : LunaWave Project Report
last_verified: 2026-07-29
sprint: 3.3
warning: temuan di bawah mungkin sudah berubah, cek kolom STATUS per-item
---

# REPORT.md — LunaWave Analysis Report

> **Tanggal Scan:** 2026-07-29
> **Sumber:** Source code (timpa.rar) + `PROJECT_STRUCTURE_AUDIT.md` + existing docs
> **Sprint aktif saat scan:** Sprint 3.2 (selesai) + Minor UI Patch

---

## Statistik Project

> ⚙️ Blok ini di-generate otomatis oleh `automation/generate_report.py`. **Jangan edit manual.**
> Jalankan `python automation/generate_report.py` untuk memperbarui.

<!-- BEGIN:GENERATED -->
> **Auto-generated:** 2026-07-29 oleh `automation/generate_report.py`  
> **Jangan edit blok ini secara manual.**


| Metrik | Nilai |
|--------|-------|
| Total folder (ekskl. `__pycache__`, `.git`) | 77 |
| Total file `.py` (source, ekskl. `__pycache__`) | 135 |
| Total file `.js` (ekskl. `.min.js`) | 61 |
| Total file `.css` (ekskl. `.min.css`) | 26 |
| Total class (Python) | 115 |
| Total function/method (Python) | 615 |
| Total baris Python | 16,556 |
| Total baris JS (web/) | 6,972 |
| Total baris CSS (web/) | 4,615 |
| Ukuran DB utama (`data/lunawave.db`) | tidak ditemukan |
| Ukuran DB library (`cache/library.db`) | tidak ditemukan |

### File Python Terbesar

| File | Baris |
|------|-------|
| `persistence/discover_repo.py` | 461 |
| `engine/playback/controller.py` | 386 |
| `launcher/gui_qt/main_window.py` | 323 |
| `server/handlers/websocket.py` | 320 |
| `server/handlers/audio_stream_handler.py` | 289 |
<!-- END:GENERATED -->

---

## Entry Point

| Jalur | Keterangan |
|-------|------------|
| `main.py` | Backend utama — `asyncio.run(main())` |
| `start.py` → `launcher/__main__` | GUI launcher Tkinter (fallback headless ke `main.py`) |
| `start.sh` / `start.bat` | Shell launcher Linux/Termux & Windows |

---
