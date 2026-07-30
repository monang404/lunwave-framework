# Coding Standard

> Prinsip dan konvensi penulisan kode LunaWave.
> Untuk setup environment, lihat → [onboarding.md](onboarding.md)
> Untuk konfigurasi linter yang menegakkan sebagian besar aturan ini, lihat → [../devops/tooling.md](../devops/tooling.md)

---

## Tiga Prinsip Utama

Seluruh kode LunaWave ditulis dengan tiga prinsip ini sebagai kompas:

> **Prinsip #1:** 1 file kode = 1 tanggung jawab
>
> **Prinsip #2:** 1 file kode (yang testable) = 1 file test
>
> **Prinsip #3:** Setiap penambahan harus punya alasan jelas — tidak ada yang ditambah demi terlihat canggih

---

## 1 File = 1 Tanggung Jawab

### Apa Artinya

Setiap file Python atau JS hanya melakukan satu hal. Bukan "satu class" — satu **concern**.

| File | Tanggung Jawab Tunggal |
|---|---|
| `core/command_bus.py` | Mendistribusikan command ke handler yang tepat |
| `engine/radio/track_filter.py` | Memfilter track dari daftar kandidat radio |
| `persistence/track_repo.py` | CRUD track ke SQLite |
| `utils/format.js` | Formatting string untuk UI |

### Tanda File Sudah Melanggar Prinsip Ini

- Nama file mengandung kata "and", "or", "utils", "helpers" tanpa qualifier spesifik
- File punya lebih dari 2-3 class yang tidak terkait erat
- Import list file tersebut panjang dan berasal dari banyak domain berbeda

### God File Threshold

| Kondisi | Aksi |
|---|---|
| File Python < 100 baris | Aman |
| File Python 100–150 baris | Perhatikan — mungkin sudah terlalu banyak concern |
| File Python > 150 baris | **Waspada** — kemungkinan besar perlu dipecah |
| File Python > 300 baris | **God file** — pecah segera |

> **Catatan `serializers.py`:** Saat ini 55 baris, 3 fungsi — masih sehat. Ambang waspada: kalau mendekati ~150 baris, pecah per domain (`serializers/track.py`, `serializers/state.py`).

Aturan yang sama berlaku untuk JS:

| Kondisi | Aksi |
|---|---|
| File JS < 150 baris | Aman |
| File JS 150–200 baris | Perhatikan |
| File JS > 200 baris | Kandidat untuk dipecah |

---

## Type Checking

### Strategi: Bertahap, Bukan Sekaligus

Jangan aktifkan `mypy --strict` global di awal — CI akan merah semua dan tidak informatif. Naikkan coverage per folder secara bertahap.

**Urutan prioritas:**

```
1. core/         → strict = true  (paling murni, paling mudah)
2. persistence/  → strict = true  (terisolasi, mudah ditype)
3. engine/       → strict = true  (domain logic)
4. adapters/     → sedang         (ada external type stubs)
5. server/       → sedang
6. plugins/      → longgar
7. launcher/gui/ → ignore_errors  (Tkinter typing tidak ideal)
```

### Konfigurasi Mypy Saat Ini

```toml
# pyproject.toml
[tool.mypy]
strict = false

[[tool.mypy.overrides]]
module = ["lunawave.core.*", "lunawave.persistence.*"]
strict = true

[[tool.mypy.overrides]]
module = ["launcher.gui.*"]
ignore_errors = true
```

Lihat konfigurasi lengkap → [../devops/tooling.md](../devops/tooling.md#toolmypy)

### Ports Sudah Pakai `typing.Protocol`

`core/ports.py` sudah menggunakan `typing.Protocol` dengan benar. Ini adalah fondasi yang baik — setiap fake di `tests/fakes/` harus comply dengan Protocol yang sama.

---

## Konvensi Naming

### Python

```python
# Modul & file: snake_case
track_repository.py
command_bus.py

# Class: PascalCase
class TrackRepository:
class CommandBus:

# Fungsi & variable: snake_case
async def find_by_id(track_id: str) -> Track | None:

# Konstanta: UPPER_SNAKE_CASE
MAX_QUEUE_SIZE = 100
ADMIN_ONLY_ACTIONS = frozenset({"delete", "clear_queue"})

# Private: prefix underscore
_internal_state: dict
```

### JavaScript

```javascript
// File: kebab-case
format.js
playback-sync.js
ws-routing.test.js

// Fungsi & variable: camelCase
function formatDuration(seconds) {}
const currentTrack = null;

// Konstanta: UPPER_SNAKE_CASE
const MAX_RETRIES = 3;

// Event name (custom): kebab-case string
"track-started"
"download-progress"
```

---

## Commit Convention

LunaWave mengikuti [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

feat(radio): add track deduplication in track_filter
fix(auth): use absolute time for session expiry
refactor(engine): split controller.py into queue_ops and mode_ops
test(persistence): add unit test for track_repo.save
docs(adr): add ADR-0003 hexagonal ports protocol
chore(ci): add continue-on-error to lint steps
```

| Type | Kapan Digunakan |
|---|---|
| `feat` | Fitur baru |
| `fix` | Bug fix |
| `refactor` | Refactor tanpa perubahan behavior |
| `test` | Tambah atau perbaiki test |
| `docs` | Perubahan dokumentasi |
| `chore` | Maintenance (deps, config, tooling) |
| `perf` | Peningkatan performa |

---

## Dependency Direction

Kode harus mengikuti aturan dependency direction hexagonal architecture. Pelanggaran akan ditangkap otomatis oleh `import-linter` di CI.

```
core/        → tidak boleh import apapun di luar core/
adapters/    → boleh import core/ saja
persistence/ → boleh import core/ saja
engine/      → boleh import core/, adapters/, persistence/ (lewat ports)
server/      → boleh import core/, engine/, services/, persistence/
plugins/     → boleh import core/ saja
```

Lihat aturan lengkap → [../architecture/dependency_rules.md](../architecture/dependency_rules.md)

---

## Referensi Terkait

- Setup environment → [onboarding.md](onboarding.md)
- Peta risiko refactoring → [project_structure.md](project_structure.md)
- Linter config (ruff, mypy) → [../devops/tooling.md](../devops/tooling.md)
- Dependency rules → [../architecture/dependency_rules.md](../architecture/dependency_rules.md)
- Contributing guide → [../opensource/contributing.md](../opensource/contributing.md)
