# Packaging

> Manajemen dependencies LunaWave — runtime vs development, dan cara menjaga keduanya tetap bersih.
> Untuk CI yang menginstall dependencies ini, lihat → [ci_cd.md](ci_cd.md)

---

## Dua File Requirements

LunaWave memisahkan runtime dependencies dari development dependencies:

| File | Untuk | Diinstall Oleh |
|---|---|---|
| `requirements.txt` | Runtime — yang dibutuhkan untuk **menjalankan** LunaWave | User, CI (production), Docker |
| `requirements-dev.txt` | Development — testing, linting, type checking | Developer, CI (test/lint jobs) |

---

## `requirements.txt` (Runtime)

```text
# requirements.txt
aiohttp>=3.9
aiosqlite>=0.20
yt-dlp>=2024.1
# MPV dikontrol via IPC socket — tidak ada Python binding
```

> **Catatan MPV:** MPV diinstall sebagai system package (`apt install mpv`, `brew install mpv`, dsb.), bukan lewat pip. Tidak ada entry di `requirements.txt`.

---

## `requirements-dev.txt` (Development)

```text
# requirements-dev.txt
-r requirements.txt     # include semua runtime deps

# Testing
pytest>=8.0
pytest-asyncio>=0.23
pytest-cov>=5.0

# Linting & Formatting
ruff>=0.4

# Type Checking
mypy>=1.9

# Security
bandit>=1.7
pip-audit>=2.7

# Architecture
import-linter>=1.12

# Frontend Testing (opsional)
# vitest diinstall via npm, bukan pip — lihat package.json
```

---

## Install

```bash
# Untuk menjalankan LunaWave saja
pip install -r requirements.txt

# Untuk development (testing, linting, dsb.)
pip install -r requirements-dev.txt
```

### Dengan virtual environment (direkomendasikan)

```bash
python -m venv .venv
source .venv/bin/activate     # Linux/macOS
# atau .venv\Scripts\activate  # Windows

pip install -r requirements-dev.txt
```

---

## `pyproject.toml` — Metadata Proyek

Version string disimpan di **satu tempat**: `pyproject.toml → [project] version`.
Semua referensi lain (README badge, docs) pull dari sini.

```toml
[project]
name = "lunawave"
version = "0.1.0"          # ← single source of truth untuk version
description = "Self-hosted Python music player"
requires-python = ">=3.11"
dependencies = [
    "aiohttp>=3.9",
    "aiosqlite>=0.20",
    "yt-dlp>=2024.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.4",
    "mypy>=1.9",
    "bandit>=1.7",
    "pip-audit>=2.7",
    "import-linter>=1.12",
]
```

> Sebagai alternatif `requirements-dev.txt`, bisa juga pakai `pip install -e ".[dev]"` jika menggunakan format `optional-dependencies` di atas.

---

## Audit Dependencies

```bash
# Cek vulnerability di runtime deps
pip-audit -r requirements.txt

# Cek semua deps (termasuk dev)
pip-audit -r requirements-dev.txt
```

Jalankan secara rutin, terutama sebelum release. Sudah terintegrasi di CI — lihat [ci_cd.md](ci_cd.md).

---

## Referensi Terkait

- CI yang menginstall requirements → [ci_cd.md](ci_cd.md)
- Konfigurasi tools di pyproject.toml → [tooling.md](tooling.md)
- Release yang butuh requirements bersih → [release.md](release.md)
