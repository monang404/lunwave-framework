import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";
import { emit } from "../../../web/static/shared/js/bus.js";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  getOrInitAudio: vi.fn(),
  unlockBrowserAudio: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/render/navigation.js", () => ({
  switchTab: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import {
  initSettingsEvents,
  initSettingsBusSubscriptions,
  renderSettingsSheet,
  closeMainOverlay,
} from "../../../web/static/shared/js/events/settings-events.js";
import { getOrInitAudio, unlockBrowserAudio } from "../../../web/static/shared/js/audio/playback-sync.js";
import { switchTab } from "../../../web/static/shared/js/render/navigation.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

function classListEl(extra = {}) {
  const el = document.createElement("div");
  // dataset dan style adalah accessor properties (getter tanpa setter) di
  // jsdom, jadi tidak bisa di-assign langsung lewat Object.assign(el, extra)
  // -- itu akan throw "Cannot set property ... which has only a getter".
  // Sub-property-nya perlu di-assign satu-satu ke objek yang sudah ada.
  const { dataset, style, ...rest } = extra;
  Object.assign(el, rest);
  if (dataset) Object.assign(el.dataset, dataset);
  if (style) Object.assign(el.style, style);
  return el;
}

// <select>.value = "x" is a no-op in jsdom (and real browsers) unless a
// matching <option value="x"> actually exists -- without it the value stays
// "" and downstream parseInt/parseFloat reads NaN. Build real <option>
// elements up front so tests can freely set .value to any of them.
function selectEl(values) {
  const el = document.createElement("select");
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = String(v);
    el.appendChild(opt);
  }
  return el;
}

describe("events/settings-events.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    Object.assign(dom, {
      btnSettings: classListEl(),
      settingsSheet: classListEl(),
      mainOverlay: classListEl(),
      sbToggle: classListEl({ dataset: { on: "false" } }),
      crossfadeToggle: classListEl(),
      loudnessToggle: classListEl(),
      ssOutBtn: classListEl({ textContent: "" }),
      ssOutSub: classListEl({ textContent: "" }),
      ssStopBtn: classListEl(),
      ssHistoryBtn: classListEl(),
      ssHistorySub: classListEl({ textContent: "" }),
      ssCacheClearBtn: classListEl(),
      ssCacheSub: classListEl({ textContent: "" }),
      ssSleepSelect: selectEl([0, 1, 15, 30, 60]),
      ssSleepSub: classListEl({ textContent: "" }),
      ssSpeedSelect: selectEl([0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]),
      ssSpeedSub: classListEl({ textContent: "" }),
      ssDlRow: classListEl({ style: {} }),
      ssDlPct: classListEl({ textContent: "" }),
      ssDlFill: classListEl({ style: {} }),
      ssDlTrack: classListEl({ textContent: "" }),
      btnHelp: classListEl(),
      helpSheet: classListEl(),
      helpCloseBtn: classListEl(),
      actionSheet: classListEl(),
      artistDetailSheet: classListEl(),
      discRecent: { scrollIntoView: vi.fn() },
    });

    Object.assign(store, {
      userRole: "admin",
      sponsorblock_active: false,
      crossfade_enabled: false,
      loudness_normalization_enabled: false,
      audio_output: "browser",
      playback_speed: 1.0,
      download_progress: null,
      history_count: 3,
    });

    globalThis.confirm = vi.fn().mockReturnValue(true);
    initSettingsEvents();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("btnSettings opens the sheet+overlay when closed", () => {
    dom.btnSettings.click();
    expect(dom.settingsSheet.classList.contains("open")).toBe(true);
    expect(dom.mainOverlay.classList.contains("open")).toBe(true);
    expect(wsSend).toHaveBeenCalledWith("get_cache_size", {});
  });

  it("btnSettings closes the sheet when already open", () => {
    dom.settingsSheet.classList.add("open");
    dom.mainOverlay.classList.add("open");
    dom.btnSettings.click();
    expect(dom.settingsSheet.classList.contains("open")).toBe(false);
  });

  it("clicking the overlay closes settings/action/help/artist sheets", () => {
    [dom.settingsSheet, dom.mainOverlay, dom.actionSheet, dom.helpSheet, dom.artistDetailSheet].forEach(
      (el) => el.classList.add("open")
    );
    dom.mainOverlay.click();
    expect(dom.settingsSheet.classList.contains("open")).toBe(false);
    expect(dom.actionSheet.classList.contains("open")).toBe(false);
    expect(dom.helpSheet.classList.contains("open")).toBe(false);
    expect(dom.artistDetailSheet.classList.contains("open")).toBe(false);
  });

  it("sbToggle flips sponsorblock state and notifies server, admin only", () => {
    dom.sbToggle.click();
    expect(dom.sbToggle.dataset.on).toBe("true");
    expect(store.sponsorblock_active).toBe(true);
    expect(wsSend).toHaveBeenCalledWith("set_sponsorblock", { enabled: true });

    wsSend.mockClear();
    store.userRole = "client";
    dom.sbToggle.click();
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("ssOutBtn toggles output, unlocks audio for browser, and closes settings", () => {
    store.audio_output = "device";
    dom.settingsSheet.classList.add("open");
    dom.ssOutBtn.click();
    expect(unlockBrowserAudio).toHaveBeenCalled();
    expect(wsSend).toHaveBeenCalledWith("set_output", { output: "browser" });
    expect(dom.settingsSheet.classList.contains("open")).toBe(false);
  });

  it("crossfadeToggle/loudnessToggle send the inverse of current state, admin only", () => {
    store.crossfade_enabled = true;
    dom.crossfadeToggle.click();
    expect(wsSend).toHaveBeenCalledWith("set_crossfade", { enabled: false });

    store.loudness_normalization_enabled = false;
    dom.loudnessToggle.click();
    expect(wsSend).toHaveBeenCalledWith("set_loudness_normalization", { enabled: true });
  });

  it("ssStopBtn sends stop and closes settings, admin only", () => {
    dom.settingsSheet.classList.add("open");
    dom.ssStopBtn.click();
    expect(wsSend).toHaveBeenCalledWith("stop");
    expect(dom.settingsSheet.classList.contains("open")).toBe(false);
  });

  it("ssHistoryBtn closes settings, switches to discover tab, requests discover data, and scrolls after a delay", () => {
    dom.ssHistoryBtn.click();
    expect(switchTab).toHaveBeenCalledWith("discover");
    expect(wsSend).toHaveBeenCalledWith("discover", {});
    vi.advanceTimersByTime(300);
    expect(dom.discRecent.scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth" });
  });

  it("ssCacheClearBtn asks for confirmation before clearing cache, admin only", () => {
    dom.ssCacheClearBtn.click();
    expect(globalThis.confirm).toHaveBeenCalled();
    expect(dom.ssCacheSub.textContent).toBe("Membersihkan...");
    expect(wsSend).toHaveBeenCalledWith("clear_cache", {});
  });

  it("ssCacheClearBtn does nothing if the user cancels the confirm dialog", () => {
    globalThis.confirm.mockReturnValue(false);
    dom.ssCacheClearBtn.click();
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("ssSleepSelect starts a countdown and notifies the server with minutes", () => {
    dom.ssSleepSelect.value = "1";
    dom.ssSleepSelect.dispatchEvent(new Event("change"));
    expect(wsSend).toHaveBeenCalledWith("set_sleep_timer", { minutes: 1 });
    expect(dom.ssSleepSub.textContent).toBe("1:00 tersisa");

    vi.advanceTimersByTime(1000);
    expect(dom.ssSleepSub.textContent).toBe("0:59 tersisa");
  });

  it("ssSleepSelect with 0 minutes shows 'Mati' immediately", () => {
    dom.ssSleepSelect.value = "0";
    dom.ssSleepSelect.dispatchEvent(new Event("change"));
    expect(dom.ssSleepSub.textContent).toBe("Mati");
  });

  it("ssSpeedSelect updates store, label, and live browser audio playbackRate", () => {
    const audio = { playbackRate: 1 };
    getOrInitAudio.mockReturnValue(audio);
    dom.ssSpeedSelect.value = "1.5";
    dom.ssSpeedSelect.dispatchEvent(new Event("change"));
    expect(store.playback_speed).toBe(1.5);
    expect(dom.ssSpeedSub.textContent).toBe("1.50x");
    expect(audio.playbackRate).toBe(1.5);
    expect(wsSend).toHaveBeenCalledWith("set_speed", { speed: 1.5 });
  });

  it("btnHelp opens the help sheet and overlay, closing the settings sheet", () => {
    dom.settingsSheet.classList.add("open");
    dom.btnHelp.click();
    expect(dom.settingsSheet.classList.contains("open")).toBe(false);
    expect(dom.helpSheet.classList.contains("open")).toBe(true);
    expect(dom.mainOverlay.classList.contains("open")).toBe(true);
  });

  it("helpCloseBtn closes the help sheet and the overlay", () => {
    dom.helpSheet.classList.add("open");
    dom.mainOverlay.classList.add("open");
    dom.helpCloseBtn.click();
    expect(dom.helpSheet.classList.contains("open")).toBe(false);
    expect(dom.mainOverlay.classList.contains("open")).toBe(false);
  });

  describe("renderSettingsSheet", () => {
    it("does nothing when the sheet isn't open", () => {
      renderSettingsSheet();
      expect(dom.sbToggle.dataset.on).toBe("false");
    });

    it("syncs toggle states and output label when the sheet is open", () => {
      dom.settingsSheet.classList.add("open");
      store.sponsorblock_active = true;
      store.audio_output = "device";
      renderSettingsSheet();
      expect(dom.sbToggle.dataset.on).toBe("true");
      expect(dom.ssOutSub.textContent).toBe("Keluar via perangkat (mpv)");
      expect(dom.ssOutBtn.textContent).toBe("📱 Device");
    });

    it("shows and updates the download progress row", () => {
      dom.settingsSheet.classList.add("open");
      store.download_progress = 0.42;
      store.current_track = { title: "My Song" };
      renderSettingsSheet();
      expect(dom.ssDlRow.style.display).toBe("flex");
      expect(dom.ssDlPct.textContent).toBe("42%");
      expect(dom.ssDlFill.style.width).toBe("42%");
      expect(dom.ssDlTrack.textContent).toBe("My Song");
    });

    it("hides the download row when there is no active download", () => {
      dom.settingsSheet.classList.add("open");
      store.download_progress = null;
      renderSettingsSheet();
      expect(dom.ssDlRow.style.display).toBe("none");
    });
  });

  describe("initSettingsBusSubscriptions", () => {
    it("re-renders the settings sheet on 'settings:sheet-changed'", () => {
      initSettingsBusSubscriptions();
      dom.settingsSheet.classList.add("open");
      store.sponsorblock_active = true;
      emit("settings:sheet-changed");
      expect(dom.sbToggle.dataset.on).toBe("true");
    });

    it("closes overlays on 'overlay:main-close'", () => {
      initSettingsBusSubscriptions();
      dom.mainOverlay.classList.add("open");
      dom.settingsSheet.classList.add("open");
      emit("overlay:main-close");
      expect(dom.mainOverlay.classList.contains("open")).toBe(false);
      expect(dom.settingsSheet.classList.contains("open")).toBe(false);
    });
  });

  it("closeMainOverlay is exported and safe to call directly", () => {
    dom.mainOverlay.classList.add("open");
    closeMainOverlay();
    expect(dom.mainOverlay.classList.contains("open")).toBe(false);
  });
});
