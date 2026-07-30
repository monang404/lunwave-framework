# Onboarding

> Panduan setup LunaWave dari nol — untuk contributor baru atau setup di mesin baru.
> Target: ikuti dokumen ini tanpa pengetahuan sebelumnya tentang proyek, dan LunaWave berjalan dalam < 10 menit.

---

## Prasyarat Sistem

| Dependency | Versi Minimum | Cara Install |
|---|---|---|
| Python | 3.11 | [python.org](https://python.org) atau `pyenv` |
| MPV | terbaru | `sudo apt install mpv` / `brew install mpv` |
| yt-dlp | terbaru | `pip install yt-dlp` atau `brew install yt-dlp` |
| Git | — | bawaan sistem |
| Node.js *(opsional)* | 18+ | Hanya jika ingin jalankan frontend test |

### Verifikasi Prasyarat

```bash
python --version    # → Python 3.11.x atau lebih baru
mpv --version       # → mpv 0.xx.x
yt-dlp --version    # → yt-dlp 20xx.xx.xx
git --version       # → git 2.x
```

---

## Setup Langkah demi Langkah

### 1. Clone Repository

```bash
git clone https://github.com/<user>/lunawave.git
cd lunawave
```

### 2. Buat Virtual Environment

```bash
python -m venv .venv

# Aktifkan (Linux/macOS)
source .venv/bin/activate

# Aktifkan (Windows)
.venv\Scripts\activate
```

Setelah aktif, prompt terminal akan berubah menampilkan `(.venv)`.

### 3. Install Dependencies

```bash
# Runtime saja (untuk menjalankan LunaWave)
pip install -r requirements.txt

# Atau: runtime + dev tools (untuk development)
pip install -r requirements-dev.txt
```

### 4. Inisialisasi Database

```bash
# Database SQLite akan dibuat otomatis saat pertama kali dijalankan
# Tidak ada langkah manual yang diperlukan
```

### 5. Jalankan LunaWave

```bash
python main.py
```

Atau jika tersedia launcher GUI:

```bash
python start.py
```

### 6. Buka di Browser

```
http://localhost:8000
```

LunaWave berjalan. Selesai.

---

## Troubleshooting

### MPV tidak terdeteksi

```
Error: MPV not found or not running
```

**Solusi:**
```bash
# Pastikan mpv ada di PATH
which mpv       # Linux/macOS
where mpv       # Windows

# Jika tidak ada, install:
sudo apt install mpv          # Ubuntu/Debian
brew install mpv              # macOS
```

### yt-dlp gagal resolve URL

```
ERROR: [youtube] ...: Unable to extract info
```

**Solusi:**
```bash
# Update yt-dlp ke versi terbaru
pip install -U yt-dlp
# atau
yt-dlp --update
```

### Port 8000 sudah dipakai

```
OSError: [Errno 98] Address already in use
```

**Solusi:**
```bash
# Cari proses yang memakai port 8000
lsof -i :8000       # Linux/macOS
netstat -ano | findstr :8000   # Windows

# Kill prosesnya, atau ubah port di config
```

### `pkill mpv` tidak bekerja

Jika MPV tidak berhenti saat stop command:
```bash
pkill -f mpv    # gunakan flag -f untuk match full command path
```

---

## Setup Development (Tambahan)

### Install Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

Setelah ini, setiap `git commit` akan otomatis menjalankan ruff, mypy, bandit, dan import-linter.

### Jalankan Test

```bash
# Unit tests
pytest tests/unit/ -v --cov

# Integration tests (butuh MPV + yt-dlp)
pytest tests/integration/ -v

# Frontend tests (butuh Node.js)
npm install -D vitest
npx vitest run tests/frontend/
```

### Struktur Folder

Lihat → [../architecture/folder_structure.md](../architecture/folder_structure.md)

### Cara Baca Kode

Mulai dari titik masuk utama:

```
main.py                  ← titik masuk aplikasi
  └── core/command_bus.py    ← routing semua command
  └── engine/command_router.py  ← dispatch ke handler
  └── server/app.py           ← HTTP + WebSocket server
  └── adapters/mpv/           ← kontrol MPV via IPC
```

Untuk arsitektur lengkap, lihat → [../architecture/overview.md](../architecture/overview.md)

---

## Pertanyaan Umum

**Q: Apakah LunaWave butuh internet?**
A: Ya, untuk resolve URL via yt-dlp dan download track. Playback dari cache bisa offline.

**Q: Di mana file audio disimpan?**
A: `cache/mp3/` — folder ini di-gitignore dan tidak ikut di-commit.

**Q: Di mana database disimpan?**
A: `data/lunawave.db` — juga di-gitignore.

**Q: Bagaimana cara reset database?**
A: Hapus `data/lunawave.db` dan restart. Database baru akan dibuat otomatis.

---

## Referensi Terkait

- Coding standard & konvensi → [coding_standard.md](coding_standard.md)
- Peta risiko perubahan → [project_structure.md](project_structure.md)
- Contributing guide → [../opensource/contributing.md](../opensource/contributing.md)
- Arsitektur overview → [../architecture/overview.md](../architecture/overview.md)
