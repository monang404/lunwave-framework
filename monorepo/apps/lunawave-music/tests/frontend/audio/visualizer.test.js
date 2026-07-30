import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// playback-sync.js exports `analyser`/`dataArray` as mutable module-scope
// bindings that get filled in later by _initAnalyser(). We mock the module
// with getters backed by a small mutable state object + setter helpers, so
// tests can flip analyser availability between "not yet initialized" (null)
// and "ready" without needing the real Web Audio API (unavailable in jsdom).
//
// IMPORTANT: vi.mock factories are NOT re-invoked by vi.resetModules() --
// the returned module object (and its closure state) is a singleton for
// the whole test file. So every test must explicitly reset analyser/
// dataArray back to null itself; otherwise a later test silently inherits
// whatever a previous test last set.
vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => {
  const state = { analyser: null, dataArray: null };
  return {
    get analyser() { return state.analyser; },
    get dataArray() { return state.dataArray; },
    __setAnalyser: (a) => { state.analyser = a; },
    __setDataArray: (d) => { state.dataArray = d; },
  };
});

function el(tag = "div") {
  return document.createElement(tag);
}

async function setupModule() {
  // _fakeBeatInterval / _vizRafId are module-scope singletons with no
  // reset hook, so each test gets a fresh module instance.
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
  const playback = await import("../../../web/static/shared/js/audio/playback-sync.js");
  playback.__setAnalyser(null);
  playback.__setDataArray(null);
  const mod = await import("../../../web/static/shared/js/audio/visualizer.js");

  Object.assign(domMod.dom, {
    tabHome: el(), // use the real CSSStyleDeclaration; read via getPropertyValue
    vinylRecord: el(),
  });

  storeMod.store.status = "PLAYING";
  storeMod.store.userRole = "client";
  storeMod.store.audio_output = "browser";
  Object.defineProperty(document, "hidden", { value: false, configurable: true });

  function runNextFrame(ts) {
    const next = rafCallbacks.shift();
    if (!next) return false;
    next.cb(ts);
    return true;
  }
  function cssVar(name) {
    return domMod.dom.tabHome.style.getPropertyValue(name);
  }

  return {
    ...mod,
    dom: domMod.dom,
    store: storeMod.store,
    setAnalyser: playback.__setAnalyser,
    setDataArray: playback.__setDataArray,
    runNextFrame,
    getPendingFrames: () => rafCallbacks.length,
    cssVar,
  };
}

describe("audio/visualizer.js", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  describe("initVisualizer", () => {
    it("starts the fake beat loop when there is no analyser", async () => {
      const { initVisualizer, cssVar } = await setupModule();
      initVisualizer();
      expect(cssVar("--beat-glow-opacity")).toBe("0.5");
    });

    it("starts the real visualizer rAF loop when an analyser is available", async () => {
      const { initVisualizer, setAnalyser, setDataArray, getPendingFrames } = await setupModule();
      setDataArray(new Uint8Array(32));
      setAnalyser({ getByteFrequencyData: vi.fn() });
      initVisualizer();
      expect(getPendingFrames()).toBe(1);
    });
  });

  describe("startFakeBeatLoop", () => {
    it("is idempotent while already running", async () => {
      const { startFakeBeatLoop } = await setupModule();
      const setIntervalSpy = vi.spyOn(globalThis, "setInterval");
      startFakeBeatLoop();
      startFakeBeatLoop();
      expect(setIntervalSpy).toHaveBeenCalledTimes(1);
    });

    it("pulses the glow variables on each beat, then settles after 150ms", async () => {
      const { startFakeBeatLoop, cssVar } = await setupModule();
      startFakeBeatLoop();
      expect(cssVar("--beat-glow-opacity")).toBe("0.5");
      vi.advanceTimersByTime(150);
      expect(cssVar("--beat-glow-opacity")).toBe("0.4");
    });

    it("repeats every 500ms while playing", async () => {
      const { startFakeBeatLoop, dom, cssVar } = await setupModule();
      startFakeBeatLoop();
      vi.advanceTimersByTime(150);
      dom.tabHome.style.removeProperty("--beat-glow-opacity");
      vi.advanceTimersByTime(350); // total 500ms -> next beat() tick
      expect(cssVar("--beat-glow-opacity")).toBe("0.5");
    });

    it("clears the glow and stops the interval once playback ends", async () => {
      const { startFakeBeatLoop, store, cssVar } = await setupModule();
      startFakeBeatLoop();
      store.status = "PAUSED";
      const clearSpy = vi.spyOn(globalThis, "clearInterval");
      vi.advanceTimersByTime(500);
      expect(clearSpy).toHaveBeenCalled();
      expect(cssVar("--beat-glow-opacity")).toBe("");
    });

    it("does not throw when dom.tabHome is missing", async () => {
      const { startFakeBeatLoop, dom } = await setupModule();
      dom.tabHome = null;
      expect(() => startFakeBeatLoop()).not.toThrow();
    });
  });

  describe("startVisualizerLoop (via initVisualizer)", () => {
    it("does nothing when dom.vinylRecord is missing", async () => {
      const { initVisualizer, setAnalyser, setDataArray, dom, getPendingFrames } = await setupModule();
      setDataArray(new Uint8Array(32));
      setAnalyser({ getByteFrequencyData: vi.fn() });
      dom.vinylRecord = null;
      initVisualizer();
      expect(getPendingFrames()).toBe(0);
    });

    it("stops and clears the glow when the user is not on browser output", async () => {
      const { initVisualizer, setAnalyser, setDataArray, dom, store, getPendingFrames, cssVar } =
        await setupModule();
      setDataArray(new Uint8Array(32));
      setAnalyser({ getByteFrequencyData: vi.fn() });
      store.userRole = "admin";
      store.audio_output = "server";
      dom.tabHome.style.setProperty("--beat-glow-opacity", "0.9");
      initVisualizer();
      expect(getPendingFrames()).toBe(0);
      expect(cssVar("--beat-glow-opacity")).toBe("");
    });

    it("stops when not playing", async () => {
      const { initVisualizer, setAnalyser, setDataArray, store, getPendingFrames } = await setupModule();
      setDataArray(new Uint8Array(32));
      setAnalyser({ getByteFrequencyData: vi.fn() });
      store.status = "PAUSED";
      initVisualizer();
      expect(getPendingFrames()).toBe(0);
    });

    it("stops when the document/tab is hidden", async () => {
      const { initVisualizer, setAnalyser, setDataArray, getPendingFrames } = await setupModule();
      setDataArray(new Uint8Array(32));
      setAnalyser({ getByteFrequencyData: vi.fn() });
      Object.defineProperty(document, "hidden", { value: true, configurable: true });
      initVisualizer();
      expect(getPendingFrames()).toBe(0);
    });

    it("reads bass frequency data and sets CSS variables proportional to bass energy", async () => {
      const { initVisualizer, setAnalyser, setDataArray, cssVar } = await setupModule();
      setDataArray(new Uint8Array(32).fill(255)); // max bass energy
      setAnalyser({ getByteFrequencyData: vi.fn() });
      initVisualizer();
      // Loop scheduled one frame per call: first call happens synchronously
      // inside initVisualizer -> startVisualizerLoop, already rendered once.
      expect(cssVar("--beat-glow-opacity")).toBe("0.600");
      expect(cssVar("--beat-bg-brightness")).toBe("0.300");
      expect(cssVar("--beat-glow-transition")).toBe("0.2s");
    });

    it("uses the slower transition when bass energy is low", async () => {
      const { initVisualizer, setAnalyser, setDataArray, cssVar } = await setupModule();
      setDataArray(new Uint8Array(32).fill(0));
      setAnalyser({ getByteFrequencyData: vi.fn() });
      initVisualizer();
      expect(cssVar("--beat-glow-transition")).toBe("0.4s");
    });

    it("keeps rescheduling itself via requestAnimationFrame while conditions hold", async () => {
      const { initVisualizer, setAnalyser, setDataArray, runNextFrame, getPendingFrames } =
        await setupModule();
      setDataArray(new Uint8Array(32).fill(10));
      setAnalyser({ getByteFrequencyData: vi.fn() });
      initVisualizer();
      expect(getPendingFrames()).toBe(1);
      runNextFrame(16);
      expect(getPendingFrames()).toBe(1);
    });
  });

  describe("resumeVisualizerLoop", () => {
    it("restarts the loop when it isn't running and an analyser exists", async () => {
      const { resumeVisualizerLoop, setAnalyser, setDataArray, getPendingFrames } =
        await setupModule();
      setDataArray(new Uint8Array(32));
      setAnalyser({ getByteFrequencyData: vi.fn() });
      resumeVisualizerLoop();
      expect(getPendingFrames()).toBe(1);
    });

    it("does nothing when there is no analyser", async () => {
      const { resumeVisualizerLoop, getPendingFrames } = await setupModule();
      resumeVisualizerLoop();
      expect(getPendingFrames()).toBe(0);
    });

    it("does not double-schedule when the loop is already running", async () => {
      const { initVisualizer, resumeVisualizerLoop, setAnalyser, setDataArray, getPendingFrames } =
        await setupModule();
      setDataArray(new Uint8Array(32));
      setAnalyser({ getByteFrequencyData: vi.fn() });
      initVisualizer();
      resumeVisualizerLoop();
      expect(getPendingFrames()).toBe(1);
    });
  });
});
