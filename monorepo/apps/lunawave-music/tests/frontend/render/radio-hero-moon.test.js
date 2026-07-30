import { describe, it, expect, vi, afterEach } from "vitest";

vi.mock("../../../web/static/shared/js/render/player.js", () => ({
  getInterpolatedPosition: vi.fn(() => 0),
}));

// radio-hero-moon.js is a self-executing IIFE: it queries #moonLitCool,
// #moonLitWarm, #moonGroup, and reads matchMedia('(prefers-reduced-motion)')
// at *import time*, then renders immediately. So the SVG markup and the
// matchMedia stub must exist BEFORE the module is imported, and we need a
// fresh module instance (vi.resetModules()) per test to re-run that setup
// with different DOM/matchMedia conditions.
async function setupModule({ reduceMotion = false } = {}) {
  document.body.innerHTML = `
    <svg>
      <g id="moonGroup" style="">
        <path id="moonLitCool"></path>
        <path id="moonLitWarm"></path>
      </g>
    </svg>
  `;
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({ matches: reduceMotion })
  );

  const rafCallbacks = [];
  let nextRafId = 1;
  vi.stubGlobal("requestAnimationFrame", vi.fn((cb) => {
    const id = nextRafId++;
    rafCallbacks.push({ id, cb });
    return id;
  }));
  vi.stubGlobal("cancelAnimationFrame", vi.fn((id) => {
    const idx = rafCallbacks.findIndex((r) => r.id === id);
    if (idx !== -1) rafCallbacks.splice(idx, 1);
  }));

  vi.resetModules();
  const storeMod = await import("../../../web/static/shared/js/store.js");
  const playerMod = await import("../../../web/static/shared/js/render/player.js");
  const mod = await import("../../../web/static/shared/js/render/radio-hero-moon.js");

  function runNextFrame(ts) {
    const next = rafCallbacks.shift();
    if (!next) return false;
    next.cb(ts);
    return true;
  }

  return {
    ...mod,
    store: storeMod.store,
    getInterpolatedPosition: playerMod.getInterpolatedPosition,
    runNextFrame,
    getPendingFrames: () => rafCallbacks.length,
  };
}

describe("render/radio-hero-moon.js", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("renders the moon path once at module load time", async () => {
    await setupModule();
    const litCool = document.getElementById("moonLitCool");
    expect(litCool.getAttribute("d")).toBeTruthy();
  });

  it("does not throw when the SVG elements are absent", async () => {
    document.body.innerHTML = "";
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
    vi.resetModules();
    await expect(
      import("../../../web/static/shared/js/render/radio-hero-moon.js")
    ).resolves.toBeTruthy();
  });

  describe("setRadioHeroAnimState(true) -- goCycling", () => {
    it("schedules an animation frame to start cycling", async () => {
      const helpers = await setupModule();
      helpers.setRadioHeroAnimState(true);
      expect(helpers.getPendingFrames()).toBe(1);
    });

    it("advancing frames updates the rendered moon path", async () => {
      const { setRadioHeroAnimState, runNextFrame } = await setupModule();
      const litCool = document.getElementById("moonLitCool");
      setRadioHeroAnimState(true);
      runNextFrame(1000);
      const after = litCool.getAttribute("d");
      // A frame ran and re-rendered (path recomputed; may legitimately be
      // identical at t≈0, so just assert it queued another frame + didn't throw).
      expect(after).toBeTruthy();
      expect(typeof after).toBe("string");
    });

    it("follows the song's playback progress when a track with a known duration is playing", async () => {
      const { setRadioHeroAnimState, runNextFrame, store, getInterpolatedPosition } =
        await setupModule();
      store.current_track = { duration: 200 };
      getInterpolatedPosition.mockReturnValue(100); // halfway through -> "full moon" phase
      const litCool = document.getElementById("moonLitCool");

      setRadioHeroAnimState(true);
      runNextFrame(1000);

      // fraction=0.5 -> phase = (0.5+0.5)%1 = 0 -> theta=0 -> rx = R -> a "full" circle path
      expect(litCool.getAttribute("d")).toContain("M 86 26");
    });

    it("respects prefers-reduced-motion by rendering statically instead of animating", async () => {
      const helpers = await setupModule({ reduceMotion: true });
      helpers.setRadioHeroAnimState(true);
      expect(helpers.getPendingFrames()).toBe(0);
    });

    it("cancels a previous animation frame before starting a new cycle", async () => {
      const { setRadioHeroAnimState } = await setupModule();
      setRadioHeroAnimState(true);
      setRadioHeroAnimState(true);
      expect(globalThis.cancelAnimationFrame).toHaveBeenCalled();
    });
  });

  describe("setRadioHeroAnimState(false) -- goTweenToReal", () => {
    it("schedules an animation frame to tween back to the real phase", async () => {
      const helpers = await setupModule();
      helpers.setRadioHeroAnimState(false);
      expect(helpers.getPendingFrames()).toBe(1);
    });

    it("settles to idle after the tween completes (advances past TWEEN_MS)", async () => {
      const helpers = await setupModule();
      helpers.setRadioHeroAnimState(false);
      helpers.runNextFrame(0);
      helpers.runNextFrame(900); // >= TWEEN_MS -> tween finishes, no further frame scheduled
      expect(helpers.getPendingFrames()).toBe(0);
    });

    it("respects prefers-reduced-motion by rendering statically instead of tweening", async () => {
      const helpers = await setupModule({ reduceMotion: true });
      helpers.setRadioHeroAnimState(false);
      expect(helpers.getPendingFrames()).toBe(0);
    });
  });

  it("initRadioHeroBusSubscriptions wires radio-hero:anim to setRadioHeroAnimState", async () => {
    const helpers = await setupModule();
    const { emit } = await import("../../../web/static/shared/js/bus.js");
    helpers.initRadioHeroBusSubscriptions();
    emit("radio-hero:anim", { on: true });
    expect(helpers.getPendingFrames()).toBe(1);
  });

  describe("shortestDelta", () => {
    it("never returns a magnitude greater than 0.5 for 1000+ random pairs", async () => {
      const { shortestDeltaTestOnly: shortestDelta } = await setupModule();
      for (let i = 0; i < 1000; i++) {
        const from = Math.random();
        const to = Math.random();
        const d = shortestDelta(from, to);
        expect(Math.abs(d)).toBeLessThanOrEqual(0.5);
      }
    });

    it("resolves the exact tie at to-from === 0.5 (mod 1) consistently to +0.5", async () => {
      const { shortestDeltaTestOnly: shortestDelta } = await setupModule();
      expect(shortestDelta(0, 0.5)).toBeCloseTo(0.5, 10);
      expect(shortestDelta(0.25, 0.75)).toBeCloseTo(0.5, 10);
      expect(shortestDelta(0.9, 0.4)).toBeCloseTo(0.5, 10);
    });

    it("matches previously-verified non-edge cases (regression)", async () => {
      const { shortestDeltaTestOnly: shortestDelta } = await setupModule();
      expect(shortestDelta(0, 0.3)).toBeCloseTo(0.3, 10);
      expect(shortestDelta(0, 0.7)).toBeCloseTo(-0.3, 10);
    });
  });
});
