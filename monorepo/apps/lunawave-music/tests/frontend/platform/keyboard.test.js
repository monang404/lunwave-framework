import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

// platform/keyboard.js is an IIFE that attaches a
// `document.addEventListener('keydown', ...)` listener at *import* time,
// permanently, based on the matchMedia('(pointer: fine)') value evaluated
// right then -- the module exports nothing and offers no teardown hook.
//
// To keep each test fully isolated on the shared jsdom `document` (instead
// of leaking one extra permanent listener per test, which both cross-fires
// stale store snapshots into later tests and quietly satisfies/contradicts
// `not.toHaveBeenCalled()` assertions depending on accumulated listener
// parity), we:
//   1. vi.resetModules() before each test so store.js and keyboard.js are
//      re-instantiated fresh (a brand new `store` object every time).
//   2. Spy on document.addEventListener while importing keyboard.js to
//      capture the exact handler it registers (if any), and explicitly
//      remove it in afterEach.
async function freshStore() {
  const mod = await import("../../../web/static/shared/js/store.js");
  return mod.store;
}

async function importKeyboardModule() {
  const addSpy = vi.spyOn(document, "addEventListener");
  await import("../../../web/static/shared/js/platform/keyboard.js");
  const call = addSpy.mock.calls.find((c) => c[0] === "keydown");
  addSpy.mockRestore();
  return call ? call[1] : undefined;
}

let keydownHandler;

describe("platform/keyboard.js", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    if (keydownHandler) {
      document.removeEventListener("keydown", keydownHandler);
      keydownHandler = undefined;
    }
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("registers no behavior on touch devices (pointer: fine not matched)", async () => {
    const store = await freshStore();
    store.userRole = "admin";
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({ matches: false })
    );
    keydownHandler = await importKeyboardModule();
    const { wsSend } = await import("../../../web/static/shared/js/ws.js");

    expect(keydownHandler).toBeUndefined();
    document.dispatchEvent(new KeyboardEvent("keydown", { code: "ArrowRight" }));
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("sends 'next' on ArrowRight for an admin on desktop (pointer: fine)", async () => {
    const store = await freshStore();
    store.userRole = "admin";
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    keydownHandler = await importKeyboardModule();
    const { wsSend } = await import("../../../web/static/shared/js/ws.js");

    document.dispatchEvent(new KeyboardEvent("keydown", { code: "ArrowRight" }));
    expect(wsSend).toHaveBeenCalledWith("next");
  });

  it("sends 'prev' on ArrowLeft for an admin on desktop", async () => {
    const store = await freshStore();
    store.userRole = "admin";
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    keydownHandler = await importKeyboardModule();
    const { wsSend } = await import("../../../web/static/shared/js/ws.js");

    document.dispatchEvent(new KeyboardEvent("keydown", { code: "ArrowLeft" }));
    expect(wsSend).toHaveBeenCalledWith("prev");
  });

  it("ignores arrow keys for a non-admin user", async () => {
    const store = await freshStore();
    store.userRole = "client";
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    keydownHandler = await importKeyboardModule();
    const { wsSend } = await import("../../../web/static/shared/js/ws.js");

    document.dispatchEvent(new KeyboardEvent("keydown", { code: "ArrowRight" }));
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("ignores arrow keys while typing inside an input/textarea", async () => {
    const store = await freshStore();
    store.userRole = "admin";
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    keydownHandler = await importKeyboardModule();
    const { wsSend } = await import("../../../web/static/shared/js/ws.js");

    const input = document.createElement("input");
    document.body.appendChild(input);
    const event = new KeyboardEvent("keydown", { code: "ArrowRight" });
    Object.defineProperty(event, "target", { value: input });
    document.dispatchEvent(event);

    expect(wsSend).not.toHaveBeenCalled();
    input.remove();
  });
});
