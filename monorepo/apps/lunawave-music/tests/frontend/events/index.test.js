import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  syncBrowserAudio: vi.fn(),
  unlockBrowserAudio: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/action-modal-events.js", () => ({
  initActionModalEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/click-delegation-events.js", () => ({
  initClickDelegationEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/discover-search-events.js", () => ({
  initDiscoverSearchEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/drag-scroll-events.js", () => ({
  initDragScrollEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/keyboard-shortcut-events.js", () => ({
  initKeyboardShortcutEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/lyrics-events.js", () => ({
  initLyricsEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/progress-events.js", () => ({
  initProgressEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/queue-events.js", () => ({
  initQueueDragDrop: vi.fn(),
  initQueueEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/search-input-events.js", () => ({
  initSearchInputEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/settings-events.js", () => ({
  initSettingsEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/events/transport-events.js", () => ({
  initTransportEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/render/discover-personalize.js", () => ({
  initDiscoverFilterEvents: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/render/navigation.js", () => ({
  switchTab: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/services/auth.js", () => ({
  applyRoleUI: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  submitSetup: vi.fn(),
}));

import { initEvents, updateSetupSubmitState } from "../../../web/static/shared/js/events/index.js";
import { unlockBrowserAudio, syncBrowserAudio } from "../../../web/static/shared/js/audio/playback-sync.js";
import { initTransportEvents } from "../../../web/static/shared/js/events/transport-events.js";
import { initProgressEvents } from "../../../web/static/shared/js/events/progress-events.js";
import { initSearchInputEvents } from "../../../web/static/shared/js/events/search-input-events.js";
import { initActionModalEvents } from "../../../web/static/shared/js/events/action-modal-events.js";
import { initClickDelegationEvents } from "../../../web/static/shared/js/events/click-delegation-events.js";
import { initKeyboardShortcutEvents } from "../../../web/static/shared/js/events/keyboard-shortcut-events.js";
import { initQueueEvents, initQueueDragDrop } from "../../../web/static/shared/js/events/queue-events.js";
import { initLyricsEvents } from "../../../web/static/shared/js/events/lyrics-events.js";
import { initSettingsEvents } from "../../../web/static/shared/js/events/settings-events.js";
import { initDiscoverFilterEvents } from "../../../web/static/shared/js/render/discover-personalize.js";
import { initDiscoverSearchEvents } from "../../../web/static/shared/js/events/discover-search-events.js";
import { initDragScrollEvents } from "../../../web/static/shared/js/events/drag-scroll-events.js";
import { switchTab } from "../../../web/static/shared/js/render/navigation.js";
import { applyRoleUI, login, logout, submitSetup } from "../../../web/static/shared/js/services/auth.js";

function el(tag = "div") {
  return document.createElement(tag);
}

describe("events/index.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
    globalThis.safeStorage = undefined;
    delete globalThis.localStorage;
    vi.stubGlobal("localStorage", { setItem: vi.fn(), getItem: vi.fn(), removeItem: vi.fn() });

    Object.assign(store, { userRole: "portal" });

    Object.assign(dom, {
      searchInput: Object.assign(document.createElement("input"), { value: "" }),
      portalClientBtn: null,
      portalAdminBtn: null,
      portalLoginForm: null,
      adminUsername: null,
      adminPassword: null,
      adminSubmitBtn: null,
      setupPassword: null,
      setupConfirmPassword: null,
      setupSubmitBtn: null,
      setupUsername: null,
      setupConfirmErrorMsg: null,
      logoutBtn: null,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("delegates to every sub-module initializer", () => {
    initEvents();

    expect(initTransportEvents).toHaveBeenCalled();
    expect(initProgressEvents).toHaveBeenCalled();
    expect(initSearchInputEvents).toHaveBeenCalled();
    expect(initActionModalEvents).toHaveBeenCalled();
    expect(initClickDelegationEvents).toHaveBeenCalled();
    expect(initKeyboardShortcutEvents).toHaveBeenCalled();
    expect(initQueueEvents).toHaveBeenCalled();
    expect(initQueueDragDrop).toHaveBeenCalled();
    expect(initLyricsEvents).toHaveBeenCalled();
    expect(initSettingsEvents).toHaveBeenCalled();
    expect(initDiscoverFilterEvents).toHaveBeenCalled();
    expect(initDiscoverSearchEvents).toHaveBeenCalled();
    expect(initDragScrollEvents).toHaveBeenCalled();
  });

  describe("mood-card click", () => {
    it("switches to search and fills the query for admins", () => {
      store.userRole = "admin";
      document.body.innerHTML = `<div class="mood-card" data-mood="galau"></div>`;
      initEvents();

      document.querySelector(".mood-card").click();

      expect(switchTab).toHaveBeenCalledWith("search");
      expect(dom.searchInput.value).toBe("galau mix");
    });

    it("does nothing for non-admins", () => {
      store.userRole = "client";
      document.body.innerHTML = `<div class="mood-card" data-mood="galau"></div>`;
      initEvents();

      document.querySelector(".mood-card").click();
      expect(switchTab).not.toHaveBeenCalled();
    });

    it("does nothing when the card has no data-mood", () => {
      store.userRole = "admin";
      document.body.innerHTML = `<div class="mood-card"></div>`;
      initEvents();

      document.querySelector(".mood-card").click();
      expect(switchTab).not.toHaveBeenCalled();
    });
  });

  describe("portalClientBtn", () => {
    it("switches to client role, persists via safeStorage, and syncs audio", () => {
      globalThis.safeStorage = { set: vi.fn() };
      dom.portalClientBtn = el("button");
      initEvents();

      dom.portalClientBtn.click();

      expect(store.userRole).toBe("client");
      expect(globalThis.safeStorage.set).toHaveBeenCalledWith("lunawave_user_role", "client");
      expect(applyRoleUI).toHaveBeenCalled();
      expect(unlockBrowserAudio).toHaveBeenCalled();
      expect(syncBrowserAudio).toHaveBeenCalled();
    });

    it("falls back to localStorage when safeStorage is unavailable", () => {
      dom.portalClientBtn = el("button");
      initEvents();
      dom.portalClientBtn.click();
      expect(localStorage.setItem).toHaveBeenCalledWith("lunawave_user_role", "client");
    });
  });

  describe("portalAdminBtn", () => {
    it("toggles the login form visible and focuses the username field", () => {
      dom.portalAdminBtn = el("button");
      dom.portalLoginForm = el();
      dom.portalLoginForm.classList.add("hidden");
      dom.adminUsername = el("input");
      const focusSpy = vi.spyOn(dom.adminUsername, "focus");
      initEvents();

      dom.portalAdminBtn.click();

      expect(dom.portalLoginForm.classList.contains("hidden")).toBe(false);
      expect(focusSpy).toHaveBeenCalled();
    });

    it("toggling back to hidden does not focus username", () => {
      dom.portalAdminBtn = el("button");
      dom.portalLoginForm = el();
      dom.adminUsername = el("input");
      const focusSpy = vi.spyOn(dom.adminUsername, "focus");
      initEvents();

      dom.portalAdminBtn.click(); // now hidden
      expect(dom.portalLoginForm.classList.contains("hidden")).toBe(true);
      expect(focusSpy).not.toHaveBeenCalled();
    });
  });

  describe("admin login form", () => {
    it("adminSubmitBtn calls login() with trimmed username and raw password", () => {
      dom.adminSubmitBtn = el("button");
      dom.adminUsername = Object.assign(el("input"), { value: "  bagas  " });
      dom.adminPassword = Object.assign(el("input"), { value: "secret" });
      initEvents();

      dom.adminSubmitBtn.click();
      expect(login).toHaveBeenCalledWith("bagas", "secret");
    });

    it("adminPassword Enter key triggers adminSubmitBtn.click()", () => {
      dom.adminSubmitBtn = el("button");
      dom.adminUsername = Object.assign(el("input"), { value: "u" });
      dom.adminPassword = Object.assign(el("input"), { value: "p" });
      const clickSpy = vi.spyOn(dom.adminSubmitBtn, "click");
      initEvents();

      dom.adminPassword.dispatchEvent(new KeyboardEvent("keypress", { key: "Enter" }));
      expect(clickSpy).toHaveBeenCalled();
    });

    it("adminPassword non-Enter key does not trigger submit", () => {
      dom.adminSubmitBtn = el("button");
      dom.adminPassword = el("input");
      const clickSpy = vi.spyOn(dom.adminSubmitBtn, "click");
      initEvents();

      dom.adminPassword.dispatchEvent(new KeyboardEvent("keypress", { key: "a" }));
      expect(clickSpy).not.toHaveBeenCalled();
    });
  });

  describe("setup form", () => {
    it("disables submit when password and confirm mismatch, with an error message", () => {
      dom.setupSubmitBtn = Object.assign(el("button"), { disabled: false });
      dom.setupPassword = Object.assign(el("input"), { value: "abc" });
      dom.setupConfirmPassword = Object.assign(el("input"), { value: "xyz" });
      dom.setupConfirmErrorMsg = Object.assign(el(), { textContent: "" });
      initEvents();

      dom.setupPassword.dispatchEvent(new Event("input"));

      expect(dom.setupSubmitBtn.disabled).toBe(true);
      expect(dom.setupConfirmErrorMsg.textContent).toContain("tidak sama");
    });

    it("enables submit and clears the error once they match", () => {
      dom.setupSubmitBtn = Object.assign(el("button"), { disabled: true });
      dom.setupPassword = Object.assign(el("input"), { value: "abc" });
      dom.setupConfirmPassword = Object.assign(el("input"), { value: "abc" });
      dom.setupConfirmErrorMsg = Object.assign(el(), { textContent: "mismatch" });
      initEvents();

      dom.setupConfirmPassword.dispatchEvent(new Event("input"));

      expect(dom.setupSubmitBtn.disabled).toBe(false);
      expect(dom.setupConfirmErrorMsg.textContent).toBe("");
    });

    it("treats two empty fields as matching (no error shown)", () => {
      dom.setupSubmitBtn = Object.assign(el("button"), { disabled: false });
      dom.setupPassword = Object.assign(el("input"), { value: "" });
      dom.setupConfirmPassword = Object.assign(el("input"), { value: "" });
      dom.setupConfirmErrorMsg = Object.assign(el(), { textContent: "" });
      initEvents();

      expect(dom.setupSubmitBtn.disabled).toBe(false);
      expect(dom.setupConfirmErrorMsg.textContent).toBe("");
    });

    it("setupConfirmPassword Enter submits only when the button is enabled", () => {
      dom.setupSubmitBtn = Object.assign(el("button"), { disabled: false });
      dom.setupConfirmPassword = el("input");
      const clickSpy = vi.spyOn(dom.setupSubmitBtn, "click");
      initEvents();

      dom.setupConfirmPassword.dispatchEvent(new KeyboardEvent("keypress", { key: "Enter" }));
      expect(clickSpy).toHaveBeenCalled();
    });

    it("setupConfirmPassword Enter is ignored while the button is disabled", () => {
      // initEvents() calls updateSetupSubmitState() once during wiring, so
      // the button's disabled state actually reflects a real mismatch here
      // (not just the initial value we hand it).
      dom.setupSubmitBtn = el("button");
      dom.setupPassword = Object.assign(el("input"), { value: "abc" });
      dom.setupConfirmPassword = Object.assign(el("input"), { value: "xyz" });
      initEvents();
      expect(dom.setupSubmitBtn.disabled).toBe(true);
      const clickSpy = vi.spyOn(dom.setupSubmitBtn, "click");

      dom.setupConfirmPassword.dispatchEvent(new KeyboardEvent("keypress", { key: "Enter" }));
      expect(clickSpy).not.toHaveBeenCalled();
    });

    it("setupSubmitBtn calls submitSetup() with the three trimmed/raw field values", () => {
      dom.setupSubmitBtn = el("button");
      dom.setupUsername = Object.assign(el("input"), { value: "  admin  " });
      dom.setupPassword = Object.assign(el("input"), { value: "p1" });
      dom.setupConfirmPassword = Object.assign(el("input"), { value: "p1" });
      initEvents();

      dom.setupSubmitBtn.click();
      expect(submitSetup).toHaveBeenCalledWith("admin", "p1", "p1");
    });
  });

  it("logoutBtn calls logout()", () => {
    dom.logoutBtn = el("button");
    initEvents();
    dom.logoutBtn.click();
    expect(logout).toHaveBeenCalled();
  });

  it("nav-btn clicks switch to the tab named in data-tab", () => {
    document.body.innerHTML = `<button class="nav-btn" data-tab="queue"></button>`;
    initEvents();
    document.querySelector(".nav-btn").click();
    expect(switchTab).toHaveBeenCalledWith("queue");
  });

  it("updateSetupSubmitState is a no-op when setupSubmitBtn is absent", () => {
    dom.setupSubmitBtn = null;
    expect(() => updateSetupSubmitState()).not.toThrow();
  });
});
