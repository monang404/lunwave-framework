# Deployment

> **Status: Partially Documented — Future Work**
>
> Blueprint v2 menyebut Docker secara singkat sebagai bagian dari release workflow.
> Dokumentasi ini akan diisi setelah Dockerfile diperbaiki (lihat catatan di bawah).

---

## Mode Deploy Saat Ini

LunaWave saat ini di-deploy dengan cara paling sederhana: **jalankan langsung dari source**.

```bash
# Clone
git clone https://github.com/<user>/lunawave.git
cd lunawave

# Install dependencies
pip install -r requirements.txt

# Jalankan
python start.py
# atau
python main.py
```

Untuk instruksi setup lengkap dari nol, lihat → [../development/onboarding.md](../development/onboarding.md)

---

## Docker (Future Work)

Blueprint v2 menyebutkan Docker build + push ke GHCR sebagai bagian dari release workflow, tetapi **Dockerfile saat ini perlu diperbaiki** sebelum bisa digunakan secara reliable.

### Hal yang Perlu Diselesaikan

- [ ] Dockerfile yang reproducible (multi-stage build)
- [ ] MPV terinstall di image (apt layer)
- [ ] Volume mount untuk `cache/mp3/` dan database file
- [ ] Port expose yang benar
- [ ] Health check endpoint

### Target `docker-compose.yml` (Belum Dibuat)

```yaml
# docker-compose.yml (target masa depan)
services:
  lunawave:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./cache:/app/cache
    environment:
      - LUNAWAVE_HOST=0.0.0.0
      - LUNAWAVE_PORT=8000
    restart: unless-stopped
```

### Target `Dockerfile` (Belum Dibuat)

```dockerfile
# Dockerfile (target masa depan)
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    mpv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "main.py"]
```

---

## Prioritas

Implementasikan Docker setelah:

1. Unit test coverage ≥ 80%
2. Radio mode berjalan stabil
3. CI pipeline hijau tanpa `continue-on-error`

---

## Referensi Terkait

- Setup dari source → [../development/onboarding.md](../development/onboarding.md)
- Release workflow (Docker push ke GHCR) → [release.md](release.md)
- CI pipeline → [ci_cd.md](ci_cd.md)
