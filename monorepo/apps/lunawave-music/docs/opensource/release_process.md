# Release Process

> Dokumen ini adalah entry point untuk contributor yang ingin memahami proses rilis LunaWave.
> Dokumentasi teknis lengkap ada di → [../devops/release.md](../devops/release.md)

---

## Ringkasan

LunaWave menggunakan **Semantic Versioning** dan **GitHub Releases** sebagai mekanisme distribusi resmi.

Setiap rilis membutuhkan:
1. CI pipeline hijau (lint + test)
2. `CHANGELOG.md` diupdate
3. `pyproject.toml` version di-bump
4. Git tag `v*.*.*` yang mentrigger `release.yml`

---

## Dokumentasi Lengkap

Seluruh detail proses rilis ada di:

→ **[../devops/release.md](../devops/release.md)**

Mencakup:
- SemVer rules (kapan naik MAJOR/MINOR/PATCH)
- Langkah manual rilis step-by-step
- `release.yml` GitHub Actions YAML
- Format `CHANGELOG.md`
- Checklist sebelum rilis

---

## Sebagai Maintainer

Hanya maintainer yang bisa membuat tag `v*.*.*` dan mentrigger release job.

Jika Anda adalah contributor (bukan maintainer), buat PR ke `main` — maintainer yang akan handle rilis setelah PR di-merge.

---

## Referensi Terkait

- Release workflow teknis → [../devops/release.md](../devops/release.md)
- Open source readiness checklist → [readiness.md](readiness.md)
- Contributing guide → [contributing.md](contributing.md)
- CI yang diperlukan sebelum release → [../devops/ci_cd.md](../devops/ci_cd.md)
