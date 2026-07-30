# Open Source Readiness

> Checklist lengkap untuk menjadikan LunaWave siap sebagai proyek open source profesional.
> Update status setiap item seiring progress.

---

## Status Legend

| Symbol | Artinya |
|---|---|
| ✅ | Selesai |
| ⚠️ | Ada tapi perlu diaudit/diperbaiki |
| ❌ | Belum ada — harus dibuat |
| 🔍 | Perlu dicek |

---

## Checklist

### Legal & Lisensi

| Item | Status | Aksi |
|---|---|---|
| `LICENSE` (MIT) | ❌ | Buat file `LICENSE` di root repo dengan teks MIT License |

### README & Dokumentasi Utama

| Item | Status | Aksi |
|---|---|---|
| `README.md` — run-from-zero | ⚠️ | Audit: ikuti dari `git clone` sampai LunaWave jalan tanpa pengetahuan sebelumnya |
| `CHANGELOG.md` | ❌ | Buat dengan format Keep a Changelog — lihat [../devops/release.md](../devops/release.md) |

### File Standar Open Source

| Item | Status | Aksi |
|---|---|---|
| `CONTRIBUTING.md` | ❌ | Buat atau symlink ke `docs/opensource/contributing.md` |
| `SECURITY.md` | ❌ | Buat — lihat [../security/security.md](../security/security.md) |
| `.editorconfig` | ❌ | Buat — lihat [../devops/tooling.md](../devops/tooling.md#editorconfig) |

### GitHub-Specific

| Item | Status | Aksi |
|---|---|---|
| `.github/ISSUE_TEMPLATE/bug_report.md` | ❌ | Buat — template ada di [contributing.md](contributing.md) |
| `.github/ISSUE_TEMPLATE/feature_request.md` | ❌ | Buat — template ada di [contributing.md](contributing.md) |
| `.github/PULL_REQUEST_TEMPLATE.md` | ❌ | Buat — template ada di [contributing.md](contributing.md) |
| `.gitignore` | ✅ | — |

### Runtime Files Di-gitignore

| Item | Status | Aksi |
|---|---|---|
| `data/lunawave.db` di-gitignore | 🔍 | Jalankan `git status` — pastikan tidak muncul sebagai untracked |
| `cache/mp3/` di-gitignore | 🔍 | Idem |

### Security & Code Quality

| Item | Status | Aksi |
|---|---|---|
| Secrets di kode | 🔍 | Jalankan `bandit -r lunawave/` dan audit manual — pastikan tidak ada password/key hardcoded |
| CI pipeline jujur | ⚠️ | Tambah `continue-on-error` pada step yang belum bisa jalan — lihat [../devops/ci_cd.md](../devops/ci_cd.md) |
| `requirements-dev.txt` | ❌ | Buat — lihat [../devops/packaging.md](../devops/packaging.md) |
| `pyproject.toml` config sections | ❌ | Buat `[tool.ruff]`, `[tool.mypy]`, `[tool.bandit]`, `[tool.coverage]` |

### Architecture Documentation

| Item | Status | Aksi |
|---|---|---|
| ADR (Architecture Decision Records) | ❌ | Buat 6 ADR — lihat [../adr/](../adr/) |
| Dependency direction documented | ✅ | Ada di `docs/architecture/dependency_rules.md` |
| Dependency direction enforced | ❌ | Buat `.importlinter` — lihat [../devops/tooling.md](../devops/tooling.md) |

---

## Dokumen yang Tidak Perlu Dibuat

Untuk skala proyek ini, nilai tambah dokumen berikut tidak sebanding dengan usaha yang dibutuhkan. Bisa ditambah belakangan kalau komunitas berkembang:

| Dokumen | Alasan Ditunda |
|---|---|
| `CODE_OF_CONDUCT.md` | Belum ada komunitas yang perlu di-govern |
| `SUPPORT.md` | Cukup lewat GitHub Issues |
| `ROADMAP.md` | Blueprint v2 sudah cukup sebagai internal roadmap |
| `API.md` | API internal, bukan public API |
| `STYLE_GUIDE.md` | Sudah tercakup di `coding_standard.md` |

---

## Urutan Prioritas

Jika belum tahu mulai dari mana, kerjakan dalam urutan ini:

1. **`LICENSE`** — tanpa ini repo secara legal tidak bisa digunakan siapapun
2. **`SECURITY.md`** — penting sebelum dipublikasi
3. **Audit `.gitignore`** — pastikan database dan cache tidak ikut di-commit
4. **`requirements-dev.txt` + `pyproject.toml` config** — perbaiki CI agar tidak merah langsung
5. **`CONTRIBUTING.md`** — buat atau symlink
6. **`.github/ISSUE_TEMPLATE/`** — standar GitHub untuk issue management
7. **6 ADR** — investasi dokumentasi dengan ROI tertinggi
8. **Audit `README.md`** — run-from-zero test

---

## Referensi Terkait

- Contributing guide → [contributing.md](contributing.md)
- Release process → [release_process.md](release_process.md)
- Security policy → [../security/security.md](../security/security.md)
- CI status → [../devops/ci_cd.md](../devops/ci_cd.md)
- ADR list → [../adr/](../adr/)
