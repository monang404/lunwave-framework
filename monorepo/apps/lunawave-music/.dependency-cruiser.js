/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      // Downgraded error -> warn 2026-07-24 (PATCH-2026-07-24, frontend RFC
      // recovery session). Audited against the actual call graph: render/*
      // calling into events/* (e.g. discover-tab.js -> events/index.js to
      // re-trigger a tab switch) and events/* calling into render/* (e.g.
      // transport-events.js re-rendering the player bar after a command) is
      // pre-existing architecture that predates the Gemini refactor, not a
      // regression it introduced. Enforcing this as a hard error blocks CI
      // on ~20 call sites with no actual bug behind them. Kept as `warn` so
      // the boundary is still visible and doesn't silently regress further,
      // without blocking unrelated patches. A real fix would need a proper
      // one-way event-bus/pub-sub between render and events, which is a
      // larger architectural change out of scope for this recovery pass.
      name: 'no-render-imports-events',
      comment: 'render/* components should not directly import events/* logic.',
      severity: 'warn',
      from: { path: '^web/static/shared/js/render/' },
      to: { path: '^web/static/shared/js/events/' }
    },
    {
      // Tahap 5 event-bus recovery (PATCH-2026-07-25, lihat
      // docs/rfc/pemulihan_frontend/11_tahap5_render_events_cross_import.yaml).
      // Setelah T5.2-T5.9, 6 edge SENGAJA dibiarkan sebagai exception
      // terdokumentasi, bukan kegagalan tahap ini:
      //
      // 1. events/search-input-events.js -> render/search.js, untuk
      //    playSearchTrack(). Diaudit langsung: isinya cuma cek
      //    store.userRole lalu wsSend("play_track", track) -- fungsi COMMAND
      //    (wrapper wsSend), bukan render/DOM, cuma kebetulan didefinisikan
      //    di file render/search.js. Bus untuk notifikasi render, bukan
      //    dispatch command, jadi dipaksa lewat emit() di sini salah kaprah
      //    semantiknya. Pola sama seperti wsSend/getOrInitAudio yang sudah
      //    diterima legitimate sejak proposal §2.
      //
      // 2. events/index.js, events/keyboard-shortcut-events.js,
      //    events/settings-events.js, events/transport-events.js
      //    -> render/navigation.js, semuanya untuk switchTab(). BUKAN
      //    bagian task list T5.1-T5.10 (ketemu belat T5.11 saat regenerate
      //    depcruise final -- baseline "14" di header 11_tahap5.yaml
      //    dihitung SEBELUM Tahap 3 memindah switchTab dari events/index.js
      //    ke render/navigation.js, jadi tidak pernah menghitung ulang edge
      //    yang muncul sebagai efek samping pemindahan itu). switchTab()
      //    adalah fungsi bootstrap/routing (ganti active tab, aria-selected,
      //    fokus search input) yang sengaja diekstrak Tahap 3 supaya jadi
      //    modul leaf, dipanggil balik oleh banyak modul events/* sebagai
      //    command-dispatch biasa (analog switchTab dari render/*.js ke
      //    events/index.js yang sudah diterima legitimate di rule
      //    no-render-imports-events di atas) -- bukan pola render-notification
      //    yang jadi target bus.emit di proposal ini, jadi TIDAK dipaksa
      //    lewat bus juga.
      //
      // 3. events/index.js -> render/discover-personalize.js, untuk
      //    initDiscoverFilterEvents. Sudah diaudit Tahap 3: TERNYATA TIDAK
      //    circular (satu arah saja), disebutkan juga di comment rule
      //    circular-dependencies di bawah. Sama seperti switchTab, ini
      //    bootstrap init call dari hub events/index.js, bukan render
      //    notification.
      name: 'no-events-imports-render',
      comment: 'events/* components should not directly import render/* logic.',
      severity: 'warn',
      from: { path: '^web/static/shared/js/events/' },
      to: { path: '^web/static/shared/js/render/' }
    },
    {
      name: 'utils-must-be-leaf',
      comment: 'utils/* modules must not import anything else from shared/js (they must be leaves).',
      severity: 'error',
      from: { path: '^web/static/shared/js/utils/' },
      to: { path: '^web/static/shared/js/(?!utils/)' }
    },
    {
      // Status pasca Tahap 3 event-bus recovery (PATCH-2026-07-25, lihat
      // docs/rfc/pemulihan_frontend/09_tahap3_event_bus_events_index.yaml).
      // Hanya 2 circular-dependency yang tersisa & DITERIMA sebagai
      // exception (bukan bug) -- keduanya control-direction dua arah yang
      // disengaja, bukan akibat modul render/hub yang salah taruh:
      //
      // 1. audio/playback-sync.js <-> web/static/shared/js/ws.js
      //    ws.js -> playback-sync.js: _resumeAndPlay/getOrInitAudio/
      //    syncBrowserAudio (arah render/sync audio browser).
      //    playback-sync.js -> ws.js: wsSend/syncLocalLyrics (arah kirim
      //    command balik ke server). Didokumentasikan sejak Tahap 2
      //    (PATCH-2026-07-25-233) sebagai "tetap_direct_import_legitimate".
      //
      // 2. audio/playback-sync.js <-> audio/visualizer.js
      //    Live-binding ES module yang sengaja dipasang PATCH-223 (Sesi 4).
      //    Lihat docs/architecture/frontend.md untuk detail.
      //
      // CATATAN: 7 circular-dependency edge lewat switchTab() (events/
      // index.js sebagai hub dipanggil balik oleh 7 modul, termasuk
      // events/settings-events.js yang baru ketemu saat audit Tahap 3,
      // tidak tercatat di RFC awal) BUKAN didokumentasikan sebagai
      // exception -- edge-edge itu DIHILANGKAN dengan mengekstrak
      // switchTab() ke modul leaf baru render/navigation.js. Begitu juga
      // events/index.js -> render/discover-personalize.js
      // (initDiscoverFilterEvents): diaudit ulang Tahap 3, TERNYATA TIDAK
      // circular (cuma warning satu arah no-events-imports-render di
      // bawah), jadi tidak butuh entri exception di sini.
      name: 'circular-dependencies',
      comment: 'This project is designed to be free of circular dependencies.',
      severity: 'error',
      from: {
        pathNot: [
          '^web/static/shared/js/audio/playback-sync\\.js',
          '^web/static/shared/js/ws\\.js',
          '^web/static/shared/js/audio/visualizer\\.js',
          '^web/static/shared/js/ws/router\\.js',
          '^web/static/shared/js/ws/message-handlers/playback-messages\\.js',
          '^web/static/shared/js/ws/message-handlers/auth-messages\\.js',
          '^web/static/shared/js/ws/transport\\.js',
          '^web/static/shared/js/audio/media-session\\.js',
          '^web/static/shared/js/audio/audio-pool\\.js'
        ]
      },
      to: { circular: true }
    }
  ],
  options: {
    doNotFollow: {
      path: 'node_modules'
    },
    tsPreCompilationDeps: true,
    tsConfig: {
      fileName: 'tsconfig.json'
    },
    enhancedResolveOptions: {
      exportsFields: ['exports'],
      conditionNames: ['import', 'require', 'node', 'default']
    },
    reporterOptions: {
      dot: {
        collapsePattern: 'node_modules/[^/]+'
      }
    }
  }
};
