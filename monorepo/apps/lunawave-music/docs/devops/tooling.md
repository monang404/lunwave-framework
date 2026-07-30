# Tooling

> Konfigurasi seluruh developer tooling LunaWave — linting, type checking, security audit, coverage, dan pre-commit hooks.
> Untuk CI yang menggunakan config ini, lihat → [ci_cd.md](ci_cd.md)
> Untuk packaging dependencies, lihat → [packaging.md](packaging.md)

---

## File Config yang Perlu Dibuat

| File | Status | Isi |
|---|---|---|
| `pyproject.toml` | ⚠️ Belum lengkap | Sections `[tool.ruff]`, `[tool.mypy]`, `[tool.bandit]`, `[tool.coverage]` |
| `requirements-dev.txt` | ❌ Belum ada | Dev dependencies — lihat [packaging.md](packaging.md) |
| `requirements-gui.txt` | ✅ Sudah ada | Opsional: PySide6 untuk launcher GUI desktop |
| `.importlinter` | ❌ Belum ada | Aturan dependency direction |
| `.pre-commit-config.yaml` | ✅ Sudah ada (root repo) | Hooks: architecture_lint, verify_docs |
| `.editorconfig` | ❌ Belum ada | Konsistensi editor: indent, charset, line ending |

---

## pyproject.toml

### `[tool.ruff]`

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "UP",  # pyupgrade
]
ignore = [
    "E501",  # line too long — ditangani oleh formatter
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### `[tool.mypy]`

```toml
[tool.mypy]
python_version = "3.11"
strict = false            # mulai longgar, naikkan bertahap

# Tahap 1: core/ dan persistence/ duluan
[[tool.mypy.overrides]]
module = ["lunawave.core.*", "lunawave.persistence.*"]
strict = true

# Exclude yang belum ditype-check
[[tool.mypy.overrides]]
module = ["launcher.gui.*"]
ignore_errors = true
```

> **Strategi type checking:** jangan langsung `strict = true` global — CI akan merah semua dan tidak informatif. Aktifkan per folder setelah tiap folder dibenahi. Prioritas: `core/` → `persistence/` → `engine/` → `adapters/` → `server/`.

### `[tool.bandit]`

```toml
[tool.bandit]
exclude_dirs = ["tests", "scratch"]
skips = []    # jangan skip kecuali ada alasan eksplisit
```

### `[tool.coverage]`

```toml
[tool.coverage.run]
source = ["lunawave"]
omit = [
    "lunawave/launcher/gui/app.py",        # Tkinter lifecycle — tidak bisa ditest headless
    "lunawave/launcher/gui/ui_builder.py", # Tkinter widget builder — idem
    "start.py",                            # Entry point OS — side-effect global
]

[tool.coverage.report]
fail_under = 100    # hanya berlaku untuk file dalam scope (setelah omit)
show_missing = true
```

### `[tool.pytest]`

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"           # pytest-asyncio: semua async test otomatis
testpaths = ["tests"]
addopts = "--tb=short -q"
```

---

## `.importlinter`

Konfigurasi ini menjaga dependency direction hexagonal architecture secara otomatis di CI.
Untuk penjelasan aturannya, lihat → [../architecture/dependency_rules.md](../architecture/dependency_rules.md)

```ini
[importlinter]
root_package = lunawave

[importlinter:contract:core-independence]
name = core must not import anything outside core
type = forbidden
source_modules = lunawave.core
forbidden_modules =
    lunawave.adapters
    lunawave.engine
    lunawave.persistence
    lunawave.server
    lunawave.services
    lunawave.plugins
    lunawave.launcher

[importlinter:contract:adapters-only-core]
name = adapters may only import from core
type = layers
layers =
    lunawave.core
    lunawave.adapters

[importlinter:contract:engine-allowed]
name = engine may import core, adapters, persistence via ports
type = forbidden
source_modules = lunawave.engine
forbidden_modules =
    lunawave.server
    lunawave.launcher

[importlinter:contract:server-no-launcher]
name = server must not import launcher
type = forbidden
source_modules = lunawave.server
forbidden_modules = lunawave.launcher
```

---

## `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.9.0
    hooks:
      - id: mypy
        args: [--config-file=pyproject.toml]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.8
    hooks:
      - id: bandit
        args: [-c, pyproject.toml]

  - repo: https://github.com/seddonym/import-linter
    rev: 1.12.1
    hooks:
      - id: import-linter

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
```

### Setup pre-commit

```bash
pip install pre-commit
pre-commit install      # install hooks ke .git/hooks/pre-commit
pre-commit run --all-files  # run manual sekali
```

---

## `.editorconfig`

```ini
root = true

[*]
indent_style = space
indent_size = 4
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.js]
indent_size = 2

[*.json]
indent_size = 2

[*.yaml]
indent_size = 2

[*.md]
trim_trailing_whitespace = false
```

---

## Menjalankan Tool Secara Manual

```bash
# Lint + format check
ruff check .
ruff format --check .

# Type check
mypy .

# Security audit
bandit -r lunawave/ -c pyproject.toml

# Dependency audit
pip-audit -r requirements.txt

# Dependency direction
lint-imports

# Semua sekaligus (simulasi CI)
ruff check . && mypy . && bandit -r lunawave/ -c pyproject.toml && lint-imports
```

---

## Referensi Terkait

- CI yang menggunakan config ini → [ci_cd.md](ci_cd.md)
- Dependencies dev → [packaging.md](packaging.md)
- Aturan dependency direction (detail) → [../architecture/dependency_rules.md](../architecture/dependency_rules.md)
- Coverage omit list (detail) → [../testing/testing_strategy.md](../testing/testing_strategy.md#coverage-configuration)
