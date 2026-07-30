# Backend Services

← [architecture/backend.md](../architecture/backend.md) | [Blueprint.md](../Blueprint.md)

---

## Engine Layer

Engine adalah domain logic utama LunaWave. Semua handler di engine hanya berbicara ke `core/` lewat ports — tidak ada import langsung ke `adapters/` atau `persistence/` kecuali lewat injeksi dependency.

---

### `engine/command_router.py`

`CommandRouter` mendaftarkan setiap `CMD_*` (dari `core/command_bus.py` / `core/commands.py`) ke `command_bus`, dibungkus tipis agar handler sync maupun async bisa dipanggil seragam. Bukan dict `HANDLERS` statis — registrasi terjadi di `__init__` via `command_bus.register(CMD_X, self._route(...))`.

```python
class CommandRouter:
    def __init__(self, playback_controller, volume_service, sleep_timer=None):
        command_bus.register(CMD_PLAY_TRACK, self._route(lambda c, data: c._on_cmd_play_track(data)))
        command_bus.register(CMD_TOGGLE_PAUSE, self._route(lambda c, data: c._on_cmd_toggle_pause(data)))
        command_bus.register(CMD_NEXT, self._route(lambda c, data: c._on_next(data)))
        # ... CMD_PREV, CMD_STOP, CMD_SEEK, CMD_SET_MODE, CMD_QUEUE_*,
        #     CMD_RADIO_RANDOMIZE, CMD_SET_OUTPUT, CMD_SET_SPONSORBLOCK,
        #     CMD_SET_LOUDNESS_NORMALIZATION, CMD_LYRICS_OFFSET -> playback_controller
        command_bus.register(CMD_VOLUME_UP, self._route_volume(lambda v, data: v._on_volume_up(data)))
        # ... CMD_VOLUME_DOWN, CMD_VOLUME_SET -> volume_service
        command_bus.register(CMD_SET_CROSSFADE, self._route(lambda c, data: c._mode_ops.set_crossfade(data)))
        # ... CMD_SET_SPEED, CMD_SET_LOOP -> playback_controller._mode_ops
        if self.sleep_timer:
            command_bus.register(CMD_SET_SLEEP_TIMER, self._route_sleep(...))  # -> sleep_timer
```

Test → `tests/unit/engine/test_command_router.py`

---

### `engine/playback/controller.py`

Orchestrator playback. Method transport (play/pause/next/prev/stop/seek) tetap di `controller.py`; sisanya didelegasikan tipis ke dua sub-controller (`PATCH-2026-07-18-085`).

**Tanggung jawab:**
- Menerima `CMD_PLAY_TRACK` → panggil `track_loader.py` (resolve URL cache → yt-dlp, load ke player)
- Menerima `CMD_TOGGLE_PAUSE` / `CMD_NEXT` / `CMD_PREV` / `CMD_SEEK` → panggil port `AudioPlayerPort`
- Publish event (`core/events.py`) ke event bus setelah setiap aksi

**Tidak boleh:**
- Akses langsung ke MPV (lewat port saja)
- Akses langsung ke database (lewat `persistence/` saja)

Sub-modul:

| File | Tanggung Jawab |
|---|---|
| `track_loader.py` | Resolve URL (cache → yt-dlp) lalu load ke player |
| `queue_controller.py` | `_on_queue_*` / `_advance_to_next` — operasi queue & auto-advance |
| `settings_controller.py` | `_on_set_mode` / `_on_set_output` / `_on_set_sponsorblock` / `_on_set_loudness_normalization` / `_on_radio_randomize` / `_on_lyrics_offset` |
| `mode_ops.py` | `set_crossfade` / `set_speed` / `set_loop` (dipanggil dari `command_router.py`) |
| `queue_ops.py` | Operasi queue level-rendah dipakai `queue_controller.py` |
| `crossfade.py` | Logic crossfade (fade in/out volume) |
| `track_ended_ops.py` | Penanganan saat track selesai diputar |
| `failure_ops.py` | Penanganan gagal load / error track (skip, retry, mark unavailable) |

⚠️ File ini di-freeze dari perubahan struktural tanpa izin eksplisit — lihat `AI_CONTEXT.md`.

Test → `tests/unit/engine/playback/`

---

### `engine/radio/engine.py` (`RadioMode`)

Orchestrator radio mode. Mengelola siklus lewat standby prefetch, bukan search-per-next sederhana.

**Alur radio (`on_activated` / `next`):**

```
on_activated(controller)
      │
      ▼
artist_selector.ensure_artists_loaded()  (sekali)
      │
      ▼
_start(controller)
      │
      ├─ prefetcher.pop_standby() ada?
      │     ├─ YA  → clear+extend radio_queue, play_track(track[0]),
      │     │        trigger_build_standby() (background, siapkan berikutnya)
      │     └─ TIDAK → artist_selector.gather_batch(ARTISTS_QUICK, timeout 20s)
      │                 → play_track() segera, lalu _backfill_and_standby()
      │                   di background (fetch sisa artis + trigger standby)
      ▼
next(controller)   ← dipanggil saat track_ended
      │
      ├─ radio_queue tidak kosong → pop kiri, play_track();
      │   kalau sisa ≤5, ensure_standby() di background
      └─ radio_queue kosong → _start() lagi (refill)
```

**⚠️ Titik rawan:** `engine/radio/track_filter.py` (dipakai `artist_selector.py`) adalah sumber bug radio mode yang paling umum — filter terlalu agresif menyebabkan queue kosong. Prioritas test tertinggi.

Sub-modul:

| File | Tanggung Jawab | Catatan |
|---|---|---|
| `engine.py` | `RadioMode` — lifecycle (`on_activated`/`on_deactivated`), `next`, `_start`, `_fetch_and_play_initial` (tombol Acak) | |
| `prefetcher.py` (`RadioPrefetcher`) | Standby prefetch batch berikutnya secara background | Async task |
| `artist_selector.py` (`ArtistSelector`) | `gather_batch()` pilih artis via bandit (BANDIT_QUOTA artis) + explore (EXPLORE_QUOTA acak) + ambil lagu, terapkan `TrackFilter` | |
| `track_filter.py` (`TrackFilter`) | Filter duplikat, recently-played, blacklist | ⚠️ Bug-prone |
| `track_interleaver.py` | Interleave lagu antar-artis agar tidak menumpuk per-artis | |
| `artist_bandit.py` | Thompson Sampling reward tracking (dipakai bareng `ArtistRepository.record_completion/record_skip`) | |
| `radio_config.py` | Konstanta: `BANDIT_QUOTA` (jumlah artis dari bandit per batch), `EXPLORE_QUOTA` (artis eksplorasi acak), `ARTISTS_PER_BATCH`, `ARTISTS_QUICK`; helper `track_task` | |

Test → `tests/unit/engine/radio/` — `test_track_filter.py` prioritas tertinggi.

---

### `engine/queue_manager.py`

**Catatan:** operasi queue (add/remove/reorder/select) **tidak** ada di file ini — sudah pindah ke `engine/playback/queue_ops.py` (`QueueOps`) + `queue_controller.py` (dijelaskan di §`engine/playback/controller.py` di atas). `queue_manager.py` sekarang hanya berisi `QueueMode`, penentu mode lanjutan (normal/radio/shuffle) saat sebuah track selesai:

```python
class QueueMode:
    async def next(self, controller: "PlaybackController") -> None:
        # Tentukan track berikutnya sesuai mode aktif (delegasi ke
        # RadioMode.next() kalau mode radio, atau queue biasa lewat state)
        ...
```

`QueueOps` (`engine/playback/queue_ops.py`):

```python
class QueueOps:
    async def queue_select(self, index: int) -> TrackInfo | None
    async def add_track(self, track: TrackInfo) -> None
    async def remove_track(self, index: int) -> None
    async def replace_queue(self, tracks: list[TrackInfo]) -> None
    async def reorder(self, from_index: int, to_index: int) -> None
```

State queue disimpan di `core/state.py`, bukan di `queue_ops.py`/`queue_manager.py` sendiri. Setiap operasi → publish event queue-terkait ke `core/events.py`.

Test → `tests/unit/engine/test_queue_manager.py`, `tests/unit/engine/playback/test_queue_ops.py`, `tests/unit/engine/playback/test_queue_controller.py`

---

### `engine/volume_service.py`

`VolumeService` — handle `CMD_VOLUME_UP`/`_DOWN`/`_SET`. Volume 0–150 (bukan 0–100), dan disuppress ke `0` di MPV saat `audio_output == BROWSER` (browser yang mengatur volume sendiri via `<audio>` tag).

```python
class VolumeService:
    async def _on_volume_up(self, _data=None):
        self.current_volume = min(150, self.current_volume + 5)
        await self._apply_volume()

    async def _on_volume_set(self, data):
        vol = data.get("volume", 80)
        self.current_volume = max(0, min(150, int(vol)))
        await self._apply_volume()

    async def _apply_volume(self):
        if self.state.audio_output == AudioOutput.BROWSER:
            await self.mpv.set_volume(0)
        else:
            await self.mpv.set_volume(self.current_volume)
        self.state.volume = self.current_volume
```

Test → `tests/unit/engine/test_volume_service.py`

---

## Services Layer

### `services/discover_service.py`

`DiscoverService` — wrapper tipis di atas `DiscoverRepository` (lihat [backend/persistence.md](persistence.md#discoverrepository-discover_repopy)), bukan lagi rule-based sederhana di layer service. Method: `get_recent`, `get_favorites`, `get_cached`, `get_featured_artists`, `get_featured_genres`, `get_for_you` (bandit-ranked), `get_unheard`, `get_genre_affinity`, `get_taste_spectrum`, `get_artist_detail`, `search_tracks` (FTS5 quick search). Detail konsumsi end-to-end (WS handler, frontend) → §Discover Tab Personalization di `STATUS.md`.

Test → `tests/unit/services/test_discover_service.py`

---

### `services/stream_prefetch.py`

Prefetch URL stream untuk track berikutnya di queue, sebelum dibutuhkan.

**Kapan berjalan:** setelah `EVENT_TRACK_CHANGED`, resolve URL track ke-2 di queue secara background.

**Kenapa:** yt-dlp resolve bisa 1–3 detik. Prefetch menghilangkan jeda saat skip.

Test → `tests/unit/services/test_stream_prefetch.py`

---

### `server/broadcast_service.py` (T2.7: tetap di `server/`, bukan `services/`)

Subscribe ke `event_bus` dan broadcast state ke semua koneksi WebSocket aktif.

```python
# Setiap event yang relevan → serialize state → kirim ke semua WS
async def on_event(event_type: str, payload: dict) -> None:
    message = serialize_state(state, event_type, payload)
    await connection_manager.broadcast(message)
```

**Catatan T2.7 (deviasi dari rencana awal):** roadmap awalnya mengarahkan
`server/services/broadcast_service.py` pindah ke root `services/` (disatukan
dengan `stream_prefetch.py` dan `discover_service.py`). Itu **tidak
dilakukan** untuk file ini karena `BroadcastService` meng-import
`server.connection_manager` (pengelola koneksi WebSocket mentah) dan
`server.serializers` — keduanya murni konstruksi web/wire layer, bukan
business logic. Memindahkannya ke `services/` akan melanggar kontrak
`.importlinter` "services hanya boleh import core dan persistence" (kontrak
ini sempat tidak terdeteksi karena bug syntax di `.importlinter` — lihat
`PATCH-2026-07-18-089` — begitu diperbaiki, pelanggaran ini langsung
terverifikasi). `stream_prefetch.py` tidak punya masalah ini (hanya impor
`config`+`core`) sehingga tetap pindah ke `services/` sesuai rencana.

Konvensi suffix `_service.py`: dipakai untuk kelas yang mewakili
use-case/orchestration murni tanpa dependency layer lain (`discover_service.py`,
`stream_prefetch.py` — meski tanpa suffix, keduanya konsisten sebagai
"service" business-logic). `broadcast_service.py` tetap pakai suffix karena
memang me-representasikan orchestration (fan-out ke semua koneksi), namun
lokasinya di `server/` mencerminkan bahwa ia terikat erat ke web layer.

Berkaitan dengan → [backend/api.md](api.md) (format pesan)

Test → `tests/unit/server/test_broadcast_service.py`

---

## Plugins

Plugin mengimplementasikan port dari `core/ports.py`. Tidak ada dependency ke `engine/` atau `server/`.

### `plugins/lyrics_fetcher.py`

Implements `LyricsProvider`.

```python
async def fetch(self, title: str, artist: str) -> LyricsResult | None:
    # coba provider 1 (LRCLIB), fallback ke provider 2
```

### `plugins/lyrics_parser.py`

Parse format LRC (timed lyrics) dan SRT menjadi `List[LyricLine]`.

```python
@dataclass
class LyricLine:
    timestamp: float   # detik
    text: str
```

### `plugins/lyrics_sync.py`

Subscribe `EVENT_POSITION_CHANGED` → cari lyric line yang tepat → publish `EVENT_LYRIC_LINE`.

### `plugins/sponsorblock.py`

Implements `SponsorBlockProvider`. Fetch segment dari SponsorBlock API, publish `EVENT_SEGMENT_SKIP` saat posisi masuk segment sponsor.

### `plugins/notifications.py`

Implements `NotificationProvider`. Kirim desktop notification saat track berubah.

---

## Fake Implementations

Semua port memiliki fake untuk unit test:

| Fake | Implements | Lokasi |
|---|---|---|
| `FakeAudioPlayer` | `AudioPlayerPort` | `tests/fakes/fake_audio_player.py` |
| `FakeMediaExtractor` | `MediaExtractorPort` | `tests/fakes/fake_media_extractor.py` |
| `FakeLyricsProvider` | `LyricsProvider` | `tests/fakes/fake_lyrics_provider.py` |
| `FakeSponsorBlock` | `SponsorBlockProvider` | `tests/fakes/fake_sponsorblock_provider.py` |

---

## Dokumen Terkait

- [architecture/domain.md](../architecture/domain.md) — Port & Protocol definitions
- [backend/background_jobs.md](background_jobs.md) — Download manager & radio prefetch detail
- [backend/api.md](api.md) — Format pesan WebSocket
- [testing/unit_testing.md](../testing/unit_testing.md) — Tabel unit test engine & services
