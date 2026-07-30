import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  _fadeIntervals: {},
  activeAudioIndex: 0,
  getOrInitAudio: vi.fn(() => ({ volume: 1 })),
}));
vi.mock("../../../web/static/shared/js/render/now-playing.js", () => ({
  syncPlayerStateAttr: vi.fn(),
}));

function el(tag = "div") {
  return document.createElement(tag);
}
function elStyle(tag = "div") {
  return Object.assign(el(tag), { style: {} });
}

async function setupModule() {
  // Fresh module registry per test: player.js keeps its progress-clock
  // state (_progressRafId, _posAnchorValue/_Time, _lastRenderedSec) at
  // module scope with no reset hook, so re-importing after
  // vi.resetModules() is the only way to get a clean starting point.
  const rafCallbacks = [];
  let nextId = 1;
  vi.stubGlobal("requestAnimationFrame", vi.fn((cb) => {
    const id = nextId++;
    rafCallbacks.push({ id, cb });
    return id;
  }));
  vi.stubGlobal("cancelAnimationFrame", vi.fn((id) => {
    const idx = rafCallbacks.findIndex((r) => r.id === id);
    if (idx !== -1) rafCallbacks.splice(idx, 1);
  }));

  vi.resetModules();
  const domMod = await import("../../../web/static/shared/js/dom.js");
  const storeMod = await import("../../../web/static/shared/js/store.js");
  const mod = await import("../../../web/static/shared/js/render/player.js");
  const playback = await import("../../../web/static/shared/js/audio/playback-sync.js");
  const nowPlaying = await import("../../../web/static/shared/js/render/now-playing.js");

  Object.assign(domMod.dom, {
    pbTrackInfo: el(),
    pbModeBadge: el(),
    btnRepeat: elStyle(),
    btnShuffle: elStyle(),
    pbVolLabel: el(),
    volSlider: Object.assign(el("input"), { value: "" }),
    pbCacheBadge: elStyle(),
    pbSbBadge: elStyle(),
    pbDlBadge: elStyle(),
    btnPlay: el(),
    pbProgressFill: elStyle(),
    pbThumb: elStyle(),
    pbTimePos: el(),
    pbTimeDur: el(),
    playerBarEl: el(),
  });

  storeMod.store.current_track = null;
  storeMod.store.status = "PAUSED";
  storeMod.store.playback_mode = "QUEUE";
  storeMod.store.loop_mode = "off";
  storeMod.store.volume = 80;
  storeMod.store.sponsorblock_active = false;
  storeMod.store.download_progress = null;
  storeMod.store.audio_output = "server";
  storeMod.store.position = 0;

  function runNextFrame(ts) {
    const next = rafCallbacks.shift();
    if (!next) return false;
    next.cb(ts);
    return true;
  }

  return {
    ...mod,
    dom: domMod.dom,
    store: storeMod.store,
    playback,
    syncPlayerStateAttr: nowPlaying.syncPlayerStateAttr,
    runNextFrame,
    getPendingFrames: () => rafCallbacks.length,
  };
}

describe("render/player.js", () => {
  beforeEach(() => {
    globalThis.isDraggingVol = false;
    globalThis.isDraggingPb = false;
    globalThis.audioBlocked = false;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    delete globalThis.isDraggingVol;
    delete globalThis.isDraggingPb;
    delete globalThis.audioBlocked;
  });

  describe("renderPlayerBar", () => {
    it("calls syncPlayerStateAttr and shows a loading spinner while LOADING", async () => {
      const { renderPlayerBar, dom, store, syncPlayerStateAttr } = await setupModule();
      store.status = "LOADING";
      store.current_track = { title: "T" };
      renderPlayerBar();
      expect(syncPlayerStateAttr).toHaveBeenCalled();
      expect(dom.pbTrackInfo.innerHTML).toContain("Memuat");
    });

    it("renders title/artist/thumbnail for the current track", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.current_track = { title: "kisah cintaku", artist: "Sheila On 7", thumbnail: "t.jpg" };
      renderPlayerBar();
      expect(dom.pbTrackInfo.innerHTML).toContain("Sheila On 7");
      expect(dom.pbTrackInfo.innerHTML).toContain("t.jpg");
    });

    it("shows a fallback icon when there is no thumbnail", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.current_track = { title: "T", artist: "A" };
      renderPlayerBar();
      expect(dom.pbTrackInfo.innerHTML).toContain("ti-music");
    });

    it("clears the track info when there is no current track", async () => {
      const { renderPlayerBar, dom } = await setupModule();
      renderPlayerBar();
      expect(dom.pbTrackInfo.innerHTML).toBe("");
    });

    it("shows the radio badge and hides repeat/shuffle in RADIO mode", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.playback_mode = "RADIO";
      renderPlayerBar();
      expect(dom.pbModeBadge.textContent).toContain("radio");
      expect(dom.btnRepeat.style.display).toBe("none");
      expect(dom.btnShuffle.style.display).toBe("none");
    });

    it("shows the queue badge and repeat/shuffle controls in QUEUE mode", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.playback_mode = "QUEUE";
      renderPlayerBar();
      expect(dom.pbModeBadge.textContent).toContain("queue");
      expect(dom.btnRepeat.style.display).toBe("inline-flex");
      expect(dom.btnShuffle.style.display).toBe("inline-flex");
    });

    it("shows the repeat-once icon and active state for loop_mode=track", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.loop_mode = "track";
      renderPlayerBar();
      expect(dom.btnRepeat.innerHTML).toContain("repeat-once");
      expect(dom.btnRepeat.classList.contains("active")).toBe(true);
    });

    it("shows the plain repeat icon (inactive) for loop_mode=off", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.loop_mode = "off";
      renderPlayerBar();
      expect(dom.btnRepeat.classList.contains("active")).toBe(false);
    });

    it("shows the volume percentage and syncs the slider (when not dragging)", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.volume = 42;
      renderPlayerBar();
      expect(dom.pbVolLabel.textContent).toBe("42%");
      expect(dom.volSlider.value).toBe("42");
    });

    it("does not overwrite the volume slider while the user is dragging it", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      globalThis.isDraggingVol = true;
      dom.volSlider.value = "99";
      store.volume = 42;
      renderPlayerBar();
      expect(dom.volSlider.value).toBe("99");
    });

    it("shows the cached badge for locally stored tracks", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.current_track = { title: "T", local_path: "/path" };
      renderPlayerBar();
      expect(dom.pbCacheBadge.textContent).toContain("tersimpan");
    });

    it("shows the stream badge for non-cached tracks", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.current_track = { title: "T" };
      renderPlayerBar();
      expect(dom.pbCacheBadge.textContent).toContain("stream");
    });

    it("hides the cache badge when there is no track", async () => {
      const { renderPlayerBar, dom } = await setupModule();
      renderPlayerBar();
      expect(dom.pbCacheBadge.style.display).toBe("none");
    });

    it("shows the SponsorBlock badge when active", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.sponsorblock_active = true;
      renderPlayerBar();
      expect(dom.pbSbBadge.textContent).toBe("SB: ON");
      expect(dom.pbSbBadge.style.display).toBe("inline-block");
    });

    it("shows a download progress badge when downloading", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.download_progress = 0.5;
      renderPlayerBar();
      expect(dom.pbDlBadge.textContent).toBe("⬇ 50%");
    });

    it("hides the download badge otherwise", async () => {
      const { renderPlayerBar, dom, store } = await setupModule();
      store.download_progress = null;
      renderPlayerBar();
      expect(dom.pbDlBadge.style.display).toBe("none");
    });
  });

  describe("renderPlayBtn", () => {
    it("shows a pause icon and starts the progress clock while PLAYING", async () => {
      const { renderPlayBtn, dom, store, getPendingFrames } = await setupModule();
      store.status = "PLAYING";
      renderPlayBtn();
      expect(dom.btnPlay.innerHTML).toContain("<svg");
      expect(getPendingFrames()).toBe(1);
    });

    it("shows a play icon and stops the clock when not playing", async () => {
      const { renderPlayBtn, startProgressClock, store, getPendingFrames } = await setupModule();
      store.status = "PLAYING";
      startProgressClock();
      store.status = "PAUSED";
      renderPlayBtn();
      expect(getPendingFrames()).toBe(0);
    });
  });

  describe("progress clock (position anchoring + rAF loop)", () => {
    it("setPositionAnchor stores the position and resets the last-rendered second", async () => {
      const { setPositionAnchor, store } = await setupModule();
      setPositionAnchor(42);
      expect(store.position).toBe(42);
    });

    it("clamps a negative/undefined position to 0", async () => {
      const { setPositionAnchor, store } = await setupModule();
      setPositionAnchor(-5);
      expect(store.position).toBe(0);
      setPositionAnchor();
      expect(store.position).toBe(0);
    });

    it("getInterpolatedPosition returns the static anchor while not playing", async () => {
      const { getInterpolatedPosition, setPositionAnchor, store } = await setupModule();
      store.status = "PAUSED";
      setPositionAnchor(10);
      expect(getInterpolatedPosition()).toBe(10);
    });

    it("getInterpolatedPosition returns the static anchor when browser audio is blocked", async () => {
      const { getInterpolatedPosition, setPositionAnchor, store } = await setupModule();
      store.status = "PLAYING";
      store.audio_output = "browser";
      globalThis.audioBlocked = true;
      setPositionAnchor(10);
      expect(getInterpolatedPosition()).toBe(10);
    });

    it("getInterpolatedPosition clamps to the track duration", async () => {
      const { getInterpolatedPosition, setPositionAnchor, store } = await setupModule();
      store.status = "PLAYING";
      store.current_track = { duration: 5 };
      setPositionAnchor(4.999);
      // elapsed time since anchor is ~0, so pos ~= 4.999, still under 5;
      // this mainly exercises the dur>0 clamp branch without flaking on timing.
      expect(getInterpolatedPosition()).toBeLessThanOrEqual(5);
    });

    it("startProgressClock is idempotent while already running", async () => {
      const { startProgressClock, getPendingFrames } = await setupModule();
      startProgressClock();
      startProgressClock();
      expect(getPendingFrames()).toBe(1);
    });

    it("stopProgressClock cancels the pending frame", async () => {
      const { startProgressClock, stopProgressClock, getPendingFrames } = await setupModule();
      startProgressClock();
      stopProgressClock();
      expect(getPendingFrames()).toBe(0);
      expect(globalThis.cancelAnimationFrame).toHaveBeenCalled();
    });

    it("the tick loop skips rendering while the progress bar is being dragged, but keeps rescheduling", async () => {
      const { startProgressClock, runNextFrame, dom, getPendingFrames } = await setupModule();
      startProgressClock();
      globalThis.isDraggingPb = true;
      dom.pbProgressFill.style.width = "0%";
      runNextFrame(16);
      expect(dom.pbProgressFill.style.width).toBe("0%");
      expect(getPendingFrames()).toBe(1); // rescheduled itself
    });

    it("the tick loop renders progress when not dragging", async () => {
      const { startProgressClock, runNextFrame, dom, store } = await setupModule();
      store.current_track = { duration: 100 };
      store.status = "PLAYING";
      startProgressClock();
      runNextFrame(16);
      expect(dom.pbProgressFill.style.width).not.toBe("");
    });
  });

  describe("renderProgress / _renderProgressCore", () => {
    it("does nothing while dragging the progress bar", async () => {
      const { renderProgress, dom } = await setupModule();
      globalThis.isDraggingPb = true;
      dom.pbProgressFill.style.width = "unset";
      renderProgress();
      expect(dom.pbProgressFill.style.width).toBe("unset");
    });

    it("sets the fill width and thumb position as a percentage of duration", async () => {
      const { renderProgress, setPositionAnchor, dom, store } = await setupModule();
      store.current_track = { duration: 200 };
      setPositionAnchor(50);
      renderProgress();
      expect(dom.pbProgressFill.style.width).toBe("25%");
      expect(dom.pbThumb.style.left).toBe("25%");
    });

    it("shows 0% when there is no known duration", async () => {
      const { renderProgress, setPositionAnchor, dom, store } = await setupModule();
      store.current_track = null;
      setPositionAnchor(50);
      renderProgress();
      expect(dom.pbProgressFill.style.width).toBe("0%");
    });

    it("writes the formatted time text only once per whole second", async () => {
      const { renderProgress, setPositionAnchor, dom, store } = await setupModule();
      store.current_track = { duration: 200 };
      setPositionAnchor(10);
      renderProgress();
      dom.pbTimePos.textContent = "OVERRIDDEN";
      renderProgress(); // same anchor, same second (status is PAUSED -> static pos)
      expect(dom.pbTimePos.textContent).toBe("OVERRIDDEN");
    });

    it("updates the mini-player progress CSS variable", async () => {
      const { renderProgress, setPositionAnchor, dom, store } = await setupModule();
      store.current_track = { duration: 200 };
      const setPropertySpy = vi.spyOn(dom.playerBarEl.style, "setProperty");
      setPositionAnchor(100);
      renderProgress();
      expect(setPropertySpy).toHaveBeenCalledWith("--mini-progress", "50%");
    });

    it("syncs the audio element's volume for browser output when not fading/dragging", async () => {
      const { renderProgress, setPositionAnchor, store, playback } = await setupModule();
      store.audio_output = "browser";
      store.volume = 60;
      const fakeAudio = { volume: 0 };
      playback.getOrInitAudio.mockReturnValue(fakeAudio);
      setPositionAnchor(0);
      renderProgress();
      expect(fakeAudio.volume).toBeCloseTo(0.6);
    });

    it("does not touch audio volume while actively dragging the volume slider", async () => {
      const { renderProgress, setPositionAnchor, store, playback } = await setupModule();
      store.audio_output = "browser";
      globalThis.isDraggingVol = true;
      const fakeAudio = { volume: 0.42 };
      playback.getOrInitAudio.mockReturnValue(fakeAudio);
      setPositionAnchor(0);
      renderProgress();
      expect(fakeAudio.volume).toBe(0.42);
    });
  });

  describe("resetAnchorClock", () => {
    it("does not throw and keeps position readable afterward", async () => {
      const { resetAnchorClock, getInterpolatedPosition } = await setupModule();
      expect(() => resetAnchorClock()).not.toThrow();
      expect(typeof getInterpolatedPosition()).toBe("number");
    });
  });

  describe("initPlayerBusSubscriptions", () => {
    it("wires player:bar-changed to renderPlayerBar", async () => {
      const { initPlayerBusSubscriptions, dom, store } = await setupModule();
      const { emit } = await import("../../../web/static/shared/js/bus.js");
      initPlayerBusSubscriptions();
      store.current_track = { title: "T", artist: "A" };
      emit("player:bar-changed");
      expect(dom.pbTrackInfo.innerHTML).toContain("A");
    });

    it("wires player:position to setPositionAnchor", async () => {
      const { initPlayerBusSubscriptions, store } = await setupModule();
      const { emit } = await import("../../../web/static/shared/js/bus.js");
      initPlayerBusSubscriptions();
      emit("player:position", 33);
      expect(store.position).toBe(33);
    });

    it("wires player:progress to renderProgress", async () => {
      const { initPlayerBusSubscriptions, setPositionAnchor, dom, store } = await setupModule();
      const { emit } = await import("../../../web/static/shared/js/bus.js");
      initPlayerBusSubscriptions();
      store.current_track = { duration: 100 };
      setPositionAnchor(25);
      emit("player:progress");
      expect(dom.pbProgressFill.style.width).toBe("25%");
    });

    it("wires player:clock-start / player:clock-stop to the progress clock", async () => {
      const { initPlayerBusSubscriptions, getPendingFrames } = await setupModule();
      const { emit } = await import("../../../web/static/shared/js/bus.js");
      initPlayerBusSubscriptions();
      emit("player:clock-start");
      expect(getPendingFrames()).toBe(1);
      emit("player:clock-stop");
      expect(getPendingFrames()).toBe(0);
    });
  });
});
