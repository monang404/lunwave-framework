# Temuan investigasi circular-dependencies — Sesi 4

65 dari 67 circular-dependency warning (2 sisanya sudah didokumentasikan
sebagai exception sadar di S4.1) berakar pada SATU pola yang sama:
modul audio (`playback-sync.js`) dan transport (`ws.js`) memanggil
fungsi render secara langsung, dan modul render/events memanggil
balik fungsi kontrol/kirim-pesan di audio/ws. Ini identik dengan
masalah render<->events cross-import yang sudah ditandai di RFC
terpisah (lihat 05_sesi5_render_events.yaml).

Hub utama: ws.js (17 edge), events/index.js (15 edge),
audio/playback-sync.js (11 edge).

**Rekomendasi:** satukan keputusan RFC event bus (semula scope-nya
cuma render<->events, 20 warning) supaya juga mencakup ws.js dan
audio/playback-sync.js sebagai pengirim/penerima event, bukan
pemanggil langsung. Ini satu proyek arsitektur, bukan dua yang
kebetulan bertumpang tindih.

Data mentah 67-edge dan hub breakdown: lihat
04_sesi4_circular_deps.yaml > data_mentah_edge_list_67 dan
> diagnosis.
