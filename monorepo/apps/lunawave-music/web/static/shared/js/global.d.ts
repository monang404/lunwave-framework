// Ambient declaration only — NOT a runtime dependency (ADR-0011 §6: JSDoc +
// tsc --checkJs, no build step, no npm runtime deps).
//
// Several shared modules (store.js, ws.js, utils/format.js) end with:
//   if (typeof module !== "undefined" && module.exports) { module.exports = {...} }
// This is an intentional dual CJS/ESM export shim so the same file can be
// `import`-ed by the browser (native ES module) and `require`-d by Vitest
// under Node. Declaring `module` here just lets tsc's `typeof module` check
// resolve the name; it has no effect on what actually loads in the browser.
declare var module: { exports: any } | undefined;

// PATCH-2026-07-24-224: tiga global ad-hoc yang di-assign lewat
// `globalThis.X = ...` / `window.X = ...` di runtime tapi tidak pernah
// dideklarasikan, jadi setiap pemakaian di file lain gagal TS2339 ("Property
// 'X' does not exist on type ..."). Bukan bug perilaku -- ini murni anotasi
// tipe untuk pola yang sudah ada (lihat ws.js:40, main.js:48, chat.js:127).

/** WebSocket aktif, di-set oleh ws.js (`globalThis.ws = ws`) / client.js
 * (`window.ws = new WebSocket(...)`). undefined sebelum koneksi dibuka. */
declare var ws: WebSocket | undefined;

/** API yang di-export chat.js untuk dipanggil balik dari ws.js saat pesan
 * chat masuk (lihat chat.js:127 `window.ChatModule = {...}`). */
interface ChatModuleApi {
    onHistory: (messages: any[]) => void;
    onNewMessage: (msg: any) => void;
}

interface Window {
    ws?: WebSocket;
    /** Alias `window.switchTab` untuk pemanggilan dari luar module graph
     * (lihat main.js:48). */
    switchTab?: (tab: string) => void;
    ChatModule?: ChatModuleApi;
    /** Kill switch untuk Service Worker (lihat main.js:96). */
    __lunawaveKillSW?: () => Promise<void>;
}

/** Di-assign lewat `globalThis.setRadioHeroAnimState = ...` di
 * radio-hero-moon.js:227, dipakai sebagai `typeof setRadioHeroAnimState`
 * check di playback-sync.js:184 dan radio-tab.js:36. */
declare var setRadioHeroAnimState: ((isOn: boolean) => void) | undefined;
