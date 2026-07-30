# LunaWave

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![MPV](https://img.shields.io/badge/Powered_by-MPV-purple.svg)
![Termux](https://img.shields.io/badge/Optimized_for-Termux-green.svg)

**LunaWave (sebelumnya YT Termux Player/bagas.fm)** adalah aplikasi web pemutar musik YouTube yang didesain secara khusus untuk tampil memukau di layar portrait HP maupun desktop. Aplikasi ini memutar audio di latar belakang menggunakan `mpv` (sebagai *engine*) dan diakses sepenuhnya melalui antarmuka web, sehingga ringan dan hemat kuota internet.

---

## ✨ Fitur Unggulan

- **🎵 Sinkronisasi Lirik Real-Time**: Lirik berjalan otomatis (karaoke style) mengambil data dari LRCLIB.
- **⏭️ SponsorBlock Integration**: Otomatis melompati iklan/sponsor yang disematkan di dalam video YouTube.
- **📻 Smart Radio Autoplay**: Antrean kosong? Aplikasi akan otomatis mencari dan memutar lagu yang relevan tanpa henti. Artis dipilih menggunakan **Thompson Sampling bandit** yang belajar dari selera dengaran Anda.
- **💾 Smart Caching & Download**: Lagu yang pernah diputar atau di-download manual akan disimpan secara lokal. Pemutaran ulang tidak akan menyedot kuota internet.
- **🔊 Loudness Normalization (EBU R128)**: Volume antar lagu diseimbangkan secara otomatis menggunakan standar broadcast EBU R128 (via ffprobe + MPV audio filter).
- **🎯 Discover Personalization**: Tab Discover menampilkan rekomendasi artis yang dipersonalisasi berdasarkan selera dengaran Anda (bandit-ranked + taste spectrum).
- **🌐 Web UI Server-Client (LunaWave)**: Dapat dijalankan sebagai backend server di Termux HP, lalu diakses secara nirkabel dari browser Laptop/PC atau HP lain di jaringan WiFi yang sama.
- **🔒 Portal Akses Ganda (Admin & Client)**:
  - **Admin Mode (`/admin`)**: Membutuhkan login username & password untuk kontrol penuh pemutaran musik.
  - **Client Mode / Dengar Saja (`/`)**: Akses instan tanpa password untuk menampilkan "now playing" dan lirik secara sinkron di perangkat lain.
- **⚡ Arsitektur Enterprise-Ready**: Dibangun dengan *Hexagonal Architecture* (*Ports and Adapters*) dan pola *CommandBus & EventBus*, dirancang untuk personal music player single-user. Struktur *EventBus* sudah menyiapkan fondasi untuk *multi-room* di masa depan (lihat ADR-0005), namun belum aktif di rilis ini. Dilengkapi dengan *Structured Logging* (JSON) untuk kemudahan *troubleshooting*.

---

## 🛠️ Prasyarat Instalasi

Aplikasi ini membutuhkan beberapa program eksternal untuk berjalan:
1. **Python** (versi 3.10 atau lebih baru)
2. **MPV** (sebagai engine pemutar audio utama)
3. **FFmpeg** (untuk ekstraksi dan konversi audio)

### 📱 Instalasi di Android (via Termux)

1. Buka Termux dan perbarui package list:
   ```bash
   pkg update && pkg upgrade -y
   ```
2. Instal dependensi sistem yang dibutuhkan:
   ```bash
   pkg install python mpv ffmpeg git -y
   ```
3. Clone repository ini (atau salin file project ke dalam Termux):
   ```bash
   pkg install socat termux-api -y
   git clone https://github.com/monang404/lunawave.git
   cd lunawave
   ```
4. Instal dependensi Python:
   ```bash
   pip install -r requirements.txt
   ```

### 💻 Instalasi di Windows

1. Pastikan Anda sudah menginstal **Python 3.10+**.
2. Download dan instal **MPV** serta **FFmpeg**. Tambahkan keduanya ke dalam sistem PATH environment variables Anda.
   *(Saran: Gunakan package manager seperti Scoop: `scoop install mpv ffmpeg`)*
3. Buka Command Prompt / PowerShell, masuk ke direktori aplikasi:
   ```cmd
   cd lunawave
   pip install -r requirements.txt
   # (Opsional) Jika ingin menggunakan antarmuka GUI desktop:
   pip install -r requirements-gui.txt
   ```

---

## 🚀 Cara Menjalankan

Dari dalam direktori `lunawave`, pilih salah satu cara:

```bash
# Cara 1 — server langsung (tanpa GUI)
python main.py

# Cara 2 — GUI launcher Tkinter (start/stop visual)
python start.py

# Cara 3 — script shell (Linux / Termux, auto-setup env)
bash start.sh

# Cara 4 — script Windows (CMD/PowerShell)
start.bat
```

> **Info Konfigurasi:** Host dan port default adalah `0.0.0.0` dan `8765`. Anda dapat mengubahnya menggunakan environment variable `LUNAWAVE_HOST` dan `LUNAWAVE_PORT`. Pengecekan preflight juga dapat dijalankan manual via CLI: `python -m launcher.preflight --host 127.0.0.1 --port 8765`.

> **Catatan Windows:** Di Windows, aplikasi akan otomatis membuka koneksi TCP internal ke MPV (via fallback) karena fitur Unix Socket tidak tersedia. Pastikan port lokal tidak terblokir firewall.

### 🌐 Mengakses Antarmuka Web (LunaWave)
Saat Anda menjalankan aplikasi, server web otomatis aktif di latar belakang pada port `8765`.
1. Buka browser di Laptop/PC atau HP lain yang satu jaringan WiFi dengan HP Termux Anda.
2. Untuk mengontrol musik, akses rute `/admin` (Contoh: `http://192.168.1.5:8765/admin`). Mengakses `/` langsung akan membuka tampilan "Dengar Saja" untuk klien.
   - **Dashboard Observabilitas**: Anda dapat memantau kesehatan server dan log secara real-time di `/admin/logs`, sejajar dengan ketersediaan `/health` dan `/metrics`.
3. **Pertama kali dijalankan**, Anda akan diarahkan ke halaman **Initial Setup** untuk membuat akun admin sendiri (username + password minimal 8 karakter). Tidak ada password yang di-generate otomatis lagi — Anda yang menentukannya sendiri, sekali, saat setup.
4. Setelah setup selesai, gunakan kredensial itu untuk login. Untuk provisioning non-interaktif (CI, automated deploy) yang tidak bisa lewat wizard browser, kredensial awal juga bisa di-set via Environment Variable `LUNAWAVE_ADMIN_USER` dan `LUNAWAVE_ADMIN_PASS` — jalur ini hanya aktif kalau akun admin belum pernah dibuat.
5. Klik tombol **`🚪 Keluar`** di pojok kanan atas UI Web untuk logout.

> **⚠️ Catatan Upgrade (dari versi sebelum Fitur B / login redesign):**
> Kredensial admin lama (`cache/admin_password.txt` atau
> `instance/admin_password.txt`) **tidak dimigrasikan secara otomatis**.
> Setelah upgrade, Anda akan logout paksa dan diarahkan ke Initial Setup
> lagi untuk membuat akun admin baru — ini perilaku yang disengaja, bukan
> bug. Alasan lengkap: [ADR-0008](docs/adr/0008-admin-credentials-in-sqlite.md).

### 🔒 Deployment Aman (HTTPS / WSS Publik)
Secara default, LunaWave berjalan di `http://` (teks biasa). Jika Anda ingin mengakses server ini dari luar jaringan WiFi rumah (Internet), **SANGAT DISARANKAN** untuk mengamankannya dengan HTTPS. Anda dapat menggunakan *Reverse Proxy* seperti Nginx, Caddy, atau layanan tunneling:
- **Ngrok / Tailscale / Cloudflare Tunnels**: Cara termudah menghubungkan server Termux Anda ke internet menggunakan enkripsi dari ujung ke ujung tanpa perlu setting port-forwarding manual.
- **Contoh Nginx Reverse Proxy**:
  Arahkan trafik HTTPS ke port `8765`, dan pastikan Anda me-*proxy* *header* WebSocket (`Upgrade: websocket`) agar *streaming* lirik dan perintah admin tidak terputus.

---

## 🎮 Panduan Penggunaan (Controls)

Setelah aplikasi berjalan, Anda dapat mengontrol pemutaran melalui sentuhan jari/mouse secara langsung pada elemen layar (klik tombol, *progress bar*, antrean) atau menggunakan tombol pintasan *keyboard* berikut:

### 🔍 Mencari Lagu
- Akses **Tab Pencarian** pada antarmuka web.
- Ketik nama lagu atau artis (Contoh: `coldplay yellow`).
- Klik hasil pencarian untuk memutar lagu dan menambahkannya ke antrean.

### 🎧 Kontrol Pemutaran
Gunakan tombol-tombol yang tersedia di **Player Bar** bagian bawah web UI untuk:
- Pause / Resume
- Next / Previous
- Menggeser (Seek) progress lagu
- Mengatur volume
- Toggle antrean (Queue)
- Mengaktifkan Radio Mode (Autoplay)
- Menampilkan Lirik Sinkron

---

## 📖 Dokumentasi Lengkap

Dokumentasi teknis lengkap ada di folder `docs/` — mulai dari arsitektur, API WebSocket, keamanan, hingga panduan kontribusi.

Baca `docs/INDEX.md` sebagai titik masuk navigasi.

---

## 📁 Struktur Direktori & Sistem Log

Aplikasi ini menggunakan sistem *smart caching* dan memiliki sistem log tingkat lanjut:
- `data/lunawave.db` : Database SQLite penyimpan metadata track, riwayat putar, artis, genre, dan sesi login.
- `cache/mp3/<video_id>.mp3` : File audio hasil unduhan manual. Folder ini aman untuk dihapus kapanpun untuk menghemat ruang penyimpanan.
- `lunawave.log` : Berkas log aplikasi dalam format JSON (Structured Logging) untuk observabilitas yang mudah dibaca oleh mesin/developer.

Anda bisa menghapus isi folder `cache/mp3/` kapanpun jika ingin menghemat ruang penyimpanan.

---

## 📄 Lisensi

Didistribusikan di bawah lisensi MIT. Anda bebas memodifikasi, mendistribusikan, dan menggunakannya secara pribadi maupun komersial.

## 🤝 Berkontribusi & Arsitektur

Bagi para *developer* atau agen AI yang ingin berkontribusi, sangat diwajibkan untuk membaca dokumen berikut demi menjaga kualitas dan konsistensi kode:
- **[Panduan Kontribusi (CONTRIBUTING.md)](CONTRIBUTING.md)**
- **[Penjelasan Arsitektur (docs/INDEX.md)](docs/INDEX.md)**

---
Enjoy your web music experience! 🎶
