# Background Jobs

← [architecture/backend.md](../architecture/backend.md) | [Blueprint.md](../Blueprint.md)

---

## Gambaran Umum

LunaWave memiliki dua jenis background job yang berjalan async:

| Job | File | Trigger |
|---|---|---|
| Download Manager | `engine/download_manager.py` | `CMD_DOWNLOAD_START` |
| Radio Prefetcher | `engine/radio/prefetcher.py` | `EVENT_TRACK_CHANGED` saat mode radio |
| Stream Prefetch | `services/stream_prefetch.py` | `EVENT_TRACK_CHANGED` |

Semua berjalan sebagai asyncio task — tidak ada thread pool, tidak ada celery, tidak ada external queue.

---

## Download Manager

### Tanggung Jawab

- Mengelola antrian download MP3
- Menjalankan download satu per satu (bukan paralel) untuk menghindari rate limit yt-dlp
- Melaporkan progress ke event bus
- Menyimpan hasil ke `cache/mp3/`

### State Download

```python
@dataclass
class DownloadJob:
    video_id: str
    title: str
    status: DownloadStatus   # QUEUED | DOWNLOADING | DONE | ERROR | CANCELLED
    pct: int                 # 0–100
    error: str | None = None
```

### Alur Kerja

```
CMD_DOWNLOAD_START {video_id}
        │
        ▼
download_manager.enqueue(video_id)
        │
        ▼ (async, background)
loop: ambil job dari antrian
        │
        ├── resolve stream URL (cache/resolver.py)
        │
        ├── ytdlp_adapter.download_mp3(url, dest=cache/mp3/{video_id}.mp3)
        │       └── progress_hook → EventBus.publish(EVENT_DOWNLOAD_PROGRESS)
        │
        ├── update job.status = DONE
        │
        ├── persistence.track_repo.update_file_path(video_id, path)
        │
        └── EventBus.publish(EVENT_DOWNLOAD_COMPLETE)
```

### Concurrent Downloads

Default: **1 download sekaligus**. Antrian FIFO.

Alasan tidak paralel:
- yt-dlp dapat di-rate-limit jika terlalu banyak request bersamaan
- Download yang overlap menyulitkan progress tracking

### Pembatalan

```
CMD_DOWNLOAD_CANCEL {video_id}
        │
        ├── Jika status QUEUED → hapus dari antrian langsung
        └── Jika status DOWNLOADING → set flag cancel → yt-dlp check flag di progress hook
```

### Persistensi Antrian

Antrian **tidak persisten** lintas restart. Jika server restart, download yang sedang berjalan harus dimulai ulang dari frontend.

### Error Handling

| Error | Tindakan |
|---|---|
| yt-dlp gagal resolve | status = ERROR, publish event error |
| Disk penuh | status = ERROR, log warning |
| Download dibatalkan | status = CANCELLED |
| Timeout | Retry sekali, lalu ERROR |

Test → `tests/unit/engine/test_download_manager.py`

---

## Radio Prefetcher

### Tanggung Jawab

Prefetch track berikutnya untuk mode radio **sebelum** track saat ini selesai, agar tidak ada jeda saat skip/autoplay.

### Alur Kerja

```
EVENT_TRACK_CHANGED (saat mode radio)
        │
        ▼
prefetcher.schedule_next()
        │
        ▼ (async, setelah delay singkat)
artist_selector.select_next(history)
        │
        ▼
ytdlp_adapter.search(artist + " music")
        │
        ▼
track_filter.filter(results, history, queue)
        │
        ▼
queue_manager.enqueue(next_track)
        │
        ▼
stream_prefetch.prefetch(next_track.video_id)
```

### Timing

Prefetch dimulai **5 detik** setelah `EVENT_TRACK_CHANGED` untuk menghindari konflik dengan track yang baru dimuat.

### Cancellation

Jika `CMD_RADIO_STOP` diterima, semua prefetch task dibatalkan via `core/task_utils.py`.

Test → `tests/unit/engine/radio/test_prefetcher.py`

---

## Stream Prefetch Service

### Tanggung Jawab

Berbeda dari Radio Prefetcher — ini berlaku untuk **semua mode**, bukan hanya radio. Tugasnya: resolve URL stream untuk track ke-2 di queue segera setelah track ke-1 mulai diputar.

```
EVENT_TRACK_CHANGED
        │
        ▼
Ambil track[1] dari queue (track berikutnya)
        │
        ▼
cache/resolver.py: ada?
        ├── Ya → selesai
        └── Tidak → ytdlp_adapter.resolver.get_stream_url(video_id)
                    └── simpan ke cache
```

**Tidak ada event yang di-publish** — ini murni background optimization.

Test → `tests/unit/services/test_stream_prefetch.py`

---

## Monitoring Background Jobs

Status semua download job tersedia di `full_state`:

```json
{
  "downloads": [
    { "video_id": "abc", "title": "Creep", "status": "downloading", "pct": 63 },
    { "video_id": "def", "title": "Karma Police", "status": "queued", "pct": 0 }
  ]
}
```

Prefetch task tidak diekspos ke frontend — transparan.

---

## Dokumen Terkait

- [backend/services.md](services.md) — Radio engine (orchestrator)
- [backend/caching.md](caching.md) — Cache resolver (dipakai oleh prefetch & download)
- [backend/api.md](api.md) — Format event `download_progress`
- [testing/unit_testing.md](../testing/unit_testing.md) — Test download_manager & prefetcher
