import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { store } from "../../../web/static/shared/js/store.js";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  unlockBrowserAudio: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/render/toast.js", () => ({
  showLogToast: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

function makeTouchEvent(type, { touches = [], changedTouches = [], target } = {}) {
  const event = new Event(type, { bubbles: true });
  Object.defineProperty(event, "touches", { value: touches });
  Object.defineProperty(event, "changedTouches", { value: changedTouches });
  if (target) Object.defineProperty(event, "target", { value: target });
  return event;
}

// Same ordering caveat as platform/keyboard.test.js: platform/touch.js
// attaches document-level listeners at import time with no teardown, so we
// import it once via a top-level await here and reuse it across `it`
// blocks, resetting mocks/store between tests instead of re-importing.
let unlockBrowserAudio;
let showLogToast;
let wsSend;

beforeEach(async () => {
  vi.clearAllMocks();
  store.userRole = "admin";
  ({ unlockBrowserAudio } = await import(
    "../../../web/static/shared/js/audio/playback-sync.js"
  ));
  ({ showLogToast } = await import("../../../web/static/shared/js/render/toast.js"));
  ({ wsSend } = await import("../../../web/static/shared/js/ws.js"));
});

beforeAll(async () => {
  await import("../../../web/static/shared/js/platform/touch.js");
});

describe("platform/touch.js", () => {
  it("unlocks browser audio on touchstart", () => {
    document.dispatchEvent(makeTouchEvent("touchstart", { touches: [{ screenX: 0, screenY: 0 }] }));
    expect(unlockBrowserAudio).toHaveBeenCalled();
  });

  it("sends 'next' when admin swipes left far enough", () => {
    document.dispatchEvent(
      makeTouchEvent("touchstart", { touches: [{ screenX: 300, screenY: 100 }] })
    );
    document.dispatchEvent(
      makeTouchEvent("touchend", {
        changedTouches: [{ screenX: 100, screenY: 100 }],
        target: document.body,
      })
    );
    expect(wsSend).toHaveBeenCalledWith("next");
  });

  it("sends 'prev' when admin swipes right far enough", () => {
    document.dispatchEvent(
      makeTouchEvent("touchstart", { touches: [{ screenX: 100, screenY: 100 }] })
    );
    document.dispatchEvent(
      makeTouchEvent("touchend", {
        changedTouches: [{ screenX: 300, screenY: 100 }],
        target: document.body,
      })
    );
    expect(wsSend).toHaveBeenCalledWith("prev");
  });

  it("does nothing for a short swipe below the 80px threshold", () => {
    document.dispatchEvent(
      makeTouchEvent("touchstart", { touches: [{ screenX: 100, screenY: 100 }] })
    );
    document.dispatchEvent(
      makeTouchEvent("touchend", {
        changedTouches: [{ screenX: 120, screenY: 100 }],
        target: document.body,
      })
    );
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("does nothing when vertical movement dominates the horizontal swipe", () => {
    document.dispatchEvent(
      makeTouchEvent("touchstart", { touches: [{ screenX: 100, screenY: 100 }] })
    );
    document.dispatchEvent(
      makeTouchEvent("touchend", {
        changedTouches: [{ screenX: 250, screenY: 400 }],
        target: document.body,
      })
    );
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("shows a toast instead of sending a command for a non-admin swipe", () => {
    store.userRole = "client";
    document.dispatchEvent(
      makeTouchEvent("touchstart", { touches: [{ screenX: 300, screenY: 100 }] })
    );
    document.dispatchEvent(
      makeTouchEvent("touchend", {
        changedTouches: [{ screenX: 100, screenY: 100 }],
        target: document.body,
      })
    );
    expect(wsSend).not.toHaveBeenCalled();
    expect(showLogToast).toHaveBeenCalledWith("Hanya admin yang bisa memutar musik");
  });

  it("ignores touchend on interactive elements like buttons", () => {
    const button = document.createElement("button");
    document.body.appendChild(button);

    document.dispatchEvent(
      makeTouchEvent("touchstart", { touches: [{ screenX: 300, screenY: 100 }] })
    );
    document.dispatchEvent(
      makeTouchEvent("touchend", {
        changedTouches: [{ screenX: 100, screenY: 100 }],
        target: button,
      })
    );
    expect(wsSend).not.toHaveBeenCalled();
    button.remove();
  });
});
