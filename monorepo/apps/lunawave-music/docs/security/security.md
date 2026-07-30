# Security

> Kebijakan keamanan LunaWave — cara melaporkan vulnerability, audit secrets, dan checklist sebelum go public.
> Untuk threat model lengkap, lihat → [threat_model.md](threat_model.md)

---

## Melaporkan Vulnerability

LunaWave adalah proyek open source self-hosted. Jika menemukan vulnerability:

1. **Jangan buat public GitHub Issue** untuk security vulnerability.
2. Kirim laporan ke maintainer via email atau GitHub Security Advisory (Private).
3. Sertakan: deskripsi, langkah reproduksi, dampak yang mungkin, dan versi yang terpengaruh.
4. Respons awal dalam **72 jam**. Fix dan disclosure dalam **14 hari** untuk vulnerability kritis.

### Scope

| In Scope | Out of Scope |
|---|---|
| Autentikasi WebSocket | Keamanan jaringan di luar aplikasi |
| Injeksi command ke MPV/yt-dlp | Keamanan OS host |
| Akses file di luar `cache/mp3/` | Vulnerability di MPV atau yt-dlp itu sendiri |
| Hardcoded credentials | Serangan yang butuh akses fisik ke server |
| Path traversal via URL/filename | |
| Cross-Site WebSocket Hijacking (CSWSH) | |

---

## Audit Secrets & Credentials

### Checklist Sebelum Push

Pastikan hal berikut tidak ada di kode:

- [ ] Password atau API key hardcoded
- [ ] Token autentikasi dalam source code
- [ ] Credential dalam komentar atau string debug
- [ ] File `.env` yang tidak di-gitignore

### File yang Wajib Di-gitignore

```gitignore
# Runtime — tidak boleh di-commit
data/lunawave.db
cache/mp3/
*.db
*.db-shm
*.db-wal

# Secrets
.env
.env.local
config.local.py

# OS & tooling noise
__pycache__/
*.pyc
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
```

> **Aksi:** Cek `data/lunawave.db` dan `cache/mp3/` sudah ada di `.gitignore`. Jalankan `git status` — pastikan keduanya tidak muncul sebagai untracked file.

### Scan Otomatis

```bash
# Bandit — static analysis untuk security issue Python
bandit -r . -c pyproject.toml

# pip-audit — cek vulnerability di dependencies
pip-audit -r requirements.txt
```

Kedua tool sudah terintegrasi di CI — lihat → [../devops/ci_cd.md](../devops/ci_cd.md)

---

## Autentikasi WebSocket

LunaWave menggunakan token-based auth untuk WebSocket.

### Alur Autentikasi

1. Client kirim `{"type": "cmd", "action": "auth", "data": {"username": "...", "password": "..."}}` via WS
2. Server verifikasi password dengan PBKDF2-SHA256 (100k iterasi, via `core.security.verify_password`)
3. Jika sukses, server issue token: `secrets.token_hex(16)` (128-bit entropy)
4. Token **di-hash dengan SHA-256** sebelum disimpan di tabel `sessions` — raw token tidak pernah masuk DB
5. Client simpan token; kirim ulang sebagai `{"token": "..."}` untuk sesi berikutnya
6. Server hash token yang diterima → bandingkan dengan hash di DB (constant-time compare)

### Hal yang Harus Dijaga

- Token di-generate dengan entropi cukup (`secrets.token_hex(16)` = 128-bit)
- Token **tidak di-log** dalam bentuk plaintext
- Token di-hash SHA-256 sebelum disimpan di DB — bocornya DB tidak langsung memberikan akses
- Session expired menggunakan **waktu absolut** (Unix timestamp), bukan monotonic clock
- Rate limit 5x/5 menit per IP untuk percobaan password

```python
# Implementasi aktual (core/security.py)
import hashlib, secrets

# Hash password (simpan di admin_account)
hash_password(password)   # PBKDF2-SHA256, 100k iterasi, random salt

# Issue & hash token (simpan di sessions)
token = secrets.token_hex(16)        # raw token → kirim ke client
hash_token(token)                    # SHA-256 → simpan di DB

# Verifikasi token dari client
verify_token(raw_token, stored_hash) # constant-time compare

# Yang harus dihindari
import time
expiry = time.monotonic() + 3600  # ← BUG: monotonic tidak valid sebagai timestamp absolut
```

### Perlindungan CSWSH (Cross-Site WebSocket Hijacking)

`ws_handler` memvalidasi header `Origin` sebelum `ws.prepare()` (implementasi di `server/handlers/websocket.py`):

- Tidak ada `Origin` header → diizinkan (klien non-browser: curl, Termux, Python script)
- `Origin` ada, host cocok dengan `Host` header → diizinkan
- `Origin` ada, host **tidak cocok** → ditolak `HTTP 403` sebelum koneksi WS terbuka

Ini penting karena README merekomendasikan expose server via tunnel (ngrok/Cloudflare).

---

## `SECURITY.md` (Root Repo)

> **Status:** ✅ Sudah ada di root repo.

File `SECURITY.md` di root repo mengikuti standar GitHub untuk disclosure policy.

---

## Referensi Terkait

- Threat model detail → [threat_model.md](threat_model.md)
- Bandit config → [../devops/tooling.md](../devops/tooling.md)
- CI security audit → [../devops/ci_cd.md](../devops/ci_cd.md)
- Open source readiness checklist → [../opensource/readiness.md](../opensource/readiness.md)
- ADR autentikasi & kredensial admin → [../adr/0008-admin-credentials-in-sqlite.md](../adr/0008-admin-credentials-in-sqlite.md)
