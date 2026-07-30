# Technology Stack

← [architecture/overview.md](overview.md) | [Blueprint.md](../Blueprint.md)

---

## Backend

| Teknologi | Versi | Peran | Alasan |
|---|---|---|---|
| Python | 3.11+ | Runtime utama | `asyncio` matang, type hints kuat, ekosistem audio/media luas |
| FastAPI | latest | Web framework | ASGI native, WebSocket built-in, Pydantic integration |
| Uvicorn | latest | ASGI server | Performa tinggi, asyncio-native |
| SQLite | built-in | Database | Zero-setup, cukup untuk single-user player, backup trivial |
| MPV | system | Audio/video player | Powerful, scriptable via IPC socket, support semua format |
| yt-dlp | latest | Media extractor | Fork yt-dlp aktif di-maintain, support ratusan sumber |

### Dev & Tooling

| Teknologi | Peran |
|---|---|
| pytest | Test runner |
| pytest-asyncio | Async test support |
| pytest-cov | Coverage report |
| ruff | Linter & formatter (menggantikan flake8 + black) |
| mypy | Static type checker |
| bandit | Security linter |
| pip-audit | Dependency vulnerability audit |
| import-linter | Penegakan aturan dependency antar layer |
| pre-commit | Git hook runner |

---

## Frontend

| Teknologi | Versi | Peran | Alasan |
|---|---|---|---|
| Vanilla JS | ES2022+ | UI logic | Tidak ada build step, tidak ada dependency drift |
| CSS (native) | Custom Properties | Styling | Design tokens via `tokens.css`, tidak perlu preprocessor |
| WebSocket API | built-in | Komunikasi real-time | Native browser, tidak perlu library |
| Web Audio API | built-in | Visualizer | Native browser |
| PWA (Manifest + SW) | built-in | Offline & installable | Native browser |
| Tabler Icons | 3.x | Icon set | SVG inline, ringan, konsisten |

**Tidak digunakan (dan alasannya):**

| Yang Tidak Dipakai | Alasan |
|---|---|
| React / Vue / Svelte | DOM statis, overhead tidak perlu. Lihat [ADR-0006](../adr/0006-vanilla-js-over-framework.md) |
| Webpack / Vite | Tidak ada build step = tidak ada dependency drift |
| TypeScript | Overhead setup tidak sepadan untuk project ini; `JSDoc` cukup |
| Sass / Less | CSS Custom Properties sudah cukup untuk design tokens |
| jQuery | Tidak perlu untuk codebase ini |

---

## Infrastructure

| Teknologi | Peran | Alasan |
|---|---|---|
| Docker | Packaging & distribusi | Reproducible environment |
| GitHub Actions | CI/CD | Gratis untuk open source, YAML-based |
| GHCR | Docker registry | Gratis untuk open source, satu platform dengan GitHub |
| Git + GitHub | Version control & hosting | Standar industri |

---

## Sistem Operasi yang Didukung

| OS | Status | Catatan |
|---|---|---|
| Linux | ✅ Utama | MPV tersedia via package manager |
| macOS | ✅ Didukung | MPV via Homebrew |
| Windows | ⚠️ Eksperimental | MPV tersedia, perlu testing lebih |

---

## Dependency Runtime vs Dev

### `requirements.txt` (runtime)

```
fastapi
uvicorn[standard]
yt-dlp
```

### `requirements-dev.txt` (development)

```
pytest
pytest-asyncio
pytest-cov
ruff
mypy
bandit
pip-audit
import-linter
pre-commit
httpx          # untuk test HTTP client
```

Detail pyproject.toml → [devops/packaging.md](../devops/packaging.md)

---

## Keputusan Stack yang Didokumentasikan sebagai ADR

- [ADR-0001](../adr/0001-mpv-ipc-over-subprocess.md) — MPV via IPC, bukan subprocess biasa
- [ADR-0002](../adr/0002-sqlite-over-json-cache.md) — SQLite, bukan JSON file cache
- [ADR-0006](../adr/0006-vanilla-js-over-framework.md) — Vanilla JS, bukan framework

---

## Dokumen Terkait

- [devops/tooling.md](../devops/tooling.md) — Setup semua tooling di atas
- [development/onboarding.md](../development/onboarding.md) — Install dari nol
- [devops/packaging.md](../devops/packaging.md) — pyproject.toml detail
