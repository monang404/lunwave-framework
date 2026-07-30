import { describe, it, expect, vi, afterEach } from "vitest";

vi.mock("../../../web/static/shared/js/bus.js", () => ({ emit: vi.fn() }));
vi.mock("../../../web/static/shared/js/events/settings-events.js", () => ({
  closeMainOverlay: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({
  syncLocalLyrics: vi.fn(),
  wsSend: vi.fn(),
}));

// lyrics-events.js captures btn-sync-minus/plus, lyrics-wrap, and
// lyric-sync-ctrls via document.getElementById(...) at *module import
// time* (module-scope consts, not read fresh inside initLyricsEvents()).
// So the real <div id="lyrics-wrap">... markup must exist in the document
// *before* the module is imported. We rebuild that markup and do a fresh
// (vi.resetModules()) import every test, so listeners attached to those
// persistent nodes never accumulate across tests.
async function setupModule() {
  document.body.innerHTML = `
    <div id="lyrics-wrap">
      <div id="lyric-sync-ctrls">
        <button id="btn-sync-minus"></button>
        <button id="btn-sync-plus"></button>
      </div>
    </div>
  `;
  vi.resetModules();
  const domMod = await import("../../../web/static/shared/js/dom.js");
  const storeMod = await import("../../../web/static/shared/js/store.js");
  const { initLyricsEvents } = await import(
    "../../../web/static/shared/js/events/lyrics-events.js"
  );
  const { emit } = await import("../../../web/static/shared/js/bus.js");
  const { closeMainOverlay } = await import(
    "../../../web/static/shared/js/events/settings-events.js"
  );
  const { syncLocalLyrics, wsSend } = await import("../../../web/static/shared/js/ws.js");

  Object.assign(domMod.dom, {
    btnLyrics: document.createElement("button"),
    lyricsCloseBtn: document.createElement("button"),
    lyricsSheet: document.createElement("div"),
    mainOverlay: document.createElement("div"),
    lyricOffsetMinus: document.createElement("button"),
    lyricOffsetPlus: document.createElement("button"),
  });
  storeMod.store.userRole = "admin";
  storeMod.store.lyrics_offset = 0;

  initLyricsEvents();

  return {
    dom: domMod.dom,
    store: storeMod.store,
    emit,
    closeMainOverlay,
    syncLocalLyrics,
    wsSend,
  };
}

describe("events/lyrics-events.js", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("btnLyrics opens the lyrics sheet + overlay and emits lyrics:changed", async () => {
    const { dom, emit } = await setupModule();
    dom.btnLyrics.click();

    expect(dom.lyricsSheet.classList.contains("open")).toBe(true);
    expect(dom.mainOverlay.classList.contains("open")).toBe(true);
    expect(emit).toHaveBeenCalledWith("lyrics:changed");
  });

  it("lyricsCloseBtn closes the sheet and calls closeMainOverlay", async () => {
    const { dom, closeMainOverlay } = await setupModule();
    dom.lyricsSheet.classList.add("open");
    dom.lyricsCloseBtn.click();

    expect(dom.lyricsSheet.classList.contains("open")).toBe(false);
    expect(closeMainOverlay).toHaveBeenCalled();
  });

  it("lyricOffsetMinus decreases the offset for admins and notifies the server", async () => {
    const { dom, store, emit, syncLocalLyrics, wsSend } = await setupModule();
    dom.lyricOffsetMinus.click();

    expect(store.lyrics_offset).toBe(-0.5);
    expect(emit).toHaveBeenCalledWith("lyrics:offset-display");
    expect(syncLocalLyrics).toHaveBeenCalled();
    expect(wsSend).toHaveBeenCalledWith("lyrics_offset", { offset: -0.5 });
  });

  it("lyricOffsetPlus increases the offset for admins and notifies the server", async () => {
    const { dom, store, wsSend } = await setupModule();
    dom.lyricOffsetPlus.click();

    expect(store.lyrics_offset).toBe(0.5);
    expect(wsSend).toHaveBeenCalledWith("lyrics_offset", { offset: 0.5 });
  });

  it("lyricOffsetMinus/Plus are no-ops for non-admins", async () => {
    const { dom, store, wsSend } = await setupModule();
    store.userRole = "client";
    dom.lyricOffsetMinus.click();
    dom.lyricOffsetPlus.click();

    expect(store.lyrics_offset).toBe(0);
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("moving the mouse over lyrics-wrap shows the sync controls and auto-hides after 3s", async () => {
    vi.useFakeTimers();
    await setupModule();
    const lyricsWrap = document.getElementById("lyrics-wrap");
    const lyricSyncCtrls = document.getElementById("lyric-sync-ctrls");

    lyricsWrap.dispatchEvent(new Event("mousemove", { bubbles: true }));
    expect(lyricSyncCtrls.classList.contains("active")).toBe(true);

    vi.advanceTimersByTime(3000);
    expect(lyricSyncCtrls.classList.contains("active")).toBe(false);
    vi.useRealTimers();
  });

  it("btn-sync-minus stops propagation, adjusts offset for admins, and re-shows sync controls", async () => {
    const { store, wsSend } = await setupModule();
    const btnSyncMinus = document.getElementById("btn-sync-minus");
    const lyricSyncCtrls = document.getElementById("lyric-sync-ctrls");
    const event = new Event("click", { bubbles: true });
    const stopSpy = vi.spyOn(event, "stopPropagation");

    btnSyncMinus.dispatchEvent(event);

    expect(stopSpy).toHaveBeenCalled();
    expect(store.lyrics_offset).toBe(-0.5);
    expect(wsSend).toHaveBeenCalledWith("lyrics_offset", { offset: -0.5 });
    expect(lyricSyncCtrls.classList.contains("active")).toBe(true);
  });

  it("btn-sync-plus stops propagation and adjusts offset for admins", async () => {
    const { store, wsSend } = await setupModule();
    const btnSyncPlus = document.getElementById("btn-sync-plus");

    btnSyncPlus.dispatchEvent(new Event("click", { bubbles: true }));

    expect(store.lyrics_offset).toBe(0.5);
    expect(wsSend).toHaveBeenCalledWith("lyrics_offset", { offset: 0.5 });
  });

  it("btn-sync-minus/plus are no-ops for non-admins (offset unchanged)", async () => {
    const { store, wsSend } = await setupModule();
    store.userRole = "client";
    const btnSyncMinus = document.getElementById("btn-sync-minus");

    btnSyncMinus.dispatchEvent(new Event("click", { bubbles: true }));

    expect(store.lyrics_offset).toBe(0);
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("is safe to call when optional dom elements are missing", async () => {
    document.body.innerHTML = "";
    vi.resetModules();
    const domMod = await import("../../../web/static/shared/js/dom.js");
    const { initLyricsEvents } = await import(
      "../../../web/static/shared/js/events/lyrics-events.js"
    );
    Object.assign(domMod.dom, {
      btnLyrics: null,
      lyricsCloseBtn: null,
      lyricOffsetMinus: null,
      lyricOffsetPlus: null,
    });
    expect(() => initLyricsEvents()).not.toThrow();
  });
});
