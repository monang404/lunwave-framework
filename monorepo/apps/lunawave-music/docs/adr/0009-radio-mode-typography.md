# ADR-0009: Tipografi Radio Mode Menggunakan Font Eksternal

**Status:** Accepted
**Date:** 2026-07-22

---

## Konteks

LunaWave mengadopsi prinsip desain *offline-first* dan dioptimasi untuk berjalan di lingkungan Termux. Secara bawaan, seluruh antarmuka aplikasi menggunakan font standar (`--font`) demi efisiensi ukuran, memori, dan konsistensi lintas perangkat. Namun, pada pengembangan fitur "Radio Mode", muncul kebutuhan editorial untuk memberikan kesan visual yang khas dan lebih premium. Timbul perdebatan apakah Radio Mode harus dipaksa mematuhi keseragaman font bawaan, atau diizinkan menggunakan font eksternal yang lebih dekoratif (seperti Fraunces dan Space Grotesk).

## Keputusan

Radio Mode **diperbolehkan** menggunakan font eksternal (Fraunces dan Space Grotesk) untuk menciptakan identitas visual yang khas. Namun, penggunaannya dikunci dengan syarat ketat:
1. Font **wajib di-self-host** (tidak boleh ada *request* jaringan ke CDN eksternal seperti Google Fonts).
2. Font wajib di-*subset* agar ukuran keseluruhan aset tetap ringan (<150KB).
3. Berkas lisensi font (`LICENSE.md`) harus disertakan di dalam *repository* pada direktori masing-masing.

Hal ini secara resmi mengukuhkan keputusan yang sebelumnya disetujui dalam fase perancangan `docs/rfc/radio_toggle/` menjadi ketetapan arsitektur.

## Alasan

Radio Mode didesain sebagai pengalaman imersif (*editorial moment*) yang terpisah dari *player* standar. Tipografi yang berbeda menegaskan mode pemutaran pasif dan otomatis ini. Awalnya ada usulan membatalkan tipografi ini guna menekan ukuran dan latensi (sesuai kaidah *offline-first*). Akan tetapi, dengan melakukan *self-hosting* plus *subsetting*, aplikasi tetap dapat berjalan murni secara *offline* tanpa hambatan privasi maupun performa pemuatan eksternal.

## Konsekuensi

- Terdapat direktori statis untuk memuat font di `web/static/fonts/fraunces/` dan `web/static/fonts/space-grotesk/`.
- Dilarang keras menggunakan ekstensi atau `@import` yang memanggil *domain third-party* di dalam *stylesheet*.
- Hal ini merupakan bentuk fleksibilitas bersyarat, namun tidak bisa dijadikan alasan bebas untuk setiap komponen UI baru membawa font eksternal lainnya di masa depan.

## Referensi

- Dokumen RFC: `docs/rfc/radio_toggle/radio_toggle.md` (§5.5)
- Rencana Kerja: `docs/rfc/radio_toggle/task_breakdown_radio.yaml` (Task R1.1)
- Referensi Implementasi: `web/static/css/components/radio-hero.css`
