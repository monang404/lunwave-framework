---
title: Proposal Perbaikan Keamanan & Bug — LunaWave
version: 1.0
tanggal: 2026-07-27
status: DRAFT — untuk direview
target rilis: usulan, non-breaking, dieksekusi bertahap per fase
author: Claude (AI audit session) — atas permintaan pemilik project
scope: server/, core/, engine/, persistence/, web/static/
sumber: Ringkasan Hasil Audit Keamanan LunaWave (20 temuan)
---

# Proposal Perbaikan Keamanan & Bug — LunaWave

> **Ringkasan satu paragraf:** Audit keamanan LunaWave menemukan 20 temuan.
> Dokumen ini memverifikasi tiap temuan langsung terhadap kode sumber
> (bukan hanya mengutip ringkasan audit), memetakan root cause per lokasi
> file/baris, dan mengusulkan desain perbaikan konkret. Lima temuan
> Prioritas Tinggi berpusat pada satu pola yang sama: **validasi/otorisasi
> yang dipercayakan ke sisi client** (chat `client_uid` yang self-asserted,
> rate limit yang bisa habis oleh satu IP di belakang reverse proxy,
> exception mentah yang bocor ke client, tidak ada jalur pencabutan sesi
> massal). Perbaikan diusulkan dalam 4 fase independen — searah dengan
> pola "jangan gabungkan 2 perubahan besar dalam 1 commit" yang sudah
> dipakai di RFC-RFC LunaWave sebelumnya (lihat `docs/rfc/arsip/`) — supaya
> tiap fase bisa dihentikan tanpa meninggalkan kode dalam keadaan rusak.

---

## 1. Latar Belakang

Dokumen sumber (`Ringkasan Hasil Audit Keamanan LunaWave`) mendaftar 20
temuan dalam empat kelompok: temuan kritis, bug & inkonsistensi
implementasi, kelemahan keamanan, dan keterbatasan desain. Sebelum
mengusulkan perbaikan, tiap temuan diverifikasi terhadap kode aktual di
repo `lunawave-develop` (bukan diasumsikan benar dari ringkasan saja).
Hasil verifikasi ada di §3–§5 di bawah, masing-masing dengan referensi
file dan baris konkret.

Kesimpulan verifikasi: **19 dari 20 temuan terkonfirmasi persis seperti
dijelaskan di audit**, dengan satu nuansa penting pada rate limiting chat
(§3.2) — rate limit *sebenarnya ada* dan mencakup chat, tapi bentuknya
per-IP dan berbagi kuota dengan semua command lain, sehingga di belakang
reverse proxy (yang direkomendasikan sendiri di README LunaWave) satu
grup pengguna bisa saling menghabiskan kuota satu sama lain — persis
mekanisme self-DoS yang disebut audit untuk login rate limit, ternyata
berlaku juga di jalur command WebSocket.

## 2. Ringkasan Temuan & Prioritas

| # | Temuan | Prioritas | Lokasi utama |
|---|---|---|---|
| 1 | IDOR pada chat via `client_uid` self-asserted | Tinggi | `server/handlers/ws_chat.py:64-83` |
| 2 | Rate limiting command WS (termasuk chat) per-IP & berbagi kuota | Tinggi | `server/middleware/__init__.py:38-53`, `server/handlers/websocket.py:222` |
| 3 | Exception mentah (`str(e)`) dikirim ke client | Tinggi | `server/handlers/websocket.py:262-278` |
| 4 | Tidak ada logout semua perangkat / revoke sesi massal | Tinggi | `persistence/session_repo.py` (tidak ada `delete_all_sessions`) |
| 5 | Tidak ada reset password admin resmi | Tinggi | `server/handlers/auth.py` (tidak ada endpoint) |
| 6 | Validasi payload WS hanya diterapkan sebagian; validasi bergantung pada edge, bukan command handler | Tinggi | `server/handlers/ws_schemas.py:82-96` vs `engine/command_router.py:129-134` |
| 7 | `verify_token()` dibuat tapi tidak pernah dipakai | Menengah | `core/security.py:67-69` |
| 8 | PBKDF2-HMAC-SHA256 100.000 iterasi, di bawah rekomendasi OWASP terkini | Menengah | `core/security.py:35-36` |
| 9 | `EXPLORE_QUOTA` dead code (di-import, tidak dipakai) | Menengah | `engine/radio/radio_config.py:32`, `engine/radio/artist_selector.py:36` |
| 10 | Validasi volume tidak konsisten: UI maks 100%, backend hingga 150% | Menengah | `web/static/pages/app/index.html:219` vs `engine/volume_service.py:42-51` |
| 11 | Download otomatis menimpa file lama tanpa konfirmasi | Menengah | `server/handlers/ws_download.py` (jalur `download`) |
| 12 | `Access-Control-Allow-Origin: *` pada endpoint streaming | Menengah | `server/handlers/audio_stream_handler.py:106,230` |
| 13 | Dependency `yt-dlp` tidak dipin ketat (`>=`, bukan `==`) | Menengah | `requirements.txt:1` (`yt-dlp>=2026.6.9`) |
| 14 | Crossfade meninggalkan volume di nilai salah saat terputus | Menengah | `engine/playback/crossfade.py:24-40` |
| 15 | Sleep timer bisa `TypeError` jika command handler dipanggil langsung tanpa lewat schema WS | Menengah | `engine/sleep_timer.py:40`, `engine/command_router.py:129-134` |
| 16 | Unused import, atribut mati, wildcard import lain | Rendah | Tersebar (lihat §5.1) |
| 17 | Hanya mendukung satu akun admin | Rendah | Desain (`core/security.py`, `persistence/`) |
| 18 | Tidak menyediakan HTTPS/TLS bawaan | Rendah | Desain (deployment) |
| 19 | SQLite tanpa strategi scaling, tanpa backup otomatis | Rendah | Desain (`persistence/`) |
| 20 | Testing frontend, i18n, aksesibilitas (ARIA) minim | Rendah | Desain (`web/static/`, `tests/frontend/`) |

---

## 3. Prioritas Tinggi — Root Cause & Desain Perbaikan

### 3.1 IDOR pada chat — `client_uid` dipercaya mentah-mentah dari client

**Bukti.** Di `server/handlers/ws_chat.py:64`:

```python
client_uid = (data.get("client_uid") or "").strip()[:80] or None
```

`client_uid` dibaca langsung dari payload WebSocket yang dikirim client,
lalu dipakai sebagai kunci thread chat untuk `get_recent_messages` (baris
83) dan sebagai penentu siapa yang menerima broadcast balasan (baris
104–115). Tidak ada langkah yang mengikat `client_uid` ke sesi/koneksi
tertentu di sisi server — siapa pun yang tahu atau menebak sebuah
`client_uid` (mis. UUID yang bocor lewat log, screenshot, atau sekadar
brute-force karena tidak ada rate limit khusus di jalur ini) bisa
mengirim `get_chat_history`/`send_chat` dengan `client_uid` milik orang
lain dan membaca atau menyisipkan pesan di thread tersebut.

**Root cause.** `client_uid` berfungsi ganda sebagai *identifier* dan
*credential* — seharusnya hanya boleh jadi identifier tampilan, sementara
kepemilikan thread diverifikasi lewat sesuatu yang tidak bisa dipalsukan
client (ikatan ke koneksi WebSocket yang sedang aktif).

**Desain yang diusulkan.** Ikat `client_uid` ke koneksi saat *pertama
kali* koneksi itu memperkenalkan diri (mis. saat `hello`/koneksi dibuka),
simpan di `ConnectionManager`, dan untuk permintaan berikutnya di
koneksi yang sama abaikan `client_uid` yang dikirim ulang di payload —
pakai yang sudah terikat ke `ws` tersebut:

```python
# server/connection_manager.py
class ConnectionManager:
    def bind_client_uid(self, ws, client_uid: str) -> None:
        """Ikat client_uid ke koneksi ini SEKALI SAJA. Percobaan mengikat
        ulang dengan uid berbeda pada koneksi yang sama ditolak -- ini
        menutup celah 'kirim client_uid orang lain di request kedua'."""
        existing = self.client_uids.get(ws)
        if existing is not None and existing != client_uid:
            raise PermissionError("client_uid koneksi ini sudah terikat")
        self.client_uids[ws] = client_uid

# server/handlers/ws_chat.py
async def handle_chat_command(action, data, ws, repos, manager, is_admin, client_ip):
    ...
    if not is_admin:
        # Non-admin TIDAK BOLEH menentukan target_uid dari payload sama
        # sekali -- satu-satunya sumber kebenaran adalah binding di
        # ConnectionManager untuk koneksi ws ini.
        target_uid = manager.client_uids.get(ws)
        if not target_uid:
            return
    else:
        target_uid = str(data.get("target_uid")) if data.get("target_uid") else None
```

Perubahan intinya: **untuk non-admin, `target_uid` tidak pernah lagi
dibaca dari payload** — hanya dari state koneksi yang dikelola server.
Admin tetap boleh memilih `target_uid` bebas (karena admin memang perlu
melihat semua thread), tapi jalur admin sudah dilindungi `is_admin`
(sesi terautentikasi), bukan oleh nilai yang dikirim client biasa.

Ini non-breaking di sisi frontend: `client.js::getClientUid()` tetap
mengirim `client_uid` di pesan pertama (dipakai untuk *bind*), hanya
perilaku server yang berubah dari "percaya setiap kali dikirim" menjadi
"percaya sekali, kunci setelahnya".

### 3.2 Rate limiting command WS (termasuk chat) — per-IP, kuota dibagi rata semua command

**Bukti.** `check_rate_limit()` (`server/middleware/__init__.py:38-53`)
membatasi 30 command/60 detik **per `client_ip`**, dan dipanggil satu
kali untuk semua jenis command (`server/handlers/websocket.py:222`) —
playback, queue, download, cache, **dan chat** berbagi kuota yang sama.
Login punya rate limit terpisah (`server/handlers/auth.py:92-98`) yang
sudah eksplisit didokumentasikan sebagai berbasis IP dengan catatan risiko
serupa (baris 12).

Konsekuensi: (a) di belakang reverse proxy — yang direkomendasikan di
README (Nginx/Cloudflare Tunnel/ngrok) — semua client eksternal terlihat
satu IP, sehingga satu pengguna yang memutar musik aktif (banyak command
playback) bisa menghabiskan kuota 30/menit dan membuat pengguna lain di
IP yang sama tidak bisa chat sama sekali; (b) 30 command/menit bukan
angka yang dirancang khusus untuk chat — untuk playback (skip, volume,
seek) itu longgar, tapi untuk spam pesan chat teks itu masih cukup untuk
membanjiri broadcast ke semua koneksi aktif (lihat catatan `MAX_MESSAGE_LEN`
di `ws_chat.py:36-39` yang sudah mengakui chat sebagai vektor DoS, tapi
belum diberi kuota sendiri).

**Desain yang diusulkan.** Pisahkan kuota chat dari kuota command umum,
dan kunci berdasarkan `client_uid` (setelah §3.1 di-*bind* ke koneksi)
alih-alih `client_ip`, karena `client_uid` sudah terbukti sebagai kunci
identitas yang lebih tepat untuk chat (alasan yang sama seperti kenapa
`client_uid` dipakai untuk segmentasi thread, lihat docstring
`ws_chat.py:9-16`):

```python
# server/middleware/__init__.py
async def check_chat_rate_limit(manager, key: str, now: float, limit: int = 10) -> bool:
    """Kuota terpisah untuk chat, dikunci per client_uid (fallback ke IP
    untuk koneksi yang belum bind client_uid). 10 pesan/menit -- longgar
    untuk percakapan wajar, cukup ketat untuk memutus spam otomatis."""
    async with manager.rl_lock:
        history = manager.chat_history.get(key, deque())
        while history and now - history[0] >= 60:
            history.popleft()
        if len(history) >= limit:
            return False
        history.append(now)
        manager.chat_history[key] = history
        return True
```

Dipanggil di `handle_chat_command` dengan `key = client_uid or client_ip`
sebelum memproses `send_chat`. Kuota command umum (30/menit per IP) tetap
dipertahankan sebagai lapisan kedua, bukan diganti — jadi ini murni
penambahan, non-breaking.

### 3.3 Exception mentah dikirim ke client

**Bukti.** `server/handlers/websocket.py:262-278`:

```python
except Exception as e:
    logger.error("ws_command_handling_failed", ..., error=str(e), exc_info=True)
    try:
        await ws.send_str(json.dumps({"type": "error", "data": str(e)}))
```

`str(e)` dari exception apa pun yang tidak tertangani di handler command
dikirim langsung sebagai pesan error ke client — berbeda dengan
`WsValidationError` (baris 249-251) yang memang didesain untuk pesan
ramah-pengguna. `Exception` generik bisa berisi path file, nama tabel
SQL, atau detail internal lain yang membantu penyerang memetakan sistem.

**Desain yang diusulkan.** Pisahkan pesan yang *aman ditampilkan*
(exception yang memang didesain untuk itu, seperti `WsValidationError`)
dari yang tidak. Log tetap dapat detail penuh (`exc_info=True` sudah
benar dan dipertahankan), tapi balasan ke client diseragamkan jadi pesan
generik:

```python
except Exception as e:
    logger.error("ws_command_handling_failed", ..., error=str(e), exc_info=True)
    try:
        await ws.send_str(json.dumps({
            "type": "error",
            "data": "Terjadi kesalahan saat memproses permintaan.",
        }))
```

Untuk debugging di lingkungan development, bisa ditambahkan flag
konfigurasi (`config.py`, mis. `DEBUG_EXPOSE_ERRORS`) yang membolehkan
`str(e)` ditampilkan hanya saat eksplisit diaktifkan — default tetap
generik.

### 3.4 Tidak ada logout semua perangkat & reset password admin resmi

**Bukti.** `persistence/session_repo.py` hanya punya `delete_session(token)`
(hapus satu token spesifik) dan `cleanup_sessions()` (hapus yang
kedaluwarsa) — tidak ada method untuk menghapus *semua* sesi aktif
sekaligus. Karena LunaWave hanya mendukung satu akun admin (temuan #17),
tidak perlu filter per-user; cukup `DELETE FROM sessions` tanpa syarat.
Untuk reset password, `server/handlers/auth.py` tidak memiliki endpoint
resmi — satu-satunya jalan saat ini adalah manipulasi database langsung.

**Desain yang diusulkan.**

```python
# persistence/session_repo.py
async def delete_all_sessions(self):
    """Cabut SEMUA sesi aktif sekaligus -- dipakai saat token bocor atau
    admin ganti password. Karena hanya ada 1 akun admin (lihat ADR terkait
    single-admin), tidak perlu filter per-user."""
    await self._conn.execute("DELETE FROM sessions")
    await self._conn.commit()
```

Endpoint baru `logout_all` (WS action, admin-only, mirip pola `logout`
yang sudah ada di `websocket.py:194-199`) memanggil
`repos.sessions.delete_all_sessions()`. Untuk reset password admin: CLI
resmi (`python -m server.reset_admin_password`, dijalankan operator di
mesin server — bukan endpoint HTTP, supaya tidak menambah permukaan
serangan) yang meminta password baru, hash dengan `core/security.py`,
`UPDATE admin_account SET password_hash = ?`, lalu panggil
`delete_all_sessions()` supaya sesi lama otomatis tercabut.

### 3.5 Validasi payload WS: kuat di edge, tidak dijamin di command handler

**Bukti.** `server/handlers/ws_schemas.py:82-96` (`SetSleepTimerPayload`)
sudah memvalidasi input dengan benar (cast `int()`, rentang 0–1440,
`WsValidationError` jika gagal) — tapi validasi ini hanya dipanggil dari
jalur WS spesifik (`ws_playback.py:115-119`). `engine/command_router.py:129-134`
mendaftarkan `CMD_SET_SLEEP_TIMER` ke `command_bus` dengan handler yang
langsung memanggil `sleep_timer.set_timer(data.get("minutes", 0))` —
tanpa validasi apa pun. Karena `command_bus.execute()` adalah API
internal generik (dipakai juga oleh, misalnya, komponen lain di masa
depan: automation, plugin, endpoint admin baru), setiap pemanggil baru
yang tidak melalui `ws_schemas.py` akan langsung memicu
`minutes <= 0` di `engine/sleep_timer.py:40` dengan `minutes` yang bisa
berupa tipe apa pun → `TypeError` tak tertangani.

**Root cause.** Validasi hidup di *edge* (parser WS), bukan di *command
handler* itu sendiri. Ini pola yang sama persis dengan temuan
IDOR di §3.1: mempercayakan kebenaran data ke lapisan yang jauh dari
titik pemakaian.

**Desain yang diusulkan.** Pindahkan validasi minimal ke dalam
`SleepTimer.set_timer()` sendiri, sehingga aman dipanggil dari jalur
mana pun — `ws_schemas.py` tetap dipertahankan sebagai validasi
"cepat gagal dengan pesan ramah" di edge, command handler jadi lapisan
pertahanan kedua:

```python
# engine/sleep_timer.py
async def set_timer(self, minutes) -> None:
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        minutes = 0
    minutes = max(0, min(1440, minutes))
    ...
```

Pola yang sama (validasi ganda: edge + handler) diusulkan diterapkan
bertahap ke command handler lain yang saat ini hanya divalidasi di
`ws_schemas.py` — didaftar sebagai backlog di Fase 2 (§6).

---

## 4. Prioritas Menengah

Ringkas per temuan (root cause sudah diverifikasi di kode; desain
perbaikan bersifat straightforward sehingga tidak diberi sketsa kode
panjang kecuali diperlukan):

**4.1 `verify_token()` dead code** (`core/security.py:67-69`). Fungsi
constant-time compare ini tidak dipanggil di mana pun — verifikasi sesi
aktual di `persistence/session_repo.py:48-56` memakai lookup SQL
berdasarkan hash token (aman, tapi berarti `verify_token()` murni kode
mati). Usul: hapus fungsi jika memang tidak diperlukan, atau — jika
dipertahankan untuk perbandingan token di jalur lain (mis. `X-API-Key`
custom di masa depan) — tambahkan pemanggilan nyata plus test yang
menjamin fungsi ini tidak kembali jadi dead code (`grep`-based check di
CI, konsisten dengan `architecture_lint.py` yang sudah ada).

**4.2 PBKDF2 100.000 iterasi** (`core/security.py:35-36`). OWASP
Password Storage Cheat Sheet terbaru merekomendasikan iterasi PBKDF2-
HMAC-SHA256 yang jauh lebih tinggi. Usul: naikkan ke minimal 600.000
iterasi (angka rekomendasi OWASP saat ini), dengan migrasi bertahap:
simpan jumlah iterasi di dalam hash string (`pbkdf2:sha256:<iter>$...`,
formatnya sudah mendukung ini — lihat parsing di baris 46), sehingga
password lama (100k) tetap valid saat verifikasi, dan di-*rehash*
otomatis ke 600k begitu admin login berhasil berikutnya (upgrade
transparan, tidak memaksa reset password).

**4.3 Dead code lain** — `EXPLORE_QUOTA` di-*import* di
`engine/radio/artist_selector.py:36` tapi tidak pernah dipakai di file
itu (grep mengonfirmasi hanya muncul di baris import). Usul: audit
`artist_selector.py` untuk memastikan apakah logika "explore" radio
memang seharusnya memakai konstanta ini (kemungkinan bug perilaku, bukan
cuma import mati — radio explore-vs-familiar ratio bisa jadi tidak
berjalan sesuai desain) sebelum menghapusnya; jika logikanya memang
hilang, ini naik jadi bug fungsional, bukan cuma cleanup.

**4.4 Batas volume tidak konsisten**. Slider UI di
`web/static/pages/app/index.html:219` (`max="100"`) vs
`engine/volume_service.py:42,51` yang meng-clamp ke 150. Usul: satukan
sumber kebenaran — jadikan `MAX_VOLUME = 100` konstanta di
`engine/volume_service.py`, pakai konstanta yang sama saat merender
`max` attribute slider (lewat template/config yang di-share ke frontend,
bukan angka hardcode dua tempat terpisah).

**4.5 Download menimpa file lama tanpa konfirmasi**
(`server/handlers/ws_download.py`, jalur `download`). Usul: sebelum
memulai download, cek apakah `local_path` tujuan sudah ada; jika ya,
kirim event `download_conflict` ke client agar UI bisa menanyakan
konfirmasi, alih-alih menimpa langsung.

**4.6 `Access-Control-Allow-Origin: *` pada streaming**
(`server/handlers/audio_stream_handler.py:106,230`). Mengizinkan hotlink
dari situs mana pun. Usul: karena endpoint ini melayani `<audio>` yang
dikonsumsi oleh frontend LunaWave sendiri (same-origin dalam pemakaian
normal), turunkan ke origin yang dikonfigurasi eksplisit (`config.py`,
default ke origin server sendiri), bukan wildcard.

**4.7 `yt-dlp` tidak dipin ketat** (`requirements.txt:1`:
`yt-dlp>=2026.6.9`). Usul: pin ke versi eksak (`==`) di
`requirements.txt`/lockfile, dengan proses upgrade terjadwal (mis. bagian
dari checklist rilis) alih-alih auto-update implisit saat instalasi baru.

**4.8 Crossfade meninggalkan volume salah saat terputus**
(`engine/playback/crossfade.py:24-40`). Baik `apply_crossfade_in` maupun
`apply_crossfade_out` berhenti di tengah ramping bila `state.status`
berubah (mis. user menekan stop/pause di tengah fade), tapi tidak
mengembalikan volume MPV ke `state.volume` — volume tertinggal di nilai
parsial. Usul: tambahkan `finally`/`except asyncio.CancelledError` yang
secara eksplisit memanggil `mpv.set_volume(state.volume)` (untuk
crossfade-in yang diinterupsi) atau `mpv.set_volume(0)` lalu biarkan
pemutaran berikutnya yang mengatur ulang (untuk crossfade-out) — supaya
state volume selalu konsisten terlepas dari kapan proses terputus.

---

## 5. Prioritas Rendah — Backlog

Temuan-temuan ini bersifat keterbatasan desain, bukan bug/kerentanan
langsung, sehingga diusulkan sebagai backlog terpisah (tidak masuk
rollout 4 fase di §6) dan dibahas lewat RFC tersendiri bila mau
dieksekusi:

### 5.1 Unused import & atribut mati lain
Selain `EXPLORE_QUOTA` (§4.3), audit menyebut adanya wildcard import dan
atribut mati lain yang tersebar. Usul teknis: jalankan `ruff --select F401,F403,F841`
(atau linter setara yang sudah dipakai proyek — cek `pyproject.toml`)
di seluruh repo sebagai satu PR cleanup terpisah, ditinjau manual
per-file karena wildcard import kadang sengaja dipakai untuk re-export
(lihat pola re-export di `server/middleware/__init__.py:33-35`).

### 5.2–5.6 Keterbatasan desain
Single-admin, tidak ada HTTPS bawaan, SQLite tanpa scaling/backup
otomatis, testing frontend minim, i18n/aksesibilitas minim — semuanya
adalah keputusan desain yang valid untuk aplikasi personal single-user
seperti LunaWave saat ini, bukan cacat yang mendesak. Direkomendasikan
didiskusikan sebagai RFC roadmap terpisah (bukan bagian dari perbaikan
bug/keamanan ini) karena masing-masing punya trade-off arsitektur
sendiri (mis. multi-admin butuh desain role/permission baru, bukan
sekadar patch).

---

## 6. Rencana Rollout Bertahap

Empat fase, masing-masing independen dan bisa dihentikan tanpa
meninggalkan kode rusak — konsisten dengan pola rollout di RFC
sebelumnya (`docs/rfc/arsip/`):

**Fase 1 — Kebocoran informasi & sesi (low risk, tanpa perubahan skema DB)**
- §3.3 Exception generik ke client
- §3.4 `logout_all` + CLI reset password admin (butuh 1 migrasi kecil: tidak ada skema baru, hanya query baru)
- §4.6 CORS non-wildcard pada streaming

**Fase 2 — Validasi & rate limiting**
- §3.1 IDOR chat (binding `client_uid` ke koneksi)
- §3.2 Rate limit chat terpisah
- §3.5 Validasi ganda command handler (mulai dari sleep timer, lalu command lain sebagai backlog eksplisit)

**Fase 3 — Kriptografi & dependency**
- §4.2 Naikkan iterasi PBKDF2 + rehash transparan
- §4.7 Pin `yt-dlp` ke versi eksak

**Fase 4 — Cleanup & konsistensi**
- §4.1 verify_token() (hapus atau pakai nyata)
- §4.3 EXPLORE_QUOTA (audit dulu apakah bug fungsional, baru cleanup)
- §4.4 Batas volume konsisten
- §4.5 Konfirmasi overwrite download
- §4.8 Crossfade volume restore
- §5.1 Unused import sapuan penuh

## 7. Kriteria Penerimaan (ringkas)

- Fase 1: test baru memastikan pesan error ke client tidak pernah
  memuat `type(e).__name__`/traceback; `logout_all` mencabut sesi lain
  yang sedang aktif dalam test integrasi.
- Fase 2: test yang mengirim `client_uid` berbeda pada koneksi yang
  sama harus ditolak (`PermissionError`/error terkontrol, bukan
  membaca thread lain); test spam >10 pesan/menit dari satu
  `client_uid` harus kena limit walau `client_ip` bervariasi (simulasi
  reverse proxy) dan sebaliknya.
- Fase 3: password lama (hash 100k iterasi) tetap bisa login, lalu
  ter-*rehash* ke 600k di baris DB setelah satu login sukses.
- Fase 4: `ruff`/linter proyek bersih dari F401/F841 di file yang
  disentuh; test crossfade-interrupted memverifikasi `mpv.set_volume`
  dipanggil dengan nilai akhir yang benar.

---

## 8. Kesimpulan

Pola yang berulang di seluruh temuan Prioritas Tinggi adalah kepercayaan
implisit terhadap data/kondisi yang sebenarnya berasal dari — atau bisa
dipengaruhi oleh — sisi client atau lapisan yang terlalu jauh dari titik
pemakaian: `client_uid` mentah untuk otorisasi chat, kuota rate limit
yang dibagi rata tanpa mempertimbangkan reverse proxy, exception mentah
yang bocor ke luar boundary server, dan validasi yang hanya hidup di
parser WS alih-alih di command handler itu sendiri. Perbaikan yang
diusulkan di sini secara konsisten memindahkan titik kebenaran (source of
truth) ke sisi server dan ke titik pemakaian data itu sendiri, tanpa
mengubah kontrak API yang sudah ada di frontend — sehingga seluruh Fase 1–4
bisa dieksekusi tanpa breaking change bagi pengguna.
