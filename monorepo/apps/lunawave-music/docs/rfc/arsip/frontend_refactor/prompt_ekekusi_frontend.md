Eksekusi task_breakdown_frontend_tooling.yaml (frontend tooling & restructure).

Sumber dokumen (baca SEMUA sebelum mulai, urutan ini):
1. AI_CONTEXT.md — aturan governance & file locked
2. docs/rfc/frontend_refactor/proposal_frontend_tooling.md — RFC/latar belakang
3. docs/rfc/frontend_refactor/0011-frontend-tooling-governance.md — keputusan final (ADR)
4. docs/rfc/frontend_refactor/audit_dan_visi_struktur_web.md — peta struktur as-is/to-be
5. docs/rfc/frontend_refactor/task_breakdown_frontend_tooling.yaml — rencana eksekusi (SUMBER UTAMA task)

Sebelum mulai:
- Baca docs/STATUS.md dan 2-3 entri terakhir docs/PATCHLOG.md untuk konteks sprint aktif
- Konfirmasi web/static/index.html masih ada di daftar locked AI_CONTEXT.md
- Jalankan automation/find_owner.py untuk file-file kunci yang disebut di file_manifest task_breakdown

Aturan eksekusi (WAJIB, ikuti persis):
- Kerjakan sesi sesuai urutan di blok `execution_order` — JANGAN melompati sesi
- Sesi dengan parallel_ok: false dikerjakan sendirian, tidak dicampur task sesi lain
- Task dengan locked: true (semua di sesi 8) TIDAK BOLEH dieksekusi tanpa berhenti dulu
- Task F8.1 secara eksplisit mengharuskan kamu STOP dan menunggu approval tertulis dariku sebelum lanjut ke F8.2 — jangan asumsikan approval, tanya dulu
- Setiap file yang dipindah wajib backward-compat alias sampai semua caller ikut pindah
- Setelah tiap task: jalankan post_commands miliknya, cek semua dod true, baru lanjut task berikutnya
- Setelah tiap sesi selesai: jalankan automation/doctor.py, lalu catat entry docs/PATCHLOG.md via automation/patchlog.py add (ikuti patchlog_group kalau ada), update docs/STATUS.md jika kondisi file berubah
- Kalau ketemu keadaan yang tidak sesuai asumsi task_breakdown (misal file sudah berubah sejak ditulis) — STOP, laporkan, jangan improvisasi sendiri

Mulai dari sesi 1 (F1.1). Laporkan ringkasan tiap sesi selesai sebelum lanjut ke sesi berikutnya.
