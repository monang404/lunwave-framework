# ADR-0008: Kredensial Admin di SQLite, Tanpa Migrasi Otomatis

**Status:** Accepted
**Date:** 2026-07-19

---

## Konteks

Sebelum Fitur B (login_redesign), kredensial admin di-generate otomatis oleh
`config.py` saat startup dan disimpan sebagai hash di file cache
(`cache/admin_password.txt`, lalu `instance/admin_password.txt` di launcher).
Password *raw* hanya dicetak sekali ke konsol. Pola ini punya beberapa
masalah yang mendorong redesign:

- Dua file password (`cache/admin_password.txt` dan
  `instance/admin_password.txt`) bisa tidak sinkron satu sama lain di
  lapangan — tidak ada source of truth tunggal.
- Password di-generate otomatis tanpa proses konfirmasi/setup eksplisit apa
  pun dari user, dan launcher desktop punya mekanisme auth sendiri yang
  terpisah dari server web (akar masalah "Temuan C").
- Tidak ada alur setup yang jelas untuk membedakan instalasi baru vs upgrade.

Redesign ini perlu memutuskan tiga hal terkait sekaligus (didiskusikan
sebagai K3, K4, K5 di `task_breakdown_agent.yaml`), yang saling terkait erat
sehingga didokumentasikan sebagai satu ADR.

## Keputusan

1. **Sumber kebenaran kredensial pindah ke tabel `admin_account` di
   SQLite** (lihat [ADR-0002](0002-sqlite-over-json-cache.md) untuk alasan
   SQLite atas JSON secara umum), diisi lewat alur **Initial Setup** di web
   (`server/handlers/setup.py`, action WS `setup_admin`) — bukan lagi
   di-generate otomatis oleh `config.py`.

2. **(K3) Tidak ada migrasi otomatis** dari file password lama
   (`cache/admin_password.txt` / `instance/admin_password.txt`) ke
   `admin_account`. Startup tidak membaca kedua file itu sama sekali.
   Instalasi lama (upgrade) dan instalasi baru diperlakukan identik —
   keduanya diarahkan ke Initial Setup selama `admin_account` masih kosong.

3. **(K4) Env var override tetap tersedia**, terpisah dari mekanisme
   auto-generate yang dihapus. `LUNAWAVE_ADMIN_PASS` (atau alias lama
   `YTGUI_ADMIN_PASS`) di-hash oleh `config.py` menjadi
   `ADMIN_PASSWORD_OVERRIDE`, lalu dikonsumsi satu-satunya kali oleh
   `bootstrap.services._seed_admin_account_from_env()`: hanya jalan kalau
   `admin_account` **masih kosong**, dan tidak pernah menimpa akun yang
   sudah ada. Ini jalur non-default untuk provisioning non-interaktif (CI,
   automated deploy) yang tidak bisa lewat wizard browser — bukan mekanisme
   migrasi.

4. **(K5) Launcher desktop tidak lagi punya mekanisme auth sendiri.**
   Tombol "Reset Password" di launcher GUI (`launcher/gui/auth_panel.py`)
   sekarang hanya membuka `http://localhost:{server_port}` di browser
   (`webbrowser.open`), mengarahkan user ke alur Initial-Setup-ulang/Login
   yang sama dengan client web biasa. `launcher/auth_service.py` (mekanisme
   auth terpisah lama) dihapus.

## Alternatif Dipertimbangkan

- **Migrasi otomatis dari file password lama** — ditolak. Migrasi harus
  menebak file mana yang jadi sumber kebenaran ketika keduanya ada dan
  tidak sinkron; risiko salah pilih (login dengan kredensial usang yang
  tanpa sadar tetap valid) dinilai lebih besar daripada biaya re-setup satu
  kali saat upgrade.
- **Hapus env var override sepenuhnya** — ditolak. Dibutuhkan untuk
  deployment non-interaktif (CI, provisioning otomatis) yang tidak bisa
  melalui wizard browser secara manual.
- **Launcher mempertahankan mekanisme reset password sendiri** (generate
  ulang file lokal) — ditolak. Ini melanggengkan dua sumber kebenaran
  auth (launcher vs `admin_account` SQLite) yang justru jadi akar masalah
  yang sedang ditutup oleh redesign ini.

## Konsekuensi

- **User existing yang upgrade WAJIB melalui Initial Setup lagi** — efeknya
  logout paksa dari sesi admin lama. Ini didokumentasikan sebagai catatan
  upgrade di `README.md` (lihat T-B6) dan tidak dianggap sebagai bug.
- File `cache/admin_password.txt` dan `instance/admin_password.txt` yang
  tersisa dari instalasi pra-redesign diabaikan, bukan dihapus paksa oleh
  startup; keduanya tetap di-gitignore selama masa transisi (lihat
  `automation/verify_security.py`, T-B17).
- `config.py` tidak lagi auto-generate password, tidak lagi menulis file
  cache password, dan tidak lagi mencetak banner password saat startup.
- Tidak ada admin account = tidak ada state "login tanpa password" yang
  mungkin — kegagalan penyimpanan (DB corrupt, disk penuh) saat Initial
  Setup selalu gagal eksplisit ke halaman error, tidak pernah membuat baris
  `admin_account` kosong (lihat T-B7).

## Referensi

- Implementasi: `server/handlers/setup.py`, `server/handlers/auth.py`,
  `persistence/admin_account_repo.py`, `bootstrap/services.py`,
  `launcher/gui/auth_panel.py`
- Keputusan asal: `task_breakdown_agent.yaml` §`decisions` (K3, K4, K5)
- Catatan desain terkait: [threat_model.md](../security/threat_model.md#catatan-desain-kredensial-admin-tidak-dimigrasikan-otomatis-k3)
- Test: `tests/unit/server/handlers/test_setup.py`,
  `tests/unit/server/handlers/test_auth.py`,
  `tests/unit/bootstrap/`, `tests/unit/launcher/gui/test_auth_panel.py`
