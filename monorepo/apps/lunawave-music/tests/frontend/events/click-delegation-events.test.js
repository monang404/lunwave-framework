import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { store } from "../../../web/static/shared/js/store.js";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  unlockBrowserAudio: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/bus.js", () => ({ emit: vi.fn() }));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import { initClickDelegationEvents } from "../../../web/static/shared/js/events/click-delegation-events.js";
import { unlockBrowserAudio } from "../../../web/static/shared/js/audio/playback-sync.js";
import { emit } from "../../../web/static/shared/js/bus.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

// initClickDelegationEvents() attaches permanent document-level 'click' and
// 'keydown' listeners with no teardown hook. We capture exactly what it
// registers each test and remove it afterward so tests stay isolated.
let registered = [];

function captureAndInit() {
  const addSpy = vi.spyOn(document, "addEventListener");
  initClickDelegationEvents();
  registered = addSpy.mock.calls.map(([type, handler, options]) => [type, handler, options]);
  addSpy.mockRestore();
}

function click(el) {
  el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
}

describe("events/click-delegation-events.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
    Object.assign(store, {
      userRole: "admin",
      audio_output: "browser",
      discover_recent: [],
      discover_cached: [],
      queue: [],
    });
    captureAndInit();
  });

  afterEach(() => {
    for (const [type, handler, options] of registered) {
      document.removeEventListener(type, handler, options);
    }
    registered = [];
  });

  describe("click on .sr-more-btn", () => {
    it("opens the action modal with the parsed track and does not activate the row", () => {
      document.body.innerHTML = `
        <div class="sr-item" data-track-str='{"video_id":"v1"}'>
          <button class="sr-more-btn"></button>
        </div>
      `;
      click(document.querySelector(".sr-more-btn"));

      expect(emit).toHaveBeenCalledWith("search:action-modal-open", { video_id: "v1" });
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("does nothing if the parent .sr-item has no track data", () => {
      document.body.innerHTML = `
        <div class="sr-item"><button class="sr-more-btn"></button></div>
      `;
      click(document.querySelector(".sr-more-btn"));
      expect(emit).not.toHaveBeenCalled();
    });

    it("swallows JSON parse errors from a malformed track string", () => {
      document.body.innerHTML = `
        <div class="sr-item" data-track-str="not-json">
          <button class="sr-more-btn"></button>
        </div>
      `;
      const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      expect(() => click(document.querySelector(".sr-more-btn"))).not.toThrow();
      expect(errSpy).toHaveBeenCalled();
      expect(emit).not.toHaveBeenCalled();
    });
  });

  describe("click on .sr-item (play track)", () => {
    it("plays the track for admins, unlocking browser audio first", () => {
      document.body.innerHTML = `<div class="sr-item" data-track-str='{"video_id":"v2"}'>row</div>`;
      click(document.querySelector(".sr-item"));

      expect(unlockBrowserAudio).toHaveBeenCalledWith(true);
      expect(wsSend).toHaveBeenCalledWith("play_track", { video_id: "v2" });
    });

    it("does not unlock audio when output is not browser", () => {
      store.audio_output = "server";
      document.body.innerHTML = `<div class="sr-item" data-track-str='{"video_id":"v2"}'>row</div>`;
      click(document.querySelector(".sr-item"));

      expect(unlockBrowserAudio).not.toHaveBeenCalled();
      expect(wsSend).toHaveBeenCalledWith("play_track", { video_id: "v2" });
    });

    it("shows a toast instead of playing for non-admins", () => {
      store.userRole = "client";
      document.body.innerHTML = `<div class="sr-item" data-track-str='{"video_id":"v2"}'>row</div>`;
      click(document.querySelector(".sr-item"));

      expect(wsSend).not.toHaveBeenCalled();
      expect(emit).toHaveBeenCalledWith("toast:log", {
        message: "Hanya admin yang bisa memutar musik",
      });
    });

    it("falls back to data-search-track-str when data-track-str is absent", () => {
      document.body.innerHTML = `<div class="sr-item" data-search-track-str='{"video_id":"v3"}'>row</div>`;
      click(document.querySelector(".sr-item"));
      expect(wsSend).toHaveBeenCalledWith("play_track", { video_id: "v3" });
    });

    it("does nothing when the item has no track data at all", () => {
      document.body.innerHTML = `<div class="sr-item">row</div>`;
      click(document.querySelector(".sr-item"));
      expect(wsSend).not.toHaveBeenCalled();
      expect(emit).not.toHaveBeenCalled();
    });
  });

  describe("click on .disc-card/.fav-card/.search-result-item", () => {
    it("opens the action modal using the track's own embedded search-track-str", () => {
      document.body.innerHTML = `
        <div class="search-result-item" data-vid="v4" data-search-track-str='{"video_id":"v4","title":"T"}'></div>
      `;
      click(document.querySelector(".search-result-item"));
      expect(emit).toHaveBeenCalledWith("search:action-modal-open", { video_id: "v4", title: "T" });
    });

    it("looks up the track by video_id across discover_recent/discover_cached/queue", () => {
      store.discover_cached = [{ video_id: "v5", title: "Cached Track" }];
      document.body.innerHTML = `<div class="disc-card" data-vid="v5"></div>`;
      click(document.querySelector(".disc-card"));
      expect(emit).toHaveBeenCalledWith("search:action-modal-open", {
        video_id: "v5",
        title: "Cached Track",
      });
    });

    it("does not emit when no matching track is found anywhere", () => {
      document.body.innerHTML = `<div class="fav-card" data-vid="unknown"></div>`;
      click(document.querySelector(".fav-card"));
      expect(emit).not.toHaveBeenCalled();
    });

    it("ignores cards without a data-vid attribute", () => {
      document.body.innerHTML = `<div class="disc-card"></div>`;
      click(document.querySelector(".disc-card"));
      expect(emit).not.toHaveBeenCalled();
    });
  });

  it("does nothing for clicks that hit none of the delegated targets", () => {
    document.body.innerHTML = `<div id="plain">hello</div>`;
    click(document.getElementById("plain"));
    expect(emit).not.toHaveBeenCalled();
    expect(wsSend).not.toHaveBeenCalled();
  });

  describe("keyboard activation (Enter/Space) on .sr-item", () => {
    it("activates the track on Enter and prevents default", () => {
      document.body.innerHTML = `<div class="sr-item" data-track-str='{"video_id":"v6"}'>row</div>`;
      const event = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true });
      const preventSpy = vi.spyOn(event, "preventDefault");
      Object.defineProperty(event, "target", { value: document.querySelector(".sr-item") });

      document.dispatchEvent(event);

      expect(preventSpy).toHaveBeenCalled();
      expect(wsSend).toHaveBeenCalledWith("play_track", { video_id: "v6" });
    });

    it("activates the track on Space", () => {
      document.body.innerHTML = `<div class="sr-item" data-track-str='{"video_id":"v7"}'>row</div>`;
      const event = new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true });
      Object.defineProperty(event, "target", { value: document.querySelector(".sr-item") });

      document.dispatchEvent(event);
      expect(wsSend).toHaveBeenCalledWith("play_track", { video_id: "v7" });
    });

    it("ignores other keys", () => {
      document.body.innerHTML = `<div class="sr-item" data-track-str='{"video_id":"v8"}'>row</div>`;
      const event = new KeyboardEvent("keydown", { key: "a", bubbles: true, cancelable: true });
      Object.defineProperty(event, "target", { value: document.querySelector(".sr-item") });

      document.dispatchEvent(event);
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("does nothing when Enter is pressed outside a .sr-item", () => {
      document.body.innerHTML = `<div id="plain">hello</div>`;
      const event = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true });
      Object.defineProperty(event, "target", { value: document.getElementById("plain") });

      document.dispatchEvent(event);
      expect(wsSend).not.toHaveBeenCalled();
    });
  });
});
