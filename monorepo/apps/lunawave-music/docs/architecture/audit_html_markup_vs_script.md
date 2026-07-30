# Audit Rasio Markup vs Script/Template (Temuan M)

Dokumen ini merangkum hasil audit formal terkait rasio markup HTML natural versus script dan template pada tiga halaman utama aplikasi sesuai instruksi di `04_fase4_html_audit.yaml` (Temuan M, Fase 4).

## Hasil Audit

### 1. `web/static/pages/app/index.html`
- **Total Baris**: 898
- **Baris Markup**: 856
- **Baris Script (inline)**: 42
- **Baris Template**: 0
- **Daftar Class berulang (>= 4x)**:
  - `ti`: 47
  - `ss-row`: 26
  - `ss-label-text`: 25
  - `ss-label-sub`: 25
  - `star`: 14
  - `ss-label`: 14
  - `eq-bar`: 10
  - `tick`: 9
  - `skeleton-box`: 9
  - `section-label-row`: 8
  - `label-text`: 8
  - `hashtag-pill`: 6
  - `login-input-group`: 5
  - `settings-sheet`: 5
  - `ss-handle`: 5
  - `ss-action-btn`: 5
  - `tab-panel`: 4
  - `label-sub`: 4
  - `nav-btn`: 4
  - `ss-title`: 4
  - `ti-chevron-right`: 4
  - `ss-out-btn`: 4

### 2. `web/static/pages/client/client.html`
- **Total Baris**: 290
- **Baris Markup**: 264
- **Baris Script (inline)**: 26
- **Baris Template**: 0
- **Daftar Class berulang (>= 4x)**:
  - `eq-bar`: 10
  - `ti`: 9

### 3. `web/static/pages/admin-logs/admin-logs.html`
- **Total Baris**: 1074
- **Baris Markup**: 1074
- **Baris Script (inline)**: 0
- **Baris Template**: 0
- **Daftar Class berulang (>= 4x)**:
  - `ti`: 17
  - `status-item`: 5
  - `tab-btn`: 4
  - `tab-content`: 4

## Kesimpulan & Keputusan (M.3)

Berdasarkan hasil audit di atas:
1. Markup natural mendominasi ukuran ketiga halaman.
2. Tidak ditemukan blok HTML yang terduplikasi secara berulang secara manual untuk satu komponen yang sama dalam jumlah yang masif (seperti kartu track yang dirender puluhan kali di HTML). Class dengan frekuensi tinggi seperti `ti` adalah utility untuk ikon, dan `ss-row`, `ss-label-text` adalah elemen dalam form layout (Settings Sheet) yang isinya memang berbeda-beda.
3. Ukuran HTML tersebut sangat wajar mengingat kompleksitas halaman SPA ini yang memuat berbagai bagian UI (home, discover, queue, settings) di `index.html`, sedangkan data utamanya dirender secara dinamis melalui JavaScript, bukan disalin manual di markup.

**Keputusan Akhir (Task M.3)**: Componentize HTML dengan tag `<template>` **TIDAK DIPERLUKAN**. Temuan M ditutup sampai di sini tanpa ada pemindahan elemen HTML menjadi komponen terpisah.
