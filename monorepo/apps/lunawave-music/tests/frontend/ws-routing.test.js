import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

import { on } from "../../web/static/shared/js/bus.js";
import { store } from "../../web/static/shared/js/store.js";
import { dom } from "../../web/static/shared/js/dom.js";
import * as toast from "../../web/static/shared/js/render/toast.js";
import * as search from "../../web/static/shared/js/render/search.js";
import * as discoverTab from "../../web/static/shared/js/render/discover-tab.js";

// Mock out UI renderers
vi.mock("../../web/static/shared/js/render/toast.js", () => ({ showLogToast: vi.fn(), showPersistentToast: vi.fn(), hidePersistentToast: vi.fn(), showConnectionToast: vi.fn(), hideConnectionToast: vi.fn() }));
vi.mock("../../web/static/shared/js/services/auth.js", () => ({ applyRoleUI: vi.fn(), login: vi.fn(), logout: vi.fn() }));
vi.mock("../../web/static/shared/js/render/full-state.js", () => ({ renderFullState: vi.fn(), applyFullState: vi.fn() }));
vi.mock("../../web/static/shared/js/render/search.js", () => ({ renderSearchResults: vi.fn(), updateSearchPlayingState: vi.fn() }));
vi.mock("../../web/static/shared/js/render/discover-tab.js", () => ({ renderDiscoverTab: vi.fn(), renderRecentRow: vi.fn(), updateDiscoverPlayingState: vi.fn() }));
vi.mock("../../web/static/shared/js/render/now-playing.js", () => ({ renderNowPlaying: vi.fn(), syncPlayerStateAttr: vi.fn() }));
vi.mock("../../web/static/shared/js/render/player.js", () => ({ renderPlayerState: vi.fn(), renderProgress: vi.fn(), renderPlayBtn: vi.fn(), renderPlayerBar: vi.fn(), resetAnchorClock: vi.fn(), setPositionAnchor: vi.fn() }));
vi.mock("../../web/static/shared/js/render/queue.js", () => ({ renderQueue: vi.fn() }));
vi.mock("../../web/static/shared/js/render/radio-tab.js", () => ({ renderRadio: vi.fn() }));
vi.mock("../../web/static/shared/js/render/lyrics.js", () => ({ renderLyrics: vi.fn(), syncLocalLyrics: vi.fn() }));
vi.mock("../../web/static/shared/js/audio/playback-sync.js", () => ({ syncBrowserAudio: vi.fn(), getOrInitAudio: vi.fn(), _resumeAndPlay: vi.fn() }));

// Setup DOM mocks
dom.loginErrorMsg = { textContent: "" };
dom.portalLoginForm = { classList: { add: vi.fn(), remove: vi.fn() } };
dom.setupSubmitBtn = { disabled: true, textContent: "" };
dom.setupErrorMsg = { textContent: "" };
dom.setupConfirmErrorMsg = { textContent: "" };
dom.setupScreen = { classList: { add: vi.fn(), remove: vi.fn() } };
dom.portalScreen = { classList: { add: vi.fn(), remove: vi.fn() } };
dom.adminUsername = { value: "someuser" };
dom.logToast = { textContent: "", classList: { add: vi.fn(), remove: vi.fn() } };
dom.statusDot = { classList: { add: vi.fn(), remove: vi.fn() } };
dom.statusText = { textContent: "" };
dom.outputToggleBtn = { classList: { add: vi.fn(), remove: vi.fn() }, textContent: "" };

// Mock globalThis.safeStorage for ES modules
globalThis.safeStorage = { set: vi.fn(), remove: vi.fn(), get: vi.fn() };

import * as wsModule from "../../web/static/shared/js/ws.js";
import * as playbackSync from "../../web/static/shared/js/audio/playback-sync.js";
import * as busModule from "../../web/static/shared/js/bus.js";

// vi.mock() above replaces toast.js/search.js/discover-tab.js entirely, so the
// real init*BusSubscriptions() (which call bus.on(...)) never run -- normally
// main.js calls these at startup. Without this, ws.js's bus(...) emits have no
// listeners and the mocked render fns below are never invoked. Wire them here
// to mirror what main.js does in the real app.
on("toast:log", ({ message }) => toast.showLogToast(message));
on("toast:connection-show", ({ text, type }) => toast.showConnectionToast(text, type));
on("toast:connection-hide", () => toast.hideConnectionToast());
on("search:results", (data) => search.renderSearchResults(data));
on("discover:tab-changed", () => discoverTab.renderDiscoverTab());
on("discover:recent-changed", (data) => discoverTab.renderRecentRow(data));

describe("WebSocket Message Router", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(store, { status: "IDLE", userRole: "client", is_online: true });
  });

  it("handles auth_status success", () => {
    wsModule.handleServerMessage({ type: "auth_status", data: { success: true, token: "abc" } });
    expect(store.userRole).toBe("admin");
    expect(globalThis.safeStorage.set).toHaveBeenCalledWith("lunawave_session_token", "abc");
    expect(toast.showLogToast).toHaveBeenCalledWith("Akses Admin Diterima!");
  });

  it("handles setup_status success -- switches from setup-screen to portal-screen", () => {
    wsModule.handleServerMessage({ type: "setup_status", data: { success: true } });
    expect(dom.setupSubmitBtn.disabled).toBe(false);
    expect(dom.setupScreen.classList.remove).toHaveBeenCalledWith("portal-active");
    expect(dom.portalScreen.classList.add).toHaveBeenCalledWith("portal-active");
    expect(dom.adminUsername.value).toBe("");
    expect(toast.showLogToast).toHaveBeenCalledWith("Akun admin berhasil dibuat! Silakan login.");
  });

  it("handles setup_status failure -- keeps setup-screen, shows server message", () => {
    dom.setupScreen.classList.remove.mockClear();
    dom.portalScreen.classList.add.mockClear();
    wsModule.handleServerMessage({
      type: "setup_status",
      data: { success: false, message: "Akun admin sudah pernah dibuat. Silakan login." },
    });
    expect(dom.setupSubmitBtn.disabled).toBe(false);
    expect(dom.setupErrorMsg.textContent).toBe("Akun admin sudah pernah dibuat. Silakan login.");
    expect(dom.setupScreen.classList.remove).not.toHaveBeenCalled();
    expect(dom.portalScreen.classList.add).not.toHaveBeenCalled();
  });

  it("handles log", () => {
    wsModule.handleServerMessage({ type: "log", data: "Test log message" });
    expect(toast.showLogToast).toHaveBeenCalledWith("Test log message");
  });

  it("handles error", () => {
    wsModule.handleServerMessage({ type: "error", data: "Test error" });
    expect(toast.showLogToast).toHaveBeenCalledWith("Error: Test error");
  });

  it("handles search_results", () => {
    wsModule.handleServerMessage({ type: "search_results", data: [] });
    expect(search.renderSearchResults).toHaveBeenCalledWith([]);
  });

  it("handles discover_data and stores favorites alongside recent/cached", () => {
    wsModule.handleServerMessage({
      type: "discover_data",
      data: {
        recent: [{ video_id: "r1" }],
        favorites: [{ video_id: "f1" }],
        cached_tracks: [{ video_id: "c1" }],
        featured_artists: [],
        featured_genres: [],
      },
    });
    expect(store.discover_recent).toEqual([{ video_id: "r1" }]);
    expect(store.discover_favorites).toEqual([{ video_id: "f1" }]);
    expect(store.discover_cached).toEqual([{ video_id: "c1" }]);
    expect(discoverTab.renderDiscoverTab).toHaveBeenCalled();
  });

  it("defaults discover_favorites to empty array when server omits it", () => {
    wsModule.handleServerMessage({
      type: "discover_data",
      data: { recent: [], cached_tracks: [], featured_artists: [], featured_genres: [] },
    });
    expect(store.discover_favorites).toEqual([]);
  });

  it("handles auth_status failure -- shows the server message and logs out an already-admin session", () => {
    store.userRole = "admin";
    dom.loginErrorMsg.textContent = "";
    wsModule.handleServerMessage({
      type: "auth_status",
      data: { success: false, message: "Password salah." },
    });
    expect(dom.loginErrorMsg.textContent).toBe("Password salah.");
  });

  it("handles state -- forwards the payload via state:full", () => {
    const emitSpy = vi.spyOn(busModule, "emit");
    wsModule.handleServerMessage({ type: "state", data: { status: "PAUSED" } });
    expect(emitSpy).toHaveBeenCalledWith("state:full", { status: "PAUSED" });
  });

  describe("progress", () => {
    beforeEach(() => {
      store._pendingToggleTarget = null;
      store._toggleSentAt = null;
      playbackSync.getOrInitAudio.mockReset();
    });

    it("updates store.status on a genuine change and resets the clock when it becomes PLAYING", () => {
      const emitSpy = vi.spyOn(busModule, "emit");
      store.status = "PAUSED";
      store.audio_output = "server";
      wsModule.handleServerMessage({ type: "progress", data: { status: "PLAYING", position: 10 } });
      expect(store.status).toBe("PLAYING");
      expect(emitSpy).toHaveBeenCalledWith("player:clock-reset");
    });

    it("ignores a contradictory status while a pending toggle to a different target is still in flight", () => {
      store._pendingToggleTarget = "PAUSED";
      store._toggleSentAt = Date.now();
      store.status = "PLAYING";
      wsModule.handleServerMessage({ type: "progress", data: { status: "PLAYING", position: 10 } });
      expect(store.status).toBe("PLAYING"); // unchanged: PLAYING contradicts the awaited PAUSED
      expect(store._pendingToggleTarget).toBe("PAUSED"); // still waiting
    });

    it("clears the pending toggle once the server confirms the awaited target", () => {
      store._pendingToggleTarget = "PAUSED";
      store._toggleSentAt = Date.now();
      store.status = "PLAYING";
      wsModule.handleServerMessage({ type: "progress", data: { status: "PAUSED", position: 10 } });
      expect(store.status).toBe("PAUSED");
      expect(store._pendingToggleTarget).toBeNull();
    });

    it("anchors player:position from the server when output is not 'browser'", () => {
      const emitSpy = vi.spyOn(busModule, "emit");
      store.audio_output = "server";
      wsModule.handleServerMessage({ type: "progress", data: { status: "PLAYING", position: 42 } });
      expect(emitSpy).toHaveBeenCalledWith("player:position", 42);
    });

    it("does not anchor position from the server when output is 'browser'", () => {
      const emitSpy = vi.spyOn(busModule, "emit");
      store.audio_output = "browser";
      store.status = "PAUSED";
      wsModule.handleServerMessage({ type: "progress", data: { status: "PAUSED", position: 42 } });
      expect(emitSpy).not.toHaveBeenCalledWith("player:position", 42);
    });

    it("re-seeks the browser <audio> element when it has drifted more than 5s from the server", () => {
      const emitSpy = vi.spyOn(busModule, "emit");
      const fakeAudio = { paused: false, src: "https://x/api/stream/v1", currentTime: 10, readyState: 4 };
      playbackSync.getOrInitAudio.mockReturnValue(fakeAudio);
      store.audio_output = "browser";
      store.status = "PLAYING";
      wsModule.handleServerMessage({ type: "progress", data: { status: "PLAYING", position: 20 } });
      expect(fakeAudio.currentTime).toBe(20);
      expect(emitSpy).toHaveBeenCalledWith("player:position", 20);
    });

    it("does not re-seek when the drift is within the 5s tolerance", () => {
      const fakeAudio = { paused: false, src: "https://x/api/stream/v1", currentTime: 10, readyState: 4 };
      playbackSync.getOrInitAudio.mockReturnValue(fakeAudio);
      store.audio_output = "browser";
      store.status = "PLAYING";
      wsModule.handleServerMessage({ type: "progress", data: { status: "PLAYING", position: 12 } });
      expect(fakeAudio.currentTime).toBe(10);
    });

    it("resumes a stuck-paused browser audio element (readyState loaded) when not blocked", () => {
      const fakeAudio = { paused: true, src: "https://x/api/stream/v1", currentTime: 0, readyState: 3 };
      playbackSync.getOrInitAudio.mockReturnValue(fakeAudio);
      globalThis.audioBlocked = false;
      store.audio_output = "browser";
      store.status = "PLAYING";
      wsModule.handleServerMessage({ type: "progress", data: { status: "PLAYING", position: 5 } });
      expect(playbackSync._resumeAndPlay).toHaveBeenCalledWith(fakeAudio);
    });

    it("does not retry resuming when audioBlocked is already true", () => {
      const fakeAudio = { paused: true, src: "https://x/api/stream/v1", currentTime: 0, readyState: 3 };
      playbackSync.getOrInitAudio.mockReturnValue(fakeAudio);
      globalThis.audioBlocked = true;
      store.audio_output = "browser";
      store.status = "PLAYING";
      wsModule.handleServerMessage({ type: "progress", data: { status: "PLAYING", position: 5 } });
      expect(playbackSync._resumeAndPlay).not.toHaveBeenCalled();
      globalThis.audioBlocked = false;
    });

    it("always re-syncs browser audio and emits progress/btn-changed/sync-state-attr", () => {
      const emitSpy = vi.spyOn(busModule, "emit");
      wsModule.handleServerMessage({ type: "progress", data: { status: "PAUSED", position: 0 } });
      expect(playbackSync.syncBrowserAudio).toHaveBeenCalled();
      expect(emitSpy).toHaveBeenCalledWith("player:progress");
      expect(emitSpy).toHaveBeenCalledWith("player:btn-changed");
      expect(emitSpy).toHaveBeenCalledWith("now-playing:sync-state-attr");
    });

    it("emits the full set of change events only when the status actually changed", () => {
      const emitSpy = vi.spyOn(busModule, "emit");
      store.status = "PAUSED";
      store.audio_output = "server";
      wsModule.handleServerMessage({ type: "progress", data: { status: "PLAYING", position: 0 } });
      expect(emitSpy).toHaveBeenCalledWith("now-playing:changed");
      expect(emitSpy).toHaveBeenCalledWith("queue:changed");
      expect(emitSpy).toHaveBeenCalledWith("radio:changed");
      expect(emitSpy).toHaveBeenCalledWith("search:playing-state");
      expect(emitSpy).toHaveBeenCalledWith("discover:playing-state");
    });

    it("does not emit the change events when the status is unchanged", () => {
      const emitSpy = vi.spyOn(busModule, "emit");
      store.status = "PLAYING";
      store.audio_output = "server";
      wsModule.handleServerMessage({ type: "progress", data: { status: "PLAYING", position: 0 } });
      expect(emitSpy).not.toHaveBeenCalledWith("now-playing:changed");
    });
  });

  it("handles lyrics -- stores lines/timestamps/offset and emits lyrics:changed", () => {
    const emitSpy = vi.spyOn(busModule, "emit");
    wsModule.handleServerMessage({
      type: "lyrics",
      data: { lyrics_lines: ["a", "b"], lyrics_timestamps: [0, 5], lyrics_index: 1, lyrics_offset: 0.5 },
    });
    expect(store.lyrics_lines).toEqual(["a", "b"]);
    expect(store.lyrics_timestamps).toEqual([0, 5]);
    expect(store.lyrics_index).toBe(1);
    expect(store.lyrics_offset).toBe(0.5);
    expect(emitSpy).toHaveBeenCalledWith("lyrics:changed");
  });

  it("handles discover_search_results", () => {
    const emitSpy = vi.spyOn(busModule, "emit");
    wsModule.handleServerMessage({ type: "discover_search_results", data: [{ video_id: "v1" }] });
    expect(emitSpy).toHaveBeenCalledWith("discover:search-results", [{ video_id: "v1" }]);
  });

  it("handles artist_detail", () => {
    const emitSpy = vi.spyOn(busModule, "emit");
    wsModule.handleServerMessage({ type: "artist_detail", data: { nama: "Dewa 19" } });
    expect(emitSpy).toHaveBeenCalledWith("discover:artist-detail", { nama: "Dewa 19" });
  });

  it("handles error -- also signals discover search to show an error state", () => {
    const emitSpy = vi.spyOn(busModule, "emit");
    wsModule.handleServerMessage({ type: "error", data: "boom" });
    expect(emitSpy).toHaveBeenCalledWith("discover:search-error");
  });

  describe("download_progress", () => {
    it("stores the progress and shows a start toast the first time it goes below 1.0", () => {
      store.download_progress = null;
      wsModule.handleServerMessage({ type: "download_progress", data: 0.1 });
      expect(store.download_progress).toBe(0.1);
      expect(toast.showLogToast).toHaveBeenCalledWith("⬇ Mulai mengunduh lagu...");
    });

    it("shows a completion toast and clears the progress after 3s once it reaches 1.0", () => {
      vi.useFakeTimers();
      store.download_progress = 0.9;
      wsModule.handleServerMessage({ type: "download_progress", data: 1.0 });
      expect(toast.showLogToast).toHaveBeenCalledWith("✅ Unduhan selesai! Tersedia di Tersimpan Lokal");
      vi.advanceTimersByTime(3000);
      expect(store.download_progress).toBeNull();
      vi.useRealTimers();
    });

    it("does not re-announce completion on a second 1.0 message", () => {
      store.download_progress = 1.0;
      toast.showLogToast.mockClear();
      wsModule.handleServerMessage({ type: "download_progress", data: 1.0 });
      expect(toast.showLogToast).not.toHaveBeenCalledWith("✅ Unduhan selesai! Tersedia di Tersimpan Lokal");
    });
  });

  describe("cache_size / cache_cleared", () => {
    beforeEach(() => {
      dom.ssCacheSub = { textContent: "" };
    });

    it("formats cache_size into MB", () => {
      wsModule.handleServerMessage({ type: "cache_size", data: { size_bytes: 5 * 1024 * 1024 } });
      expect(dom.ssCacheSub.textContent).toBe("5.00 MB");
    });

    it("resets to 0.00 MB on cache_cleared", () => {
      dom.ssCacheSub.textContent = "5.00 MB";
      wsModule.handleServerMessage({ type: "cache_cleared" });
      expect(dom.ssCacheSub.textContent).toBe("0.00 MB");
    });

    it("does not throw when dom.ssCacheSub is absent", () => {
      dom.ssCacheSub = null;
      expect(() =>
        wsModule.handleServerMessage({ type: "cache_size", data: { size_bytes: 1024 } })
      ).not.toThrow();
    });
  });

  describe("chat_history / chat_message", () => {
    it("forwards history to globalThis.ChatModule.onHistory when present", () => {
      globalThis.ChatModule = { onHistory: vi.fn(), onNewMessage: vi.fn() };
      wsModule.handleServerMessage({ type: "chat_history", data: [{ text: "hi" }] });
      expect(globalThis.ChatModule.onHistory).toHaveBeenCalledWith([{ text: "hi" }]);
      delete globalThis.ChatModule;
    });

    it("forwards a new message to globalThis.ChatModule.onNewMessage when present", () => {
      globalThis.ChatModule = { onHistory: vi.fn(), onNewMessage: vi.fn() };
      wsModule.handleServerMessage({ type: "chat_message", data: { text: "hai" } });
      expect(globalThis.ChatModule.onNewMessage).toHaveBeenCalledWith({ text: "hai" });
      delete globalThis.ChatModule;
    });

    it("does not throw when ChatModule is not loaded", () => {
      delete globalThis.ChatModule;
      expect(() =>
        wsModule.handleServerMessage({ type: "chat_message", data: { text: "hai" } })
      ).not.toThrow();
    });
  });

  it("ignores unknown message types without throwing", () => {
    expect(() => wsModule.handleServerMessage({ type: "totally_unknown", data: {} })).not.toThrow();
  });
});

describe("wsSend", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    store._pendingToggleTarget = "PAUSED";
  });

  afterEach(() => {
    store._pendingToggleTarget = null;
  });

  it("clears the pending toggle target for track-changing actions (next/prev/play_track)", () => {
    wsModule.wsSend("next", { video_id: "v1" });
    expect(store._pendingToggleTarget).toBeNull();
  });

  it("does not clear the pending toggle target for unrelated actions", () => {
    wsModule.wsSend("toggle_pause");
    expect(store._pendingToggleTarget).toBe("PAUSED");
  });

  it("does not throw when there is no open socket", () => {
    expect(() => wsModule.wsSend("discover")).not.toThrow();
  });
});

describe("syncLocalLyrics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(store, {
      lyrics_timestamps: [],
      lyrics_index: 0,
      lyrics_offset: 0,
      position: 0,
    });
  });

  it("does nothing when there are no lyrics timestamps", () => {
    const emitSpy = vi.spyOn(busModule, "emit");
    wsModule.syncLocalLyrics();
    expect(emitSpy).not.toHaveBeenCalledWith("lyrics:changed");
  });

  it("advances lyrics_index to the last timestamp not exceeding the current position", () => {
    const emitSpy = vi.spyOn(busModule, "emit");
    store.lyrics_timestamps = [0, 5, 10, 15];
    store.position = 11;
    wsModule.syncLocalLyrics();
    expect(store.lyrics_index).toBe(2);
    expect(emitSpy).toHaveBeenCalledWith("lyrics:changed");
  });

  it("accounts for a manual sync offset", () => {
    store.lyrics_timestamps = [0, 5, 10];
    store.position = 4;
    store.lyrics_offset = 2; // 4+2=6 -> index for timestamp 5
    wsModule.syncLocalLyrics();
    expect(store.lyrics_index).toBe(1);
  });

  it("does not emit again when the index hasn't actually changed", () => {
    store.lyrics_timestamps = [0, 5, 10];
    store.position = 6;
    wsModule.syncLocalLyrics(); // first call: index 0 -> 1
    // vi.spyOn on an already-spied function (e.g. from an earlier test in
    // this describe block, never restored) returns the SAME spy instance
    // and keeps its prior call history -- so we must clear it explicitly
    // right here rather than assume a fresh spy starts empty.
    const emitSpy = vi.spyOn(busModule, "emit");
    emitSpy.mockClear();
    wsModule.syncLocalLyrics(); // same position, same index
    expect(emitSpy).not.toHaveBeenCalledWith("lyrics:changed");
  });

  it("clamps to index 0 before the first timestamp", () => {
    store.lyrics_timestamps = [5, 10];
    store.position = 0;
    wsModule.syncLocalLyrics();
    expect(store.lyrics_index).toBe(0);
  });
});

describe("renderHeader", () => {
  beforeEach(() => {
    dom.statusDot = { classList: { add: vi.fn(), remove: vi.fn() } };
    dom.statusText = { textContent: "" };
    dom.outputToggleBtn = { classList: { add: vi.fn(), remove: vi.fn() }, textContent: "" };
  });

  it("shows 'online' and removes the offline class when connected", () => {
    store.is_online = true;
    wsModule.renderHeader();
    expect(dom.statusDot.classList.remove).toHaveBeenCalledWith("offline");
    expect(dom.statusText.textContent).toBe("online");
  });

  it("shows 'offline' and adds the offline class when disconnected", () => {
    store.is_online = false;
    wsModule.renderHeader();
    expect(dom.statusDot.classList.add).toHaveBeenCalledWith("offline");
    expect(dom.statusText.textContent).toBe("offline");
  });

  it("labels the output toggle for browser output", () => {
    store.audio_output = "browser";
    wsModule.renderHeader();
    expect(dom.outputToggleBtn.textContent).toContain("BROWSER");
    expect(dom.outputToggleBtn.classList.add).toHaveBeenCalledWith("browser");
  });

  it("labels the output toggle for device/server output", () => {
    store.audio_output = "server";
    wsModule.renderHeader();
    expect(dom.outputToggleBtn.textContent).toContain("HP");
    expect(dom.outputToggleBtn.classList.remove).toHaveBeenCalledWith("browser");
  });

  it("defaults to 'browser' labeling when audio_output is unset", () => {
    store.audio_output = undefined;
    wsModule.renderHeader();
    expect(dom.outputToggleBtn.textContent).toContain("BROWSER");
  });
});
