# Contributing to LunaWave

> Terima kasih sudah tertarik berkontribusi ke LunaWave.
> Dokumen ini menjelaskan cara fork, branch, commit, dan submit PR.

---

## Sebelum Mulai

1. **Baca dulu:** [../development/onboarding.md](../development/onboarding.md) — pastikan LunaWave berjalan di mesin Anda.
2. **Cek issue yang ada** — mungkin sudah ada diskusi tentang hal yang ingin Anda kerjakan.
3. **Buat issue baru** jika belum ada — diskusikan dulu untuk fitur besar sebelum mulai koding.

---

## Alur Kontribusi

```
Fork → Clone → Branch → Code → Test → Commit → Push → PR
```

### 1. Fork & Clone

```bash
# Fork di GitHub, lalu:
git clone https://github.com/<username>/lunawave.git
cd lunawave

# Tambahkan upstream untuk sync
git remote add upstream https://github.com/<original-user>/lunawave.git
```

### 2. Buat Branch

```bash
# Sync dengan upstream dulu
git fetch upstream
git checkout main
git merge upstream/main

# Buat branch baru
git checkout -b feat/nama-fitur
# atau
git checkout -b fix/nama-bug
```

### Branch Naming Convention

| Prefix | Kapan Digunakan | Contoh |
|---|---|---|
| `feat/` | Fitur baru | `feat/radio-deduplication` |
| `fix/` | Bug fix | `fix/session-expiry-monotonic` |
| `refactor/` | Refactor tanpa perubahan behavior | `refactor/split-websocket-handlers` |
| `test/` | Tambah atau perbaiki test | `test/engine-unit-tests` |
| `docs/` | Perubahan dokumentasi saja | `docs/add-adr-0003` |
| `chore/` | Maintenance (deps, config) | `chore/update-ruff-config` |

### 3. Kode

- Ikuti [../development/coding_standard.md](../development/coding_standard.md)
- 1 file kode = 1 tanggung jawab
- Kalau tambah file baru yang testable → tambah test-nya sekaligus

### 4. Test

```bash
# Jalankan unit test — harus hijau sebelum commit
pytest tests/unit/ -v --cov --cov-fail-under=100

# Jika menyentuh integration layer
pytest tests/integration/ -v
```

### 5. Commit

LunaWave menggunakan [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git commit -m "feat(radio): add track deduplication in track_filter"
git commit -m "fix(auth): use absolute time for session expiry"
git commit -m "test(persistence): add unit test for track_repo.save"
```

Format: `<type>(<scope>): <description singkat>`

Lihat konvensi lengkap → [../development/coding_standard.md#commit-convention](../development/coding_standard.md#commit-convention)

### 6. Push & Buat PR

```bash
git push origin feat/nama-fitur
```

Lalu buka GitHub dan buat Pull Request.

---

## PR Checklist

Sebelum submit PR, pastikan semua item berikut terpenuhi:

**Code Quality**
- [ ] Tidak ada error dari `ruff check .`
- [ ] Tidak ada error dari `mypy .`
- [ ] `lint-imports` tidak melaporkan violation dependency direction

**Testing**
- [ ] `pytest tests/unit/ --cov-fail-under=100` hijau
- [ ] Setiap file kode baru yang testable punya file test-nya
- [ ] Tidak ada test yang di-skip tanpa alasan tertulis

**Dokumentasi**
- [ ] Jika ada keputusan arsitektur baru → tambah ADR di `docs/adr/`
- [ ] Jika ada perubahan behavior publik → update docs yang relevan
- [ ] PR description menjelaskan: *apa* yang berubah dan *kenapa*

**Keamanan**
- [ ] Tidak ada secret, credential, atau API key di kode
- [ ] `bandit` tidak melaporkan issue baru

---

## GitHub Templates

### Issue Templates

`.github/ISSUE_TEMPLATE/bug_report.md`:
```markdown
## Deskripsi Bug
[Jelaskan apa yang terjadi]

## Langkah Reproduksi
1. ...
2. ...

## Expected Behavior
[Seharusnya terjadi apa]

## Environment
- OS:
- Python version:
- MPV version:
- LunaWave version:
```

`.github/ISSUE_TEMPLATE/feature_request.md`:
```markdown
## Fitur yang Diinginkan
[Jelaskan fitur yang ingin ditambahkan]

## Motivasi
[Kenapa fitur ini berguna?]

## Solusi yang Diusulkan
[Jika ada ide implementasi]
```

### PR Template

`.github/PULL_REQUEST_TEMPLATE.md`:
```markdown
## Perubahan

[Jelaskan apa yang berubah]

## Motivasi

[Kenapa perubahan ini diperlukan]

## Checklist

- [ ] Test hijau (`pytest tests/unit/ --cov-fail-under=100`)
- [ ] Lint bersih (`ruff check .`, `mypy .`)
- [ ] Tidak ada secret di kode
- [ ] Docs diupdate jika diperlukan
```

> **Status file-file di atas:** ❌ Belum dibuat. Buat sebelum repo dipublikasi.

---

## Referensi Terkait

- Setup environment → [../development/onboarding.md](../development/onboarding.md)
- Coding standard → [../development/coding_standard.md](../development/coding_standard.md)
- Open source readiness → [readiness.md](readiness.md)
- Security policy → [../security/security.md](../security/security.md)
