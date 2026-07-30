import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// platform/viewport.js is an IIFE that wires up a listener at import time,
// based on whatever `window.visualViewport` is at that moment. We control
// that via vi.stubGlobal + dynamic import + vi.resetModules() so each test
// gets a fresh evaluation of the IIFE.
describe("platform/viewport.js", () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = '<div id="app"></div>';
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not throw when window.visualViewport is unavailable", async () => {
    vi.stubGlobal("visualViewport", undefined);
    await expect(
      import("../../../web/static/shared/js/platform/viewport.js")
    ).resolves.toBeDefined();
  });

  it("resizes #app and sets safe-area CSS vars on visualViewport resize", async () => {
    const listeners = {};
    const fakeViewport = {
      height: 555,
      addEventListener: vi.fn((evt, cb) => {
        listeners[evt] = cb;
      }),
    };
    vi.stubGlobal("visualViewport", fakeViewport);

    await import("../../../web/static/shared/js/platform/viewport.js");

    expect(fakeViewport.addEventListener).toHaveBeenCalledWith("resize", expect.any(Function));

    const setPropertySpy = vi.spyOn(document.documentElement.style, "setProperty");
    listeners.resize();

    const app = document.getElementById("app");
    expect(app.style.height).toBe("555px");
    expect(setPropertySpy).toHaveBeenCalledWith("--sat", "env(safe-area-inset-top)");
    expect(setPropertySpy).toHaveBeenCalledWith("--sab", "env(safe-area-inset-bottom)");
  });

  it("does nothing when #app is missing from the DOM on resize", async () => {
    document.body.innerHTML = "";
    const listeners = {};
    const fakeViewport = {
      height: 400,
      addEventListener: vi.fn((evt, cb) => {
        listeners[evt] = cb;
      }),
    };
    vi.stubGlobal("visualViewport", fakeViewport);

    await import("../../../web/static/shared/js/platform/viewport.js");
    expect(() => listeners.resize()).not.toThrow();
  });
});
