import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  unlockBrowserAudio: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/render/navigation.js", () => ({
  switchTab: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/settings-events.js", () => ({
  closeMainOverlay: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import { initKeyboardShortcutEvents } from "../../../web/static/shared/js/events/keyboard-shortcut-events.js";
import { unlockBrowserAudio } from "../../../web/static/shared/js/audio/playback-sync.js";
import { switchTab } from "../../../web/static/shared/js/render/navigation.js";
import { closeMainOverlay } from "../../../web/static/shared/js/events/settings-events.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

function press(key, target) {
  const event = new KeyboardEvent("keydown", { key, cancelable: true, bubbles: true });
  if (target) Object.defineProperty(event, "target", { value: target });
  document.dispatchEvent(event);
  return event;
}

// initKeyboardShortcutEvents() attaches a permanent `document.addEventListener
// ('keydown', ...)` with no teardown hook. In production it's only ever
// called once at app startup, but calling it fresh in every beforeEach here
// would stack up one extra permanent listener per test -- e.g. by the time
// a later test presses 'l' (a toggle), it would fire N accumulated
// listeners for the same keydown, and an even N cancels the toggle back to
// "closed". So we capture the exact handler each call registers and
// explicitly remove it afterward, keeping every test isolated to a single
// active listener.
let keydownHandler;

describe("events/keyboard-shortcut-events.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
    document.body.focus();

    Object.assign(dom, {
      lyricsSheet: Object.assign(document.createElement("div"), {}),
      mainOverlay: Object.assign(document.createElement("div"), {}),
      helpSheet: Object.assign(document.createElement("div"), {}),
      settingsSheet: Object.assign(document.createElement("div"), {}),
    });

    Object.assign(store, {
      userRole: "admin",
      status: "PAUSED",
      audio_output: "browser",
      playback_mode: "QUEUE",
    });

    const addSpy = vi.spyOn(document, "addEventListener");
    initKeyboardShortcutEvents();
    const call = addSpy.mock.calls.find((c) => c[0] === "keydown");
    keydownHandler = call ? call[1] : undefined;
    addSpy.mockRestore();
  });

  afterEach(() => {
    if (keydownHandler) {
      document.removeEventListener("keydown", keydownHandler);
      keydownHandler = undefined;
    }
  });

  it("Space toggles playback for admin and unlocks browser audio when paused", () => {
    press(" ");
    expect(unlockBrowserAudio).toHaveBeenCalledWith(true);
    expect(wsSend).toHaveBeenCalledWith("toggle_pause");
  });

  it("Space does not unlock audio again when already PLAYING", () => {
    store.status = "PLAYING";
    press(" ");
    expect(unlockBrowserAudio).not.toHaveBeenCalled();
    expect(wsSend).toHaveBeenCalledWith("toggle_pause");
  });

  it("Space is ignored for a non-admin", () => {
    store.userRole = "client";
    press(" ");
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("'n'/'N' sends next", () => {
    press("n");
    expect(wsSend).toHaveBeenCalledWith("next");
    wsSend.mockClear();
    press("N");
    expect(wsSend).toHaveBeenCalledWith("next");
  });

  it("'b'/'B' sends prev", () => {
    press("b");
    expect(wsSend).toHaveBeenCalledWith("prev");
  });

  it("'s'/'S' sends stop", () => {
    press("s");
    expect(wsSend).toHaveBeenCalledWith("stop");
  });

  it("ArrowUp/ArrowDown send volume_up/volume_down", () => {
    press("ArrowUp");
    expect(wsSend).toHaveBeenCalledWith("volume_up");
    press("ArrowDown");
    expect(wsSend).toHaveBeenCalledWith("volume_down");
  });

  it("'m'/'M' sends download", () => {
    press("m");
    expect(wsSend).toHaveBeenCalledWith("download");
  });

  it("'r' toggles playback_mode QUEUE -> RADIO, unless status is LOADING", () => {
    store.playback_mode = "QUEUE";
    press("r");
    expect(wsSend).toHaveBeenCalledWith("set_mode", { mode: "RADIO" });

    wsSend.mockClear();
    store.status = "LOADING";
    press("r");
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("'l' opens the lyrics sheet + overlay when closed", () => {
    press("l");
    expect(dom.lyricsSheet.classList.contains("open")).toBe(true);
    expect(dom.mainOverlay.classList.contains("open")).toBe(true);
  });

  it("'l' closes the lyrics sheet when already open", () => {
    dom.lyricsSheet.classList.add("open");
    press("l");
    expect(dom.lyricsSheet.classList.contains("open")).toBe(false);
    expect(closeMainOverlay).toHaveBeenCalled();
  });

  it("'/' switches to the search tab and prevents default", () => {
    const event = press("/");
    expect(switchTab).toHaveBeenCalledWith("search");
    expect(event.defaultPrevented).toBe(true);
  });

  it("'?' toggles the help sheet", () => {
    press("?");
    expect(dom.helpSheet.classList.contains("open")).toBe(true);
    press("?");
    expect(dom.helpSheet.classList.contains("open")).toBe(false);
  });

  it("Escape closes search action-modal, help/settings/lyrics sheets, and overlay", () => {
    dom.helpSheet.classList.add("open");
    dom.settingsSheet.classList.add("open");
    dom.lyricsSheet.classList.add("open");
    press("Escape");
    expect(dom.helpSheet.classList.contains("open")).toBe(false);
    expect(dom.settingsSheet.classList.contains("open")).toBe(false);
    expect(dom.lyricsSheet.classList.contains("open")).toBe(false);
    expect(closeMainOverlay).toHaveBeenCalled();
  });

  it("ignores shortcuts (except Escape-blur) while typing in an input", () => {
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();
    press("n", input);
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("blurs the active input on Escape while typing", () => {
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();
    const blurSpy = vi.spyOn(input, "blur");
    press("Escape", input);
    expect(blurSpy).toHaveBeenCalled();
  });
});
