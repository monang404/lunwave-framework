import { describe, it, expect, vi, beforeEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  _fadeIntervals: [],
  getOrInitAudio: vi.fn(),
  syncBrowserAudio: vi.fn(),
  unlockBrowserAudio: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/render/navigation.js", () => ({
  switchTab: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/settings-events.js", () => ({
  closeMainOverlay: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import { initTransportEvents } from "../../../web/static/shared/js/events/transport-events.js";
import { getOrInitAudio, unlockBrowserAudio } from "../../../web/static/shared/js/audio/playback-sync.js";
import { switchTab } from "../../../web/static/shared/js/render/navigation.js";
import { closeMainOverlay } from "../../../web/static/shared/js/events/settings-events.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

function makeEl(overrides = {}) {
  const el = document.createElement("div");
  Object.assign(el, overrides);
  return el;
}

describe("events/transport-events.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    Object.assign(dom, {
      pbTrackInfo: makeEl(),
      btnPlay: makeEl(),
      btnNext: makeEl(),
      btnPrev: makeEl(),
      btnRepeat: makeEl(),
      btnStop: makeEl(),
      volSlider: Object.assign(document.createElement("input"), { value: "50" }),
      pbVolLabel: makeEl(),
      btnDownload: makeEl(),
      settingsSheet: { classList: { remove: vi.fn() } },
      radioToggleBtn: makeEl(),
      radioRandomizeBtn: makeEl(),
      outputToggleBtn: makeEl(),
    });

    Object.assign(store, {
      userRole: "admin",
      status: "PAUSED",
      audio_output: "browser",
      playback_mode: "QUEUE",
      loop_mode: "off",
      active_tab: "search",
      current_track: null,
    });

    globalThis.scrollTo = vi.fn();
    initTransportEvents();
  });

  it("pbTrackInfo click switches to 'home' tab only when not already there", () => {
    dom.pbTrackInfo.click();
    expect(switchTab).toHaveBeenCalledWith("home");
  });

  it("pbTrackInfo click does nothing when already on the home tab", () => {
    store.active_tab = "home";
    dom.pbTrackInfo.click();
    expect(switchTab).not.toHaveBeenCalled();
  });

  describe("btnPlay", () => {
    it("toggles PAUSED -> PLAYING for admin, unlocks audio, and sends toggle_pause", () => {
      store.status = "PAUSED";
      dom.btnPlay.click();
      expect(store.status).toBe("PLAYING");
      expect(unlockBrowserAudio).toHaveBeenCalledWith(true);
      expect(wsSend).toHaveBeenCalledWith("toggle_pause");
    });

    it("toggles PLAYING -> PAUSED without unlocking audio", () => {
      store.status = "PLAYING";
      dom.btnPlay.click();
      expect(store.status).toBe("PAUSED");
      expect(unlockBrowserAudio).not.toHaveBeenCalled();
      expect(wsSend).toHaveBeenCalledWith("toggle_pause");
    });

    it("does nothing for a non-admin", () => {
      store.userRole = "client";
      dom.btnPlay.click();
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("btnNext / btnPrev", () => {
    it("btnNext sends 'next' with the current track's video_id when admin", () => {
      store.current_track = { video_id: "abc" };
      dom.btnNext.click();
      expect(store.status).toBe("LOADING");
      expect(wsSend).toHaveBeenCalledWith("next", { video_id: "abc" });
    });

    it("btnNext sends 'next' with an empty payload when there's no current track", () => {
      store.current_track = null;
      dom.btnNext.click();
      expect(wsSend).toHaveBeenCalledWith("next", {});
    });

    it("btnPrev sends 'prev' when admin", () => {
      dom.btnPrev.click();
      expect(store.status).toBe("LOADING");
      expect(wsSend).toHaveBeenCalledWith("prev");
    });

    it("btnNext/btnPrev are no-ops for non-admins", () => {
      store.userRole = "client";
      dom.btnNext.click();
      dom.btnPrev.click();
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("btnRepeat", () => {
    it("cycles off -> track", () => {
      store.loop_mode = "off";
      dom.btnRepeat.click();
      expect(wsSend).toHaveBeenCalledWith("set_loop", { mode: "track" });
    });

    it("cycles track -> queue", () => {
      store.loop_mode = "track";
      dom.btnRepeat.click();
      expect(wsSend).toHaveBeenCalledWith("set_loop", { mode: "queue" });
    });

    it("cycles queue -> off", () => {
      store.loop_mode = "queue";
      dom.btnRepeat.click();
      expect(wsSend).toHaveBeenCalledWith("set_loop", { mode: "off" });
    });

    it("is ignored for non-admins", () => {
      store.userRole = "client";
      dom.btnRepeat.click();
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("btnStop", () => {
    it("sends 'stop' for admin", () => {
      dom.btnStop.click();
      expect(wsSend).toHaveBeenCalledWith("stop");
    });

    it("does nothing for non-admin", () => {
      store.userRole = "client";
      dom.btnStop.click();
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("volSlider", () => {
    it("updates store.volume and the label live on 'input', for any role", () => {
      dom.volSlider.value = "77";
      dom.volSlider.dispatchEvent(new Event("input"));
      expect(store.volume).toBe(77);
      expect(dom.pbVolLabel.textContent).toBe("77%");
    });

    it("applies volume to the live browser audio element when output is 'browser'", () => {
      const audio = { volume: 0 };
      getOrInitAudio.mockReturnValue(audio);
      dom.volSlider.value = "40";
      dom.volSlider.dispatchEvent(new Event("input"));
      expect(audio.volume).toBeCloseTo(0.4);
    });

    it("sends volume_set on 'change' only for admin", () => {
      dom.volSlider.value = "60";
      dom.volSlider.dispatchEvent(new Event("input"));
      dom.volSlider.dispatchEvent(new Event("change"));
      expect(wsSend).toHaveBeenCalledWith("volume_set", { volume: 60 });
    });

    it("does not send volume_set on 'change' for non-admin", () => {
      store.userRole = "client";
      dom.volSlider.dispatchEvent(new Event("change"));
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("btnDownload", () => {
    it("closes the settings sheet/overlay and sends 'download' for admin", () => {
      dom.btnDownload.click();
      expect(dom.settingsSheet.classList.remove).toHaveBeenCalledWith("open");
      expect(closeMainOverlay).toHaveBeenCalled();
      expect(wsSend).toHaveBeenCalledWith("download");
    });

    it("closes the sheet but does not send 'download' for non-admin", () => {
      store.userRole = "client";
      dom.btnDownload.click();
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("radioToggleBtn", () => {
    it("switches QUEUE -> RADIO and notifies the server, for admin", () => {
      store.playback_mode = "QUEUE";
      dom.radioToggleBtn.click();
      expect(store.playback_mode).toBe("RADIO");
      expect(wsSend).toHaveBeenCalledWith("set_mode", { mode: "RADIO" });
    });

    it("does nothing while status is LOADING", () => {
      store.status = "LOADING";
      dom.radioToggleBtn.click();
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("does nothing for non-admin", () => {
      store.userRole = "client";
      dom.radioToggleBtn.click();
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("radioRandomizeBtn", () => {
    it("resets the radio queue/current track and asks server to randomize, for admin", () => {
      store.radio_queue = [{ video_id: "x" }];
      store.current_track = { video_id: "x" };
      dom.radioRandomizeBtn.click();
      expect(store.radio_queue).toEqual([]);
      expect(store.current_track).toBeNull();
      expect(store.status).toBe("LOADING");
      expect(globalThis.scrollTo).toHaveBeenCalled();
      expect(wsSend).toHaveBeenCalledWith("radio_randomize", { seed_artist: null });
    });

    it("does nothing for non-admin", () => {
      store.userRole = "client";
      dom.radioRandomizeBtn.click();
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("outputToggleBtn", () => {
    it("toggles browser -> device and notifies server, for admin", () => {
      store.audio_output = "browser";
      dom.outputToggleBtn.click();
      expect(wsSend).toHaveBeenCalledWith("set_output", { output: "device" });
    });

    it("toggles device -> browser and unlocks audio", () => {
      store.audio_output = "device";
      dom.outputToggleBtn.click();
      expect(unlockBrowserAudio).toHaveBeenCalled();
      expect(wsSend).toHaveBeenCalledWith("set_output", { output: "browser" });
    });

    it("does nothing for non-admin", () => {
      store.userRole = "client";
      dom.outputToggleBtn.click();
      expect(wsSend).not.toHaveBeenCalled();
    });
  });
});
