# Prompt Eksekusi — Redesign Entrypoint & Dashboard Logging (LunaWave)

> Salin seluruh isi file ini sebagai prompt awal ke AI coding agent kamu
> (Claude Code, atau agent lain yang punya akses baca/tulis ke repo ini).
> Prompt ini murni instruksi "cara mengeksekusi", bukan bagian dari
> proposal/rencana itu sendiri — desainnya sudah final di dua dokumen
> sumber di bawah.

---

## 1. Peran kamu

Kamu adalah AI coding agent yang mengeksekusi migrasi
**`entrypoint_dashboard_redesign`** pada repo LunaWave, mengikuti task
breakdown yang sudah final. Kamu TIDAK mengambil keputusan desain baru —
semua keputusan (autentikasi dashboard, strategi live-tail, format
parser log, pola registrasi route) sudah diputuskan dan didokumentasikan.
Tugasmu murni eksekusi disiplin, sesi demi sesi, task demi task.

## 2. Dokumen sumber — WAJIB dibaca sebelum menyentuh kode apa pun

Baca dalam urutan ini, penuh, sebelum mulai:

1. `docs/rfc/redesign_logging/proposal_redesign_logging.md` — konteks
   kenapa fitur ini dibuat, kondisi sistem saat ini vs yang diusulkan.
2. `docs/rfc/redesign_logging/task_breakdown_logging_redesign.yaml` —
   rencana eksekusi konkret (ini yang kamu jalankan). Baca terutama:
   - komentar header (aturan eksekusi 1-10)
   - blok `meta` (file locked/caution, pola autentikasi dashboard)
   - blok `decisions` (R-D1 s/d R-D5 — kenapa desainnya begini)
   - blok `sessions` dan `tasks`
   - `execution_order` di akhir file
3. `AI_CONTEXT.md` — konfirmasi ulang file yang tidak boleh disentuh
   tanpa izin (`server/handlers/websocket.py`, `web/static/index.html`)
   dan batasan teknis lain yang berlaku untuk seluruh repo, bukan cuma
   fitur ini.
4. `docs/PATCHLOG.md` — baca frontmatter `latest_patch_id` untuk nomor
   patch berikutnya, dan 2-3 entry terakhir untuk konteks sprint aktif.

Jangan mulai task R0.1 sebelum keempat dokumen ini benar-benar terbaca.

## 3. Cara mengeksekusi

1. Jalankan task **persis** sesuai urutan di `execution_order` pada
   `task_breakdown_logging_redesign.yaml`. Jangan melompati sesi.
2. Task dalam satu `session` dengan `parallel_ok: true` boleh
   dikerjakan tidak berurutan relatif satu sama lain (asal `depends_on`
   sudah terpenuhi). Task di sesi dengan `parallel_ok: false`
   ("dedicated") WAJIB dikerjakan satu-satu, berurutan, tanpa
   menyisipkan task dari sesi lain.
3. Untuk setiap task:
   a. Baca field `files`, `steps`, `depends_on` milik task itu.
   b. Kerjakan `steps` sesuai yang tertulis — jangan menambah scope di
      luar `steps` (prinsip non-breaking per commit, aturan eksekusi #8).
   c. Jalankan semua `post_commands` milik task itu (jika ada).
   d. Verifikasi setiap butir di `dod` benar-benar terpenuhi sebelum
      menandai task selesai.
   e. Prepend satu entry baru ke `docs/PATCHLOG.md` dengan ID format
      `PATCH-YYYY-MM-DD-NNN` (cek `latest_patch_id` di frontmatter
      SEBELUM menulis, jangan menebak nomor) — KECUALI task punya
      `patchlog: skip`. Untuk task bertanda `patchlog_group`, gabung
      jadi SATU entry untuk seluruh anggota grup tsb, ditulis setelah
      task terakhir dalam grup itu selesai.
4. **Berhenti dan tunggu konfirmasi eksplisit dari saya** sebelum
   mengerjakan task apa pun yang bertanda `requires_human_confirmation:
   true` (saat ini: **R6.2**, menyentuh `server/handlers/websocket.py`
   yang berstatus locked di `AI_CONTEXT.md`). Jangan lanjut sendiri
   walau task sebelumnya lancar — tanyakan dulu, tampilkan diff yang
   akan dibuat, baru eksekusi setelah saya bilang "lanjut".
5. Untuk task dengan prefix file `CAUTION:` (mis. `main.py`,
   `server/app.py`, `server/connection_manager.py`), tetap boleh
   dikerjakan tanpa berhenti, tapi lakukan dengan perubahan **minimal
   dan aditif** — jangan menata ulang kode yang tidak relevan dengan
   task tsb, dan tunjukkan diff sebelum commit supaya saya bisa
   sekali lihat.
6. Setelah setiap **sesi** (bukan setiap task) selesai, berikan saya
   ringkasan singkat: task apa saja yang selesai, hasil `post_commands`
   penting, dan apakah ada `dod` yang gagal/perlu perhatian — sebelum
   lanjut ke sesi berikutnya.

## 4. Batasan yang tidak boleh dilanggar (ulangi dari sumber, agar tidak lupa)

- Jangan mengubah taksonomi 15 kategori di `core/log_categories.py` atau
  format `file_renderer()`/`lunawave.log` — fitur ini murni lapisan
  penyajian di atas logging yang sudah ada.
- Jangan menambah dependency Python/JS baru, jangan menambah env var
  baru. Dashboard dan `/api/logs/*` reuse proteksi `X-Metrics-Token`
  yang sudah dipakai `/metrics` (localhost atau token,
  `secrets.compare_digest`) — bukan sistem auth baru.
- `server/handlers/websocket.py`: hanya boleh MENAMBAH satu import dan
  satu percabangan dispatch baru (task R6.2). Tidak ada refactor lain
  di file itu, titik.
- `web/static/index.html`: tidak disentuh sama sekali oleh fitur ini.
- Jalankan `python automation/doctor.py` (atau `--strict --json` sesuai
  task) setelah setiap task yang mengubah kode Python, dan pastikan
  tidak ada error baru dibanding baseline sebelum fitur ini dimulai.

## 5. Titik mulai

Mulai dari task **R0.1** (orientasi) di
`task_breakdown_logging_redesign.yaml`. Setelah selesai membaca dan
menjalankan `post_commands` R0.1, laporkan temuan owner/dependency file
secara singkat ke saya sebelum masuk ke Sesi 1 (R1.1, R1.2).

## 6. Format laporan yang saya harapkan tiap sesi selesai

```
## Sesi <N> selesai — <label sesi>
Task selesai: <id, id, ...>
DoD: <semua terpenuhi / ada yang gagal — sebutkan>
post_commands penting: <ringkasan hasil, mis. doctor.py: 0 error baru>
Patch log: <PATCH-ID yang ditulis, atau "digabung, menunggu grup selesai">
Siap lanjut ke Sesi <N+1>? (tunggu konfirmasi bila sesi berikutnya
berisi task requires_human_confirmation)
```

---

*Prompt ini adalah instruksi eksekusi, bukan pengganti isi
`task_breakdown_logging_redesign.yaml` — bila ada perbedaan antara
prompt ini dan file YAML, file YAML yang menjadi acuan utama.*
