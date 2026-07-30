import { describe, it, expect, vi, beforeEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";
import { emit } from "../../../web/static/shared/js/bus.js";

vi.mock("../../../web/static/shared/js/render/radio-hero-moon.js", () => ({
  setRadioHeroAnimState: vi.fn(),
}));

import { renderRadio, initRadioTabBusSubscriptions } from "../../../web/static/shared/js/render/radio-tab.js";
import { setRadioHeroAnimState } from "../../../web/static/shared/js/render/radio-hero-moon.js";

describe("render/radio-tab.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(dom, {
      radioToggleBtn: document.createElement("button"),
      rtSub: document.createElement("div"),
    });
    Object.assign(store, { playback_mode: "QUEUE", status: "PAUSED" });
  });

  describe("radio mode ON", () => {
    beforeEach(() => {
      store.playback_mode = "RADIO";
    });

    it("marks the toggle button 'on' with aria-pressed=true", () => {
      renderRadio();
      expect(dom.radioToggleBtn.classList.contains("on")).toBe(true);
      expect(dom.radioToggleBtn.classList.contains("off")).toBe(false);
      expect(dom.radioToggleBtn.dataset.on).toBe("true");
      expect(dom.radioToggleBtn.getAttribute("aria-pressed")).toBe("true");
    });

    it("shows 'Mencari stasiun...' while loading", () => {
      store.status = "LOADING";
      renderRadio();
      expect(dom.rtSub.textContent).toBe("Mencari stasiun...");
    });

    it("shows the nonstop-music subtitle otherwise", () => {
      store.status = "PLAYING";
      renderRadio();
      expect(dom.rtSub.textContent).toBe("24/7 Nonstop Music");
    });

    it("notifies the hero moon animation with true", () => {
      renderRadio();
      expect(setRadioHeroAnimState).toHaveBeenCalledWith(true);
    });
  });

  describe("radio mode OFF", () => {
    it("marks the toggle button 'off' with aria-pressed=false", () => {
      renderRadio();
      expect(dom.radioToggleBtn.classList.contains("off")).toBe(true);
      expect(dom.radioToggleBtn.classList.contains("on")).toBe(false);
      expect(dom.radioToggleBtn.dataset.on).toBe("false");
      expect(dom.radioToggleBtn.getAttribute("aria-pressed")).toBe("false");
    });

    it("shows the 'activate for autoplay' subtitle", () => {
      renderRadio();
      expect(dom.rtSub.textContent).toBe("Aktifkan untuk putar otomatis");
    });

    it("notifies the hero moon animation with false", () => {
      renderRadio();
      expect(setRadioHeroAnimState).toHaveBeenCalledWith(false);
    });
  });

  it("does not throw when radioToggleBtn/rtSub are missing", () => {
    dom.radioToggleBtn = null;
    dom.rtSub = null;
    expect(() => renderRadio()).not.toThrow();
  });

  it("initRadioTabBusSubscriptions wires radio:changed to renderRadio", () => {
    initRadioTabBusSubscriptions();
    store.playback_mode = "RADIO";
    emit("radio:changed");
    expect(dom.radioToggleBtn.classList.contains("on")).toBe(true);
  });
});
