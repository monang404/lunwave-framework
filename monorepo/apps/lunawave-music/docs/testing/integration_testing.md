# Integration Testing

> Integration tests menguji alur end-to-end menggunakan komponen asli (bukan fakes).
> Membutuhkan **MPV** dan **yt-dlp** terinstall di environment.
> Untuk unit tests, lihat → [unit_testing.md](unit_testing.md)

---

## Prasyarat

```bash
# Pastikan MPV dan yt-dlp tersedia
which mpv        # harus ada
which yt-dlp     # harus ada

# Jalankan
pytest tests/integration/ -v
```

> **Catatan CI:** Integration tests tidak dijalankan di pipeline CI standar karena membutuhkan MPV dan yt-dlp. Lihat → [../devops/ci_cd.md](../devops/ci_cd.md)

---

## Skenario Integration Test

### IT-01: WebSocket Flow

**File:** `tests/integration/test_websocket_flow.py`

**Skenario:** Connect → auth → play → state broadcast

```
Client WebSocket
    ↓ connect
Server (aiohttp WebSocket handler)
    ↓ auth handshake
Session valid
    ↓ send: {"action": "play", "url": "..."}
CommandBus → PlaybackEngine → MPV (asli)
    ↓ MPV playing
EventBus publish: track_started
    ↓ broadcast ke semua client
Client menerima state update: {"status": "playing", "track": {...}}
```

**Assert:**
- Client berhasil connect tanpa error
- Auth diterima, session token valid
- Setelah command `play`, client menerima event `track_started` dalam X detik
- State yang diterima mengandung field `status`, `track`, `position`

---

### IT-02: Playback Flow

**File:** `tests/integration/test_playback_flow.py`

**Skenario:** Play → pause → next (via `CommandBus` asli)

```
CommandBus.dispatch(PlayCommand(url="..."))
    ↓
PlaybackEngine → MPV (asli) → track mulai
    ↓ (assert: MPV process running)
CommandBus.dispatch(PauseCommand())
    ↓
MPV pause → EventBus publish: playback_paused
    ↓ (assert: event diterima)
CommandBus.dispatch(NextCommand())
    ↓
QueueManager pop next track → MPV load track baru
    ↓ (assert: track berbeda dari sebelumnya)
```

**Assert:**
- Urutan event: `track_started → playback_paused → track_started` (track kedua)
- Tidak ada asyncio task yang leak setelah sequence selesai
- MPV process mati bersih setelah teardown

---

### IT-03: Radio Flow

**File:** `tests/integration/test_radio_flow.py`

**Skenario:** Radio aktif → prefetch → auto-next

```
CommandBus.dispatch(EnableRadioCommand(artist="Sheila on 7"))
    ↓
RadioEngine aktif → ArtistSelector pilih track
    ↓
TrackFilter filter duplikat
    ↓
Prefetcher resolve URL (via yt-dlp asli)
    ↓ (URL prefetched, ready in cache)
Track selesai → RadioEngine auto-load next track dari prefetch cache
    ↓
EventBus publish: track_started (track baru)
```

**Assert:**
- Setelah radio enabled, queue terisi minimal 1 track dalam Y detik
- Prefetcher mengisi cache sebelum track pertama selesai
- Auto-next terjadi tanpa gap (track baru load dari cache, bukan fresh resolve)
- `track_filter.py` tidak memasukkan duplikat ke queue

---

### IT-04: Download Flow

**File:** `tests/integration/test_download_flow.py`

**Skenario:** Download → progress event → selesai

```
CommandBus.dispatch(DownloadCommand(url="...", format="mp3"))
    ↓
DownloadManager → yt-dlp (asli) → file didownload
    ↓ (setiap progress hook dari yt-dlp)
EventBus publish: download_progress {percent: N, speed: "..."}
    ↓ (broadcast ke client)
Download selesai → file ada di cache/mp3/
    ↓
EventBus publish: download_complete {path: "cache/mp3/..."}
```

**Assert:**
- Event `download_progress` diterima minimal sekali selama proses
- Event `download_complete` diterima setelah proses selesai
- File hasil download ada di `cache/mp3/` dengan nama yang benar
- Tidak ada error asyncio (task exception tidak tertelan)

---

## Teardown & Isolation

Setiap integration test harus memastikan:

1. **MPV & yt-dlp process mati** — gunakan fixture yang memanggil `kill` (atau taskkill di Windows) untuk mematikan subprocess MPV dan yt-dlp secara eksplicit (mencegah *zombie process* yang memblokir penutupan *event loop* pada CI).
2. **Cache dibersihkan** — download test menggunakan directory temporary, bukan `cache/mp3/` asli
3. **Database** — gunakan `:memory:` SQLite atau temporary file, bukan database development
4. **Port tidak bentrok** — server test menggunakan port acak (misalnya `port=0`), bukan port 8000

```python
# Contoh fixture teardown
@pytest.fixture
async def integration_server():
    server = LunaWaveServer(port=0, db=":memory:")
    await server.start()
    yield server
    await server.stop()
    os.system("pkill -f mpv")  # pastikan MPV mati
    os.system("pkill -f yt-dlp")  # pastikan yt-dlp mati agar event loop teardown tidak hang di CI
```

---

## Referensi Terkait

- Unit tests per layer → [unit_testing.md](unit_testing.md)
- Filosofi & fakes → [testing_strategy.md](testing_strategy.md)
- Data flow yang ditest → [../architecture/data_flow.md](../architecture/data_flow.md)
- Radio engine detail → [../backend/background_jobs.md](../backend/background_jobs.md)
- Download manager detail → [../backend/background_jobs.md](../backend/background_jobs.md)
