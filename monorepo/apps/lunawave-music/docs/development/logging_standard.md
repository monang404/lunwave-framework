---
title: LunaWave Logging Standard
status: Official Specification
scope: Seluruh backend Python (server, engine, core, adapters, persistence, services)
last_verified: 2026-07-22
---

# LOGGING_STANDARD.md — Spesifikasi Resmi Logging LunaWave

> Dokumen ini adalah **spesifikasi konseptual**, bukan panduan implementasi.
> Ia mendefinisikan *perilaku* logging yang benar untuk LunaWave: apa yang
> harus dicatat, kapan, dengan level apa, dan dalam bentuk seperti apa.
> Detail teknis (library, handler, formatter, konfigurasi) sengaja tidak
> dibahas — itu wilayah sesi implementasi berikutnya.
>
> Dokumen ini **tidak** menilai implementasi logging yang sudah ada di
> repository saat ini. Ia adalah target baru yang akan menjadi acuan
> Gap Analysis pada sesi berikutnya.

---

## 1. Tujuan Logging

LunaWave adalah music player berbasis YouTube yang berjalan sebagai server
lokal (aiohttp + asyncio), sering di lingkungan bersumber daya terbatas
(Termux/Android) dan berumur panjang (dijalankan berjam-jam sambil memutar
musik/radio tanpa supervisi langsung). Log adalah satu-satunya jendela untuk
memahami apa yang terjadi di dalam proses tersebut. Log di LunaWave punya
empat tujuan konkret, urut dari yang paling sering dipakai:

1. **Debugging** — merekonstruksi urutan kejadian ketika playback macet,
   MPV disconnect, radio mode berhenti mengantre lagu, atau download gagal
   — tanpa harus mereproduksi bug secara live.
2. **Observability runtime** — memahami kesehatan proses yang berjalan lama:
   apakah background task (radio prefetcher, download manager, mpv observer
   loop) masih hidup dan bekerja normal, atau diam-diam macet.
3. **Audit keamanan** — mencatat jejak percobaan autentikasi, sesi yang
   dibuat/dicabut, dan aksi admin, tanpa pernah mengekspos rahasia.
4. **Basis observability masa depan** — log hari ini harus bisa dialirkan ke
   sistem observability (dashboard, alerting, log aggregator) tanpa perlu
   ditulis ulang. Ini berarti setiap baris log harus berdiri sendiri secara
   semantik, bukan hanya masuk akal bila dibaca berurutan oleh manusia.

Log **bukan** dokumentasi arsitektur, **bukan** pengganti test, dan
**bukan** saluran komunikasi ke pengguna akhir (itu tugas WebSocket event
ke frontend). Log adalah alat operator dan alat AI-agent untuk memahami apa
yang benar-benar terjadi di dalam sistem.

---

## 2. Design Principles

Prinsip-prinsip ini adalah lensa untuk setiap keputusan logging berikutnya
di dokumen ini dan di masa depan.

**1. Satu event, satu baris.**
Setiap kejadian yang layak dicatat menghasilkan tepat satu baris log
terstruktur. Tidak ada log yang dipecah menjadi beberapa baris untuk satu
kejadian yang sama (kecuali stack trace pada error, yang secara inheren
multi-baris).

**2. Behavior, bukan implementasi.**
Log mendeskripsikan apa yang *terjadi pada domain* (track dimuat, sesi
radio dimulai, autentikasi gagal), bukan detail implementasi internal yang
akan berubah (nama variabel, urutan pemanggilan fungsi). Log yang terikat
erat pada implementasi menjadi usang begitu kode direfaktor.

**3. Data di field, bukan di kalimat.**
Nilai yang berubah-ubah (video_id, durasi, jumlah retry, kode error) selalu
berada di structured field, bukan disisipkan ke dalam kalimat pesan. Ini
membuat pesan tetap konsisten dan bisa di-grep/diagregasi tanpa parsing
string bebas.

**4. Boundary adalah tempat paling layak dicatat.**
LunaWave berbicara ke banyak sistem eksternal yang tidak bisa dipercaya
sepenuhnya: proses MPV lewat IPC socket, YouTube lewat yt-dlp, SQLite,
dan browser lewat WebSocket. Setiap kali eksekusi melewati batas ini —
terutama saat batas itu gagal — adalah titik dengan nilai log tertinggi.
Logic murni di dalam `core/` (yang sudah dites unit habis-habisan) butuh
jauh lebih sedikit log daripada titik-titik boundary ini.

**5. Async dan background butuh jejak yang bisa disatukan.**
LunaWave berjalan di atas asyncio dengan banyak task konkuren (WebSocket
per klien, radio prefetcher, download manager, mpv observer loop). Tanpa
identitas korelasi, log dari task-task ini akan bercampur dan tidak bisa
direkonstruksi urutannya. Setiap alur (sesi WebSocket, satu eksekusi
command, satu siklus radio) harus bisa disatukan kembali dari log-nya.

**6. Diam itu pilihan, bukan default.**
Tidak logging itu valid — untuk hot path yang sudah diverifikasi lewat
test dan tidak pernah gagal secara diam-diam. Tapi keputusan untuk tidak
logging harus disengaja, bukan karena lupa.

**7. Level adalah kontrak, bukan selera.**
Severity level punya makna operasional yang tetap (lihat §3). Tim/AI agent
manapun yang menambah log baru harus bisa memilih level yang benar tanpa
menebak, karena definisinya presisi dan tidak tumpang tindih.

**8. Rahasia tidak pernah masuk log.**
Password, token sesi mentah, dan kredensial apa pun tidak boleh muncul di
log dalam bentuk apa pun — termasuk di level DEBUG. Lihat §11 untuk detail.

**9. Sederhana lebih baik daripada lengkap.**
LunaWave adalah aplikasi single-user/self-hosted, bukan sistem enterprise
multi-tenant. Standar ini sengaja tidak mengadopsi taksonomi logging
enterprise yang berat (misal puluhan kategori, skema field bertingkat).
Field dan kategori yang ada harus bisa dihafal, bukan dicari di manual.

---

## 3. Severity Standard

Lima level standar, masing-masing dengan makna operasional yang presisi
dan use-case konkret dari domain LunaWave. Level tidak boleh dipilih
berdasarkan "seberapa penting perasaan saya tentang ini", tapi berdasarkan
definisi berikut.

| Level | Makna Operasional | Contoh Domain LunaWave |
|---|---|---|
| **DEBUG** | Detail granular yang hanya relevan saat menelusuri masalah spesifik secara aktif. Tidak relevan untuk operasi normal. | Payload command mentah dari WebSocket, isi keputusan `track_filter.py` per kandidat lagu, state transisi internal playback controller |
| **INFO** | Kejadian normal yang menandai progres alur bisnis yang sah dan diharapkan terjadi. Aliran cerita utama aplikasi. | Track mulai diputar, sesi radio dimulai, download selesai, klien WebSocket connect/disconnect, sesi login berhasil |
| **WARNING** | Kondisi tidak ideal yang **berhasil ditangani** oleh sistem tanpa mengganggu alur pengguna secara fatal, tapi menandakan sesuatu yang menyimpang dari jalur normal dan sebaiknya diketahui. | Retry sebelum berhasil, MPV reconnect setelah drop, cache miss yang memaksa resolve ulang, lyrics tidak ditemukan, SponsorBlock API gagal (fitur degradasi, bukan mati) |
| **ERROR** | Satu operasi/alur gagal dan **tidak bisa diselesaikan** sebagaimana diminta, tapi proses aplikasi secara keseluruhan tetap berjalan dan bisa melayani permintaan lain. | Resolusi stream gagal untuk satu video_id, download gagal setelah semua retry habis, command ditolak karena state tidak valid, query SQLite gagal |
| **CRITICAL** | Kondisi yang mengancam **keberlangsungan proses aplikasi itu sendiri** — bukan satu operasi, tapi kemampuan aplikasi untuk terus melayani sama sekali. Operator harus bertindak. | Gagal bind port saat startup, tidak bisa membuka/migrasi database saat boot, MPV tidak bisa dihubungkan sama sekali di awal (fitur inti mati total), proses akan exit tak terkendali |

Aturan pembeda kunci:

- **WARNING vs ERROR**: tanyakan "apakah alur yang diminta pengguna/sistem
  pada akhirnya tetap tercapai?" Jika ya (meski lewat retry atau fallback),
  itu WARNING. Jika alur itu gagal total dan harus dilaporkan sebagai
  kegagalan ke pemanggilnya, itu ERROR.
- **ERROR vs CRITICAL**: tanyakan "apakah proses LunaWave masih bisa
  melayani permintaan lain setelah ini?" Jika ya, itu ERROR. Jika tidak
  (atau nyaris tidak), itu CRITICAL.
- **DEBUG vs INFO**: tanyakan "apakah operator yang tidak sedang
  men-debug sesuatu perlu tahu ini terjadi?" Jika tidak, itu DEBUG.

---

## 4. Category Standard

Kategori mengelompokkan log berdasarkan **domain kejadian**, bukan
berdasarkan file atau modul Python tempat log itu ditulis. Satu modul bisa
menghasilkan log dari beberapa kategori berbeda tergantung apa yang sedang
terjadi. Kategori adalah sebuah structured field (`category`), bukan bagian
dari pesan.

| Kategori | Cakupan |
|---|---|
| `lifecycle` | Startup, shutdown, sesi proses dimulai/berakhir, health check periodik, penggunaan resource (memori) |
| `session` | Koneksi WebSocket connect/disconnect, durasi sesi klien |
| `auth` | Autentikasi, verifikasi token sesi, rate-limit login, setup admin awal |
| `command` | Eksekusi command lewat Command Bus — masuk, sukses, ditolak, gagal |
| `event` | Publikasi domain event lewat Event Bus |
| `playback` | Kontrol pemutaran: load track, pause/resume, seek, next/prev, crossfade, loudness, IPC ke MPV |
| `queue` | Perubahan antrean: tambah, hapus, reorder, select |
| `radio` | Siklus mode radio: pemilihan artis, filtering kandidat, prefetch lagu berikutnya |
| `download` | Alur download MP3: mulai, progres, selesai, gagal |
| `resolve` | Resolusi stream URL (cache hit/miss, pemanggilan yt-dlp) |
| `cache` | Baca/tulis/eviksi cache stream dan cache lain yang berumur pendek |
| `persistence` | Operasi database SQLite: query, migrasi, integritas data |
| `external` | Interaksi dengan sistem eksternal di luar kategori lain — SponsorBlock API, lyrics provider |
| `security` | Kejadian yang secara eksplisit berkaitan dengan postur keamanan, bukan hanya login — mis. penolakan CSWSH, deteksi anomali rate-limit |
| `system` | Kondisi lingkungan runtime: wake-lock, notifikasi platform, sinyal OS |

Panduan memilih kategori: pilih berdasarkan **apa domainnya**, bukan
**di file mana kode itu berjalan**. Contoh: kegagalan resolve stream yang
terjadi *di dalam* alur radio tetap berkategori `resolve` (karena itu jenis
kejadiannya), bukan `radio` — korelasi ke sesi radio dilakukan lewat field
korelasi (§5), bukan lewat kategori.

Kategori adalah daftar tertutup yang sengaja pendek. Penambahan kategori
baru harus jarang dan hanya ketika sebuah domain kejadian benar-benar tidak
tercakup oleh daftar di atas — bukan setiap kali ada modul baru.

---

## 5. Structured Field Standard

Setiap baris log adalah satu event terstruktur berisi field wajib dan field
kontekstual opsional. Field kontekstual **hanya** disertakan bila relevan
dengan kejadian tersebut — jangan memaksakan field yang nilainya kosong.

### 5.1 Field Wajib (setiap baris log, tanpa kecuali)

| Field | Deskripsi |
|---|---|
| `timestamp` | Waktu kejadian |
| `level` | Salah satu dari lima severity di §3 |
| `category` | Salah satu dari daftar di §4 |
| `event` | Message key ringkas dalam format baku — lihat §6 |
| `component` | Modul/komponen logis yang menerbitkan log (mis. `playback.controller`, `radio.engine`, `ws.auth`) — identitas sumber, independen dari kategori |

### 5.2 Field Korelasi (wajib bila konteksnya tersedia)

Karena LunaWave sangat asynchronous, field korelasi adalah yang paling
penting untuk merekonstruksi satu alur dari campuran log task-task
konkuren.

| Field | Deskripsi |
|---|---|
| `session_id` | Identitas sesi WebSocket/klien — konsisten dari connect sampai disconnect |
| `request_id` | Identitas satu eksekusi command atau satu request HTTP — dibuat baru setiap eksekusi |
| `correlation_id` | Identitas satu alur logis yang melintasi banyak task async terpisah (mis. satu siklus radio: pilih artis → cari → filter → prefetch), dipakai ketika `request_id` tunggal tidak cukup karena alurnya menyeberang beberapa task terjadwal |

Aturan: begitu sebuah `session_id`/`request_id`/`correlation_id` dibuat di
titik masuk sebuah alur, field itu **wajib** dibawa ke setiap log yang
diterbitkan sepanjang alur tersebut — termasuk oleh task background yang
dijadwalkan oleh alur itu (mis. prefetch yang dipicu radio, progress hook
download yang berjalan di executor terpisah).

### 5.3 Field Kontekstual (sesuai domain kejadian)

Field-field berikut disertakan hanya ketika relevan dengan kategori
kejadiannya:

| Field | Dipakai pada kategori | Deskripsi |
|---|---|---|
| `video_id` | `playback`, `resolve`, `download`, `queue`, `radio` | Identitas track YouTube yang menjadi subjek kejadian |
| `command_name` | `command` | Konstanta command (mis. `cmd.play.track`) |
| `event_type` | `event` | Nama tipe domain event (mis. `TrackStartedEvent`) |
| `artist` | `radio` | Artis yang sedang diproses siklus radio |
| `duration_ms` | Semua kategori yang mengukur operasi berbatas waktu (resolve, query DB, panggilan MPV, download) | Lama eksekusi operasi dalam milidetik |
| `retry_count` | Kejadian yang melibatkan percobaan ulang | Berapa kali retry sudah dilakukan sejauh ini |
| `error_type` | `ERROR`/`CRITICAL` | Nama exception domain (mis. `VideoUnavailableError`, `BotCheckError`, `RateLimitedError`) — gunakan hierarki exception domain yang ada, bukan nama exception generik Python |
| `reason` | Kejadian yang punya sebab eksplisit dan bermakna (track berhenti, sesi ditolak, koneksi terputus) | Penjelasan sebab dalam bentuk kode singkat, bukan kalimat bebas |
| `client_ip` | `auth`, `security` | Alamat IP klien — dicatat apa adanya, hanya untuk kategori yang memang berbasis IP (rate-limit login), tidak ditambahkan ke kategori lain tanpa alasan |
| `bytes` / `pct` | `download`, `cache` | Ukuran data atau persentase progres |

Field kontekstual di atas adalah contoh representatif dari domain yang ada
saat ini, bukan daftar tertutup — tapi penambahan field baru harus
mengikuti pola yang sama: nama singkat, `snake_case`, satu makna yang jelas,
dan nilai yang machine-parseable (bukan kalimat).

### 5.4 Larangan Field

- Tidak ada field bebas bernama generik seperti `data`, `info`, `extra`,
  atau `details` berisi blob tak terstruktur. Jika sebuah nilai penting
  untuk dicatat, ia layak punya nama field sendiri.
- Tidak ada field yang isinya objek besar (seluruh `AppState`, seluruh
  payload track list). Log mencatat *fakta tentang* kejadian, bukan
  snapshot lengkap state.

---

## 6. Message Convention

`event` (field wajib di §5.1) adalah **key**, bukan kalimat naratif.

**Format:** `snake_case`, Bahasa Inggris, pola `subjek_kejadian` atau
`subjek_aksi_hasil` — deskriptif, ringkas, dan stabil (tidak berubah antar
eksekusi untuk kejadian yang sama).

Contoh yang benar:
```
event: "track_load_started"
event: "track_load_succeeded"
event: "track_load_failed"
event: "radio_artist_selected"
event: "download_progress"
event: "auth_login_rejected"
event: "mpv_reconnected"
```

Contoh yang salah dan alasannya:

| Salah | Kenapa Salah |
|---|---|
| `"Track abc123 berhasil dimuat dalam 240ms"` | Nilai dinamis (video_id, durasi) tercampur ke dalam kalimat — harus jadi field terpisah (`video_id`, `duration_ms`), `event` cukup `"track_load_succeeded"` |
| `"Error!"` | Tidak deskriptif, tidak stabil sebagai key, tidak bisa dibedakan dari error lain saat di-grep |
| `"handle_play_track dipanggil"` | Menyebut nama fungsi Python — ini implementasi, bukan kejadian domain (lihat prinsip §2.2) |
| `"track_load_failed_for_video_abc123_after_3_retries"` | Nilai dinamis dijadikan bagian dari key — key harus stabil terlepas dari video_id atau jumlah retry berapa pun |

**Kapan boleh pakai kalimat naratif:** hanya untuk log `lifecycle` yang
sifatnya deklaratif dan tidak berulang secara sering, seperti banner sesi
(mulai/berhenti proses) — bukan untuk kejadian domain yang berulang di
hot path.

**Bahasa:** `event` key selalu Bahasa Inggris (agar konsisten dengan nama
command, event class, dan field lain yang sudah berbahasa Inggris di
codebase). Narasi tambahan yang bersifat opsional untuk pembaca manusia
(lihat §9) boleh Bahasa Indonesia.

---

## 7. Kapan Logging Harus Digunakan

Logging **wajib** ada pada titik-titik berikut:

1. **Setiap kali eksekusi melewati boundary ke sistem eksternal** yang
   bisa gagal secara independen dari kode LunaWave sendiri — panggilan ke
   MPV lewat IPC, panggilan ke yt-dlp/YouTube, query SQLite, panggilan ke
   API pihak ketiga (SponsorBlock, lyrics). Baik pada awal (opsional,
   DEBUG) maupun pada hasil (WARNING/ERROR bila gagal, INFO/DEBUG bila
   sukses tergantung frekuensi).
2. **Titik masuk dan keluar alur bisnis utama** — command diterima,
   command selesai (sukses/gagal), event dipublikasikan, sesi WebSocket
   dibuka/ditutup, siklus radio dimulai/berakhir, download dimulai/selesai.
3. **Setiap exception yang ditangkap dan tidak diteruskan mentah-mentah**
   ke pemanggil — jika sebuah `except` blok menelan atau mengubah sebuah
   error, itu wajib dicatat pada titik itu juga, karena informasi tentang
   kegagalan itu akan hilang jika tidak.
4. **Perubahan state yang signifikan pada level aplikasi** — mode
   playback berubah, pengaturan yang memengaruhi audio berubah (loudness
   normalization, crossfade, output device), sesi admin dibuat.
5. **Kondisi retry, fallback, atau degradasi** — setiap kali sistem
   mengambil jalur alternatif karena jalur utama gagal (reconnect MPV,
   cache miss yang memicu resolve ulang, radio fallback karena artist
   selector kehabisan kandidat).
6. **Kejadian yang berkaitan dengan keamanan** — percobaan login (baik
   berhasil maupun gagal), token sesi dibuat/dicabut, rate-limit terpicu,
   penolakan koneksi WebSocket karena origin tidak valid (CSWSH).
7. **Lifecycle proses** — startup, shutdown (baik graceful maupun akibat
   sinyal), serta kondisi lingkungan runtime yang memengaruhi keandalan
   (wake-lock diperoleh/gagal, resource menipis).
8. **Task background/terjadwal** — setiap siklus task yang berjalan tanpa
   dipicu langsung oleh pengguna (radio prefetcher, download progress
   hook, health check periodik) wajib logging pada mulai dan selesainya
   siklus, agar operator bisa mendeteksi task yang diam-diam berhenti
   bekerja.

---

## 8. Kapan Logging Tidak Diperlukan

Logging **sebaiknya dihindari** pada titik-titik berikut, karena akan
menambah noise tanpa menambah nilai debug/observability:

1. **Logic domain murni yang sudah dites unit habis-habisan** di dalam
   `core/` — fungsi pure yang deterministik dan tidak menyentuh boundary
   eksternal tidak butuh logging pada operasi normalnya. Kegagalannya
   akan tertangkap sebagai exception yang naik ke lapisan yang memang
   sudah logging (lihat §7.3).
2. **Setiap iterasi loop atau setiap item dalam koleksi** — mis. jangan
   logging per-track saat memfilter ratusan kandidat radio. Log satu baris
   ringkasan hasil filter (jumlah masuk, jumlah lolos), bukan satu baris
   per kandidat. Detail per-item, jika benar-benar dibutuhkan untuk
   debugging aktif, adalah kandidat DEBUG dengan volume terbatas — bukan
   INFO.
3. **Kejadian yang frekuensinya sangat tinggi dan tidak menandakan
   perubahan state** — mis. `TrackProgressEvent` yang terbit setiap
   beberapa ratus milidetik saat playback berjalan normal. Progres posisi
   pemutaran tidak dicatat sebagai log per tick; ini murni data real-time
   untuk WebSocket broadcast ke frontend, bukan kejadian yang layak
   diaudit.
4. **State yang bisa direkonstruksi dari state lain yang sudah dicatat**
   — jangan logging ulang seluruh state aplikasi pada setiap perubahan
   kecil. Cukup log delta (apa yang berubah), bukan snapshot penuh
   berulang-ulang.
5. **Kegagalan yang sudah pasti akan dicatat lagi di lapisan atasnya**
   — jangan logging exception yang sama dua kali di dua lapisan pemanggil
   berbeda tanpa menambah informasi baru. Jika sebuah error diteruskan
   (re-raise) tanpa ditangani, cukup dicatat sekali di titik ia akhirnya
   ditangani atau di titik boundary asalnya — bukan di setiap lapisan
   yang dilewatinya.
6. **Getter/accessor sederhana dan operasi read-only berfrekuensi tinggi**
   yang tidak melewati boundary eksternal (mis. membaca in-memory queue
   untuk ditampilkan).

Prinsip pemandu: **setiap baris log harus punya alasan seseorang akan
mencarinya suatu hari nanti.** Jika tidak ada skenario debugging atau
audit yang akan membaca baris itu, jangan ditulis.

---

## 9. Human Readable Format

Format yang dibaca manusia (console/terminal serta saat file log dibuka
langsung oleh operator) harus bisa dipahami sekilas tanpa tooling.

Prinsip bentuk:

- Satu baris = satu kejadian, urut secara kronologis, tanpa terpotong
  atau meluber ke banyak baris (kecuali stack trace error).
- Bentuk dasar: `[waktu] LEVEL kategori.komponen: event_key (field=nilai, field=nilai, ...)`
- Field ditampilkan sebagai pasangan `key=value` yang mudah dipindai mata,
  bukan JSON mentah yang sulit dibaca cepat di layar 80 kolom.
- Level ditulis mencolok (huruf besar) agar bisa dipindai vertikal untuk
  menemukan WARNING/ERROR/CRITICAL di antara banyak baris INFO/DEBUG.
- Tidak ada informasi yang hilang dibanding bentuk machine-readable —
  bentuk human-readable dan machine-readable berasal dari struktur data
  yang sama, hanya dirender berbeda. Operator yang membaca file log tidak
  boleh kehilangan konteks dibanding yang dilihat sistem observability.
- Pesan error harus menyertakan cukup konteks untuk dipahami tanpa
  membuka kode sumber — nama exception domain dan `reason`, bukan hanya
  "gagal".

Bentuk human-readable ini **tidak** wajib berwarna atau interaktif — itu
adalah preferensi kenyamanan operator, bukan bagian dari kontrak standar
ini.

---

## 10. Machine Readable Format

Setiap baris log harus punya representasi terstruktur (field-value) yang
bisa diparse tanpa ambiguitas oleh tooling lain — baik oleh script
analisis, AI agent, maupun sistem observability masa depan.

Prinsip bentuk:

- Struktur data yang mendasari setiap baris log adalah **kumpulan
  field-value bertipe konsisten** (§5), bukan kalimat bebas yang perlu
  regex untuk diekstrak.
- Nama field selalu konsisten lintas seluruh aplikasi — field yang sama
  artinya harus selalu punya nama yang sama, di kategori manapun ia
  muncul (mis. `duration_ms` selalu berarti hal yang sama, tidak pernah
  `durasi_ms` di satu tempat dan `duration_ms` di tempat lain).
- Tipe nilai per field selalu konsisten (angka tetap angka, bukan kadang
  string kadang angka) sehingga agregasi (rata-rata durasi, hitung
  frekuensi error per tipe) bisa dilakukan langsung tanpa normalisasi
  manual.
- Setiap baris log berdiri sendiri secara semantik — bisa dipahami dan
  diproses tanpa harus membaca baris sebelum/sesudahnya, karena field
  korelasi (§5.2) sudah menyediakan cara menyatukannya kembali jika
  dibutuhkan.
- Format ini adalah kontrak yang stabil: field yang sudah ada tidak
  diganti nama atau makna tanpa pertimbangan breaking-change, karena
  tooling di masa depan (dashboard, alert rule, query observability) akan
  bergantung padanya.

---

## 11. Best Practices

1. **Tetapkan `session_id`/`request_id`/`correlation_id` sedini mungkin**
   di titik masuk sebuah alur (koneksi WebSocket dibuka, command diterima,
   siklus radio dimulai), lalu teruskan secara eksplisit ke semua fungsi
   dan task turunannya — termasuk task async yang dijadwalkan terpisah.
2. **Gunakan hierarki exception domain yang sudah ada** (`YtPlayerError`
   dan turunannya seperti `VideoUnavailableError`, `BotCheckError`,
   `RateLimitedError`) sebagai nilai `error_type`, bukan nama exception
   generik Python (`Exception`, `ValueError`) — hierarki domain sudah
   membawa makna tentang *mengapa* sesuatu gagal dan *apakah retry masuk
   akal*, dan log sebaiknya mewariskan makna itu.
3. **Catat hasil, bukan proses internal**, untuk operasi yang sudah
   tervalidasi lewat test — log yang baik menjawab "apa yang terjadi dan
   apa akibatnya", bukan menjelaskan ulang bagaimana algoritmanya bekerja.
4. **Log sekali per kejadian pada level yang tepat**, bukan log peringatan
   dini plus log error final untuk kegagalan yang sama — pilih satu titik
   yang paling informatif (biasanya titik final, dengan `retry_count` jika
   relevan) dan diamkan yang lain.
5. **Ringkas operasi bervolume tinggi menjadi satu baris agregat** —
   siklus filter radio, batch resolve, atau loop retry sebaiknya
   menghasilkan satu baris ringkasan (jumlah diproses, jumlah gagal,
   durasi total) alih-alih satu baris per unit kerja.
6. **Perlakukan log sebagai bagian dari behavior yang stabil**, sejajar
   dengan kontrak command dan event — mengubah field/kategori/level pada
   log yang sudah dipakai tooling observability adalah keputusan yang
   harus disengaja, bukan efek samping refactor.
7. **Pastikan log tetap berguna meski file log dirotasi atau terpotong**
   — jangan bergantung pada baris sebelumnya dalam file yang sama untuk
   memberi makna pada satu baris log (lihat §10, "berdiri sendiri secara
   semantik").
8. **Untuk task background/terjadwal, log kondisi diam yang tidak wajar**
   — jika sebuah loop yang seharusnya terus berjalan (mpv observer,
   radio prefetcher) berhenti tanpa sinyal shutdown yang eksplisit,
   itu adalah kejadian ERROR/CRITICAL yang wajib dicatat, bukan sekadar
   loop yang selesai secara diam-diam.

---

## 12. Anti Patterns

Pola-pola berikut secara eksplisit **dilarang** di seluruh codebase:

1. **Rahasia di log, level apa pun.** Password (plaintext maupun hash),
   token sesi mentah, salt, atau kredensial apa pun tidak boleh muncul di
   log sama sekali — termasuk di DEBUG. Jika sebuah token perlu
   direferensikan di log untuk korelasi, gunakan identitas yang sudah
   dihash/dipotong (mis. beberapa karakter awal dari hash-nya), tidak
   pernah nilai mentah.
2. **String interpolation ke dalam pesan.** Menyisipkan nilai dinamis
   langsung ke dalam kalimat pesan (`f"Track {video_id} gagal"`) alih-alih
   menjadikannya field terpisah — ini melanggar §2.3 dan §6, membuat
   pesan tidak konsisten dan sulit diagregasi.
3. **Level yang salah kaprah untuk menarik perhatian.** Menaikkan level
   sebuah log ke ERROR/CRITICAL padahal secara definisi §3 ia adalah
   WARNING (kondisi tertangani), hanya supaya "lebih terlihat" di
   terminal. Ini merusak makna severity sebagai kontrak dan membuat
   operator kebal terhadap ERROR/CRITICAL yang sungguhan (alert fatigue).
4. **Log-and-swallow tanpa konteks.** Menangkap exception, mencatat
   `"terjadi error"` tanpa `error_type`, tanpa konteks apa yang sedang
   dikerjakan, lalu melanjutkan seolah tidak terjadi apa-apa — baris log
   seperti ini tidak actionable dan tidak bisa dikorelasikan ke apa pun.
5. **Duplikasi log yang sama di banyak lapisan.** Mencatat exception yang
   sama, dengan pesan yang sama, di setiap fungsi pemanggil sepanjang call
   stack — ini melipatgandakan volume log tanpa menambah informasi (lihat
   §8.5).
6. **Snapshot state penuh sebagai log.** Men-dump seluruh `AppState`,
   seluruh isi antrean, atau payload besar lain ke dalam satu field log
   "untuk jaga-jaga" — ini melanggar §5.4 dan membuat log sulit dibaca
   maupun diproses secara efisien.
7. **Kategori/level dipilih berdasarkan file, bukan kejadian.** Menyamakan
   kategori log dengan nama modul Python tempat kode itu berada (mis.
   semua log di `engine/radio/` otomatis berkategori `radio` walau
   sebenarnya mendeskripsikan kegagalan resolve) — lihat §4, kategori
   mengikuti domain kejadian, bukan lokasi file.
8. **Logging di dalam hot loop bervolume tinggi tanpa agregasi** — logging
   per-tick progress, per-item filter, atau per-iterasi loop retry cepat
   yang bisa berjalan puluhan/ratusan kali per detik, membanjiri file log
   dan menyulitkan device beresource terbatas (lihat §8.2–8.3).
9. **Membuat correlation id baru di tengah alur yang sudah punya satu.**
   Setiap task turunan dari sebuah alur (prefetch yang dipicu radio, hook
   progress dari download) wajib mewarisi `session_id`/`request_id`/
   `correlation_id` yang sudah ada, bukan membuat identitas baru yang
   memutus keterhubungan alur (lihat §5.2 dan Best Practice #1).
10. **Pesan event yang tidak stabil.** Menyisipkan nilai dinamis ke dalam
    `event` key itu sendiri (lihat contoh salah di §6) sehingga kejadian
    yang secara semantik sama menghasilkan key yang berbeda-beda setiap
    kali — ini merusak kemampuan grep/agregasi yang menjadi alasan utama
    standar machine-readable ini ada.

---

## Ringkasan Kontrak

Setiap baris log LunaWave, tanpa kecuali, harus bisa menjawab lima
pertanyaan berikut hanya dari isinya sendiri:

1. **Kapan** ini terjadi? → `timestamp`
2. **Seberapa serius**? → `level` (§3)
3. **Domain apa**? → `category` (§4)
4. **Apa yang terjadi**, secara stabil dan bisa dicari? → `event` (§6)
5. **Bagian mana dari sistem yang menerbitkannya**, dan **bisakah
   dikaitkan ke alur yang lebih besar**? → `component` + field korelasi
   (§5)

Jika sebuah baris log tidak bisa menjawab kelima pertanyaan ini, ia belum
memenuhi standar ini.
