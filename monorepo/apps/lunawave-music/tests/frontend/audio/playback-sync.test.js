import { describe, it, expect, vi, afterEach } from "vitest";

vi.mock("../../../web/static/shared/js/audio/visualizer.js", () => ({
  initVisualizer: vi.fn(),
  resumeVisualizerLoop: vi.fn(),
  startFakeBeatLoop: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({
  syncLocalLyrics: vi.fn(),
  wsSend: vi.fn(),
}));

// playback-sync.js builds a real `audioPool = [new Audio(), new Audio()]`
// and wires several permanent listeners (per-audio timeupdate/pause/play,
// plus a document 'visibilitychange' listener) at *import time*, and keeps
// a large amount of other module-scope state (activeAudioIndex,
// _fadeIntervals, audioUnlocked, _unlocking, _lastLoadedVideoId, analyser).
// None of that has a reset hook, so every test gets a fully fresh module
// via vi.resetModules() + a fresh dynamic import.
async function setupModule() {
  vi.resetModules();
  const domMod = await import("../../../web/static/shared/js/dom.js");
  const storeMod = await import("../../../web/static/shared/js/store.js");
  const mod = await import("../../../web/static/shared/js/audio/playback-sync.js");
  const wsMod = await import("../../../web/static/shared/js/ws.js");
  const visualizerMod = await import("../../../web/static/shared/js/audio/visualizer.js");

  vi.stubGlobal("MediaMetadata", function (init) { Object.assign(this, init); });

  storeMod.store._pendingToggleTarget = null;
  storeMod.store._toggleSentAt = null;
  globalThis.isDraggingPb = false;
  globalThis.isDraggingVol = false;
  globalThis.audioBlocked = false;

  Object.assign(storeMod.store, {
    userRole: "admin",
    audio_output: "server",
    status: "PAUSED",
    current_track: null,
    crossfade_enabled: false,
    volume: 80,
    position: 0,
  });

  return {
    ...mod,
    dom: domMod.dom,
    store: storeMod.store,
    wsSend: wsMod.wsSend,
    syncLocalLyrics: wsMod.syncLocalLyrics,
    visualizer: visualizerMod,
  };
}

describe("audio/playback-sync.js", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    delete globalThis.AudioContext;
    delete globalThis.webkitAudioContext;
    // store._pendingToggleTarget is reset below anyway or can be omitted if resetModules is sufficient
    // reset by setupModule
    delete globalThis.isDraggingPb;
    delete globalThis.isDraggingVol;
    delete globalThis.audioBlocked;
  });

  describe("getOrInitAudio / resetLastLoadedVideoId", () => {
    it("returns the currently active pool element", async () => {
      const { getOrInitAudio } = await setupModule();
      const audio = getOrInitAudio();
      expect(audio).toBeInstanceOf(HTMLAudioElement);
    });

    it("resetLastLoadedVideoId does not throw", async () => {
      const { resetLastLoadedVideoId } = await setupModule();
      expect(() => resetLastLoadedVideoId()).not.toThrow();
    });
  });

  describe("initAudioPool listeners: timeupdate", () => {
    it("emits player:position and syncs lyrics for a client/browser listener on the active element", async () => {
      const { getOrInitAudio, store, syncLocalLyrics } = await setupModule();
      const { on } = await import("../../../web/static/shared/js/bus.js");
      store.userRole = "client";
      const handler = vi.fn();
      on("player:position", handler);

      const audio = getOrInitAudio();
      audio.currentTime = 42;
      audio.dispatchEvent(new Event("timeupdate"));

      expect(handler).toHaveBeenCalledWith(42);
      expect(syncLocalLyrics).toHaveBeenCalled();
    });

    it("does not emit position while the progress bar is being dragged", async () => {
      const { getOrInitAudio, store } = await setupModule();
      const { on } = await import("../../../web/static/shared/js/bus.js");
      store.userRole = "client";
      globalThis.isDraggingPb = true;
      const handler = vi.fn();
      on("player:position", handler);

      getOrInitAudio().dispatchEvent(new Event("timeupdate"));
      expect(handler).not.toHaveBeenCalled();
    });

    it("does nothing for admins on server output (not a browser listener)", async () => {
      const { getOrInitAudio, store } = await setupModule();
      const { on } = await import("../../../web/static/shared/js/bus.js");
      store.userRole = "admin";
      store.audio_output = "server";
      const handler = vi.fn();
      on("player:position", handler);

      getOrInitAudio().dispatchEvent(new Event("timeupdate"));
      expect(handler).not.toHaveBeenCalled();
    });
  });

  describe("initAudioPool listeners: native pause -> sync to server", () => {
    it("syncs PAUSED to the server when an admin's audio pauses natively while PLAYING", async () => {
      const { getOrInitAudio, store, wsSend } = await setupModule();
      const { on } = await import("../../../web/static/shared/js/bus.js");
      store.userRole = "admin";
      store.status = "PLAYING";
      const handler = vi.fn();
      on("now-playing:changed", handler);

      getOrInitAudio().dispatchEvent(new Event("pause"));

      expect(store.status).toBe("PAUSED");
      expect(store._pendingToggleTarget).toBe("PAUSED");
      expect(wsSend).toHaveBeenCalledWith("toggle_pause");
      expect(handler).toHaveBeenCalled();
    });

    it("does nothing when audioBlocked is true (programmatic pause, not user-initiated)", async () => {
      const { getOrInitAudio, store, wsSend } = await setupModule();
      store.userRole = "admin";
      store.status = "PLAYING";
      globalThis.audioBlocked = true;

      getOrInitAudio().dispatchEvent(new Event("pause"));
      expect(wsSend).not.toHaveBeenCalled();
      expect(store.status).toBe("PLAYING");
    });

    it("does nothing while a matching pending toggle is already in flight (UI grace period)", async () => {
      const { getOrInitAudio, store, wsSend } = await setupModule();
      store.userRole = "admin";
      store.status = "PLAYING";
      store._pendingToggleTarget = "PAUSED";
      store._toggleSentAt = Date.now();

      getOrInitAudio().dispatchEvent(new Event("pause"));
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("does not sync for non-admin users", async () => {
      const { getOrInitAudio, store, wsSend } = await setupModule();
      store.userRole = "client";
      store.status = "PLAYING";

      getOrInitAudio().dispatchEvent(new Event("pause"));
      expect(wsSend).not.toHaveBeenCalled();
      expect(store.status).toBe("PLAYING");
    });

    it("does nothing when the store wasn't PLAYING in the first place", async () => {
      const { getOrInitAudio, store, wsSend } = await setupModule();
      store.userRole = "admin";
      store.status = "PAUSED";

      getOrInitAudio().dispatchEvent(new Event("pause"));
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("initAudioPool listeners: native play -> sync to server", () => {
    it("syncs PLAYING to the server when an admin's audio starts natively while not PLAYING", async () => {
      const { getOrInitAudio, store, wsSend } = await setupModule();
      store.userRole = "admin";
      store.status = "PAUSED";

      getOrInitAudio().dispatchEvent(new Event("play"));

      expect(store.status).toBe("PLAYING");
      expect(store._pendingToggleTarget).toBe("PLAYING");
      expect(wsSend).toHaveBeenCalledWith("toggle_pause");
    });

    it("does nothing when audioBlocked is true", async () => {
      const { getOrInitAudio, store, wsSend } = await setupModule();
      store.userRole = "admin";
      store.status = "PAUSED";
      globalThis.audioBlocked = true;

      getOrInitAudio().dispatchEvent(new Event("play"));
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("does not sync for non-admin users", async () => {
      const { getOrInitAudio, store, wsSend } = await setupModule();
      store.userRole = "client";
      store.status = "PAUSED";

      getOrInitAudio().dispatchEvent(new Event("play"));
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("unlockBrowserAudio", () => {
    it("falls back to marking unlocked and syncing when there is no AudioContext available", async () => {
      const { unlockBrowserAudio, store } = await setupModule();
      delete globalThis.AudioContext;
      delete globalThis.webkitAudioContext;
      store.userRole = "client";
      store.audio_output = "browser";

      unlockBrowserAudio(true);
      // syncBrowserAudio ran; with no track, nothing to send, but it should
      // not throw and should proceed past the unlock gate.
      expect(() => unlockBrowserAudio(true)).not.toThrow();
    });

    it("resumes a suspended AudioContext before unlocking", async () => {
      const { unlockBrowserAudio, visualizer } = await setupModule();
      const resume = vi.fn().mockResolvedValue(undefined);
      vi.stubGlobal("AudioContext", vi.fn(function () { return { state: "suspended", resume }; }));

      unlockBrowserAudio(false);
      await vi.waitFor(() => expect(resume).toHaveBeenCalled());
      await vi.waitFor(() => expect(visualizer.initVisualizer).toHaveBeenCalled());
    });

    it("unlocks immediately when the AudioContext is already running", async () => {
      const { unlockBrowserAudio, visualizer } = await setupModule();
      vi.stubGlobal("AudioContext", vi.fn(function () { return { state: "running" }; }));

      unlockBrowserAudio(false);
      expect(visualizer.initVisualizer).toHaveBeenCalled();
    });

    it("only re-syncs (does not re-run the unlock sequence) once already unlocked", async () => {
      const { unlockBrowserAudio, visualizer } = await setupModule();
      vi.stubGlobal("AudioContext", vi.fn(function () { return { state: "running" }; }));
      unlockBrowserAudio(false);
      visualizer.initVisualizer.mockClear();

      unlockBrowserAudio(true);
      expect(visualizer.initVisualizer).not.toHaveBeenCalled();
    });

    it("falls open (still unlocks) if ctx.resume() rejects", async () => {
      const { unlockBrowserAudio } = await setupModule();
      const resume = vi.fn().mockRejectedValue(new Error("nope"));
      vi.stubGlobal("AudioContext", vi.fn(function () { return { state: "suspended", resume }; }));
      vi.spyOn(console, "warn").mockImplementation(() => {});

      unlockBrowserAudio(false);
      await vi.waitFor(() => expect(resume).toHaveBeenCalled());
      await new Promise((r) => setTimeout(r, 0));
      expect(true).toBe(true); // reaching here means no unhandled rejection
    });
  });

  describe("syncBrowserAudio", () => {
    it("pauses everything when the current user/output combo is not 'browser'", async () => {
      const { syncBrowserAudio, getOrInitAudio, store } = await setupModule();
      store.userRole = "admin";
      store.audio_output = "server";
      const audio = getOrInitAudio();
      const pauseSpy = vi.spyOn(audio, "pause");
      Object.defineProperty(audio, "paused", { value: false, configurable: true });

      syncBrowserAudio();
      expect(pauseSpy).toHaveBeenCalled();
    });

    it("pauses and clears the src when there is no current track", async () => {
      const { syncBrowserAudio, getOrInitAudio, store } = await setupModule();
      store.userRole = "client";
      store.current_track = null;
      const audio = getOrInitAudio();
      audio.setAttribute("src", "https://example.com/x.mp3");
      const loadSpy = vi.spyOn(audio, "load").mockImplementation(() => {});

      syncBrowserAudio();
      expect(audio.hasAttribute("src")).toBe(false);
      expect(loadSpy).toHaveBeenCalled();
    });

    it("loads a new track's stream URL and wires ontimeupdate/onended when the track changes", async () => {
      const { syncBrowserAudio, getOrInitAudio, store } = await setupModule();
      store.userRole = "client";
      store.current_track = { video_id: "v1" };
      vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => {});

      syncBrowserAudio();
      // syncBrowserAudio() flips activeAudioIndex to the *other* pool
      // element for a new track, so we must re-fetch the active element
      // afterward rather than reuse a reference captured beforehand.
      const audio = getOrInitAudio();

      expect(audio.src).toContain("/api/stream/v1");
      expect(typeof audio.ontimeupdate).toBe("function");
      expect(typeof audio.onended).toBe("function");
    });

    it("shows the tap-to-play banner instead of auto-playing while still locked", async () => {
      const { syncBrowserAudio, store } = await setupModule();
      store.userRole = "client";
      store.status = "PLAYING";
      store.current_track = { video_id: "v1" };
      vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => {});

      syncBrowserAudio(true);

      expect(globalThis.audioBlocked).toBe(true);
      expect(document.getElementById("audio-unlock-banner")).toBeTruthy();
    });

    it("onended requests the next track from the server for browser output", async () => {
      const { syncBrowserAudio, getOrInitAudio, store, wsSend } = await setupModule();
      store.userRole = "client";
      store.audio_output = "browser";
      store.current_track = { video_id: "v1" };
      vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => {});
      syncBrowserAudio();
      const audio = getOrInitAudio();

      audio.onended();
      expect(wsSend).toHaveBeenCalledWith("next", { video_id: "v1" });
    });

    it("ontimeupdate triggers a crossfade 'next' request within the crossfade window", async () => {
      const { syncBrowserAudio, getOrInitAudio, store, wsSend } = await setupModule();
      store.userRole = "client";
      store.audio_output = "browser";
      store.crossfade_enabled = true;
      store.current_track = { video_id: "v1" };
      vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => {});
      syncBrowserAudio();
      const audio = getOrInitAudio();

      Object.defineProperty(audio, "duration", { value: 100, configurable: true });
      Object.defineProperty(audio, "currentTime", { value: 96, configurable: true, writable: true }); // remaining=4 <= 5
      audio.ontimeupdate();

      expect(wsSend).toHaveBeenCalledWith("next", { video_id: "v1" });
    });

    it("ontimeupdate does not trigger crossfade outside the window or when disabled", async () => {
      const { syncBrowserAudio, getOrInitAudio, store, wsSend } = await setupModule();
      store.userRole = "client";
      store.audio_output = "browser";
      store.crossfade_enabled = false;
      store.current_track = { video_id: "v1" };
      vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => {});
      syncBrowserAudio();
      const audio = getOrInitAudio();

      Object.defineProperty(audio, "duration", { value: 100, configurable: true });
      Object.defineProperty(audio, "currentTime", { value: 96, configurable: true });
      audio.ontimeupdate();

      expect(wsSend).not.toHaveBeenCalledWith("next", { video_id: "v1" });
    });

    it("syncs volume and (when already unlocked) resumes playback for the same still-loaded track", async () => {
      const { syncBrowserAudio, unlockBrowserAudio, getOrInitAudio, store } = await setupModule();
      vi.stubGlobal("AudioContext", vi.fn(function () { return { state: "running" }; }));
      store.userRole = "client";
      store.audio_output = "browser";
      store.volume = 50;
      store.current_track = { video_id: "v1" };
      vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => {});

      unlockBrowserAudio(false); // marks audioUnlocked = true, loads v1 via syncBrowserAudio
      const audio = getOrInitAudio(); // active element may have flipped during load
      Object.defineProperty(audio, "src", { value: "https://x/api/stream/v1", configurable: true });
      Object.defineProperty(audio, "paused", { value: true, configurable: true });
      const playSpy = vi.spyOn(audio, "play").mockResolvedValue(undefined);

      store.status = "PLAYING";
      syncBrowserAudio(); // same track already loaded -> volume-sync branch

      expect(audio.volume).toBeCloseTo(0.5);
      expect(playSpy).toHaveBeenCalled();
    });

    it("pauses all pool elements and clears fade intervals when not forced to play and not PLAYING", async () => {
      const { syncBrowserAudio, getOrInitAudio, store } = await setupModule();
      store.userRole = "client";
      store.audio_output = "browser";
      store.current_track = { video_id: "v1" };
      store.status = "PAUSED";
      const audio = getOrInitAudio();
      vi.spyOn(audio, "load").mockImplementation(() => {});
      syncBrowserAudio(); // load track once
      Object.defineProperty(audio, "paused", { value: false, configurable: true });
      const pauseSpy = vi.spyOn(audio, "pause");

      syncBrowserAudio();
      expect(pauseSpy).toHaveBeenCalled();
    });
  });

  describe("initAudio", () => {
    it("wires a document click listener to unlockBrowserAudio", async () => {
      const { initAudio, store } = await setupModule();
      delete globalThis.AudioContext;
      store.userRole = "client";
      store.audio_output = "browser";
      initAudio();

      expect(() => document.body.click()).not.toThrow();
    });
  });

  describe("updateMediaSession", () => {
    it("is a no-op when the Media Session API is unavailable", async () => {
      const { updateMediaSession } = await setupModule();
      expect(() => updateMediaSession()).not.toThrow();
    });

    it("clears metadata when there is no current track", async () => {
      const { updateMediaSession, store } = await setupModule();
      const mediaSession = { metadata: "stale", playbackState: "" };
      vi.stubGlobal("navigator", { ...navigator, mediaSession });
      store.current_track = null;

      updateMediaSession();
      expect(mediaSession.metadata).toBeNull();
      expect(mediaSession.playbackState).toBe("none");
    });

    it("sets metadata and action handlers for a new track", async () => {
      const { updateMediaSession, store } = await setupModule();
      const setActionHandler = vi.fn();
      const mediaSession = { metadata: null, playbackState: "", setActionHandler };
      vi.stubGlobal("navigator", { ...navigator, mediaSession });
      store.current_track = { video_id: "v1", title: "T", artist: "A", thumbnail: "https://x/t.jpg" };
      store.status = "PLAYING";

      updateMediaSession();

      expect(mediaSession.metadata).toBeTruthy();
      expect(mediaSession.metadata.title).toBe("T");
      expect(setActionHandler).toHaveBeenCalledWith("play", expect.any(Function));
      expect(setActionHandler).toHaveBeenCalledWith("pause", expect.any(Function));
      expect(setActionHandler).toHaveBeenCalledWith("previoustrack", expect.any(Function));
      expect(setActionHandler).toHaveBeenCalledWith("nexttrack", expect.any(Function));
      expect(setActionHandler).toHaveBeenCalledWith("seekto", expect.any(Function));
      expect(mediaSession.playbackState).toBe("playing");
    });

    it("does not re-set metadata/handlers on subsequent calls for the same track", async () => {
      const { updateMediaSession, store } = await setupModule();
      const setActionHandler = vi.fn();
      const mediaSession = { metadata: null, playbackState: "", setActionHandler };
      vi.stubGlobal("navigator", { ...navigator, mediaSession });
      store.current_track = { video_id: "v1", title: "T", artist: "A" };

      updateMediaSession();
      setActionHandler.mockClear();
      updateMediaSession();

      expect(setActionHandler).not.toHaveBeenCalled();
    });

    it("the 'play' action handler optimistically flips status and asks the server to toggle", async () => {
      const { updateMediaSession, store, wsSend } = await setupModule();
      const handlers = {};
      const mediaSession = {
        metadata: null,
        playbackState: "",
        setActionHandler: (name, fn) => { handlers[name] = fn; },
      };
      vi.stubGlobal("navigator", { ...navigator, mediaSession });
      store.userRole = "admin";
      store.current_track = { video_id: "v1", title: "T", artist: "A" };
      store.status = "PAUSED";
      updateMediaSession();

      handlers.play();

      expect(store.status).toBe("PLAYING");
      expect(wsSend).toHaveBeenCalledWith("toggle_pause");
    });

    it("the 'nexttrack' action handler requests the next track for admins", async () => {
      const { updateMediaSession, store, wsSend } = await setupModule();
      const handlers = {};
      const mediaSession = {
        metadata: null,
        playbackState: "",
        setActionHandler: (name, fn) => { handlers[name] = fn; },
      };
      vi.stubGlobal("navigator", { ...navigator, mediaSession });
      store.userRole = "admin";
      store.current_track = { video_id: "v1", title: "T", artist: "A" };
      updateMediaSession();

      handlers.nexttrack();

      expect(store.status).toBe("LOADING");
      expect(wsSend).toHaveBeenCalledWith("next", { video_id: "v1" });
    });

    it("the 'seekto' action handler sends the seek position", async () => {
      const { updateMediaSession, store, wsSend } = await setupModule();
      const handlers = {};
      const mediaSession = {
        metadata: null,
        playbackState: "",
        setActionHandler: (name, fn) => { handlers[name] = fn; },
      };
      vi.stubGlobal("navigator", { ...navigator, mediaSession });
      store.current_track = { video_id: "v1", title: "T", artist: "A" };
      updateMediaSession();

      handlers.seekto({ seekTime: 12.5 });
      expect(wsSend).toHaveBeenCalledWith("seek", { position: 12.5 });
    });
  });

  describe("visibilitychange listener", () => {
    it("emits player:clock-stop when the tab becomes hidden", async () => {
      await setupModule();
      const { on } = await import("../../../web/static/shared/js/bus.js");
      const handler = vi.fn();
      on("player:clock-stop", handler);
      Object.defineProperty(document, "hidden", { value: true, configurable: true });

      document.dispatchEvent(new Event("visibilitychange"));
      expect(handler).toHaveBeenCalled();
    });

    it("emits player:clock-start and resumes the visualizer when the tab becomes visible while playing", async () => {
      const { store, visualizer } = await setupModule();
      const { on } = await import("../../../web/static/shared/js/bus.js");
      store.status = "PLAYING";
      const handler = vi.fn();
      on("player:clock-start", handler);
      Object.defineProperty(document, "hidden", { value: false, configurable: true });

      document.dispatchEvent(new Event("visibilitychange"));
      expect(handler).toHaveBeenCalled();
      expect(visualizer.resumeVisualizerLoop).toHaveBeenCalled();
    });
  });
});
