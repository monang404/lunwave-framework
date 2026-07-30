import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";
import { emit } from "../../../web/static/shared/js/bus.js";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  getOrInitAudio: vi.fn(),
  resetLastLoadedVideoId: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/render/navigation.js", () => ({
  switchTab: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({
  renderHeader: vi.fn(),
  wsSend: vi.fn(),
}));

import {
  applyRoleUI,
  submitSetup,
  login,
  logout,
  initAuthBusSubscriptions,
} from "../../../web/static/shared/js/services/auth.js";
import { getOrInitAudio, resetLastLoadedVideoId } from "../../../web/static/shared/js/audio/playback-sync.js";
import { switchTab } from "../../../web/static/shared/js/render/navigation.js";
import { renderHeader, wsSend } from "../../../web/static/shared/js/ws.js";

function classListMock() {
  return { add: vi.fn(), remove: vi.fn() };
}

describe("services/auth.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.className = "";
    globalThis.safeStorage = { get: vi.fn(), set: vi.fn(), remove: vi.fn() };
    globalThis.ws = undefined;
    globalThis.location = { pathname: "/", href: "" };
    globalThis.visualViewport = undefined;

    Object.assign(dom, {
      portalScreen: { classList: classListMock() },
      appContainer: { classList: classListMock() },
      logoutBtn: { style: {} },
      setupErrorMsg: { textContent: "" },
      setupConfirmErrorMsg: { textContent: "" },
      setupSubmitBtn: { disabled: false, textContent: "" },
      loginErrorMsg: { textContent: "" },
      adminSubmitBtn: { disabled: false, textContent: "" },
    });

    Object.assign(store, {
      userRole: "portal",
      adminUsername: "",
      adminPassword: "",
    });
  });

  afterEach(() => {
    document.body.className = "";
  });

  describe("applyRoleUI", () => {
    it("shows the portal screen for role 'portal'", () => {
      store.userRole = "portal";
      applyRoleUI();
      expect(dom.portalScreen.classList.add).toHaveBeenCalledWith("portal-active");
      expect(dom.appContainer.classList.add).toHaveBeenCalledWith("portal-active");
      expect(document.body.classList.contains("client-mode")).toBe(false);
      expect(dom.logoutBtn.style.display).toBe("none");
      expect(renderHeader).toHaveBeenCalled();
    });

    it("switches to client mode and shows logout for role 'client'", () => {
      store.userRole = "client";
      applyRoleUI();
      expect(dom.portalScreen.classList.remove).toHaveBeenCalledWith("portal-active");
      expect(document.body.classList.contains("client-mode")).toBe(true);
      expect(switchTab).toHaveBeenCalledWith("home");
      expect(dom.logoutBtn.style.display).toBe("flex");
    });

    it("switches to admin mode (visualViewport height hack was intentionally removed -- see comment in auth.js; CSS 100dvh in app-shell.css handles it now)", () => {
      document.body.innerHTML = '<div id="app"></div>';
      globalThis.visualViewport = { height: 640 };
      store.userRole = "admin";
      applyRoleUI();
      expect(document.body.classList.contains("client-mode")).toBe(false);
      expect(switchTab).toHaveBeenCalledWith("home");
      expect(dom.logoutBtn.style.display).toBe("flex");
      // #app's height must NOT be touched by JS anymore -- if this starts
      // failing because style.height is set again, that's the Android
      // Chrome nav-bar bug being reintroduced, not a test to "fix" by
      // updating the expectation.
      expect(document.getElementById("app").style.height).toBe("");
    });
  });

  describe("submitSetup", () => {
    it("shows an error when username or password is missing", () => {
      submitSetup("", "pass", "pass");
      expect(dom.setupErrorMsg.textContent).toBe("Isi username dan password!");
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("shows a mismatch error when password != confirmPassword", () => {
      submitSetup("user", "pass1", "pass2");
      expect(dom.setupConfirmErrorMsg.textContent).toBe(
        "Password dan Confirm Password tidak sama."
      );
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("sends setup_admin over an open socket, without the confirm field", () => {
      globalThis.ws = { readyState: WebSocket.OPEN };
      submitSetup("user", "pass", "pass");
      expect(dom.setupSubmitBtn.disabled).toBe(true);
      expect(wsSend).toHaveBeenCalledWith("setup_admin", { username: "user", password: "pass" });
    });

    it("shows a connection error and re-enables the button when socket isn't open", () => {
      globalThis.ws = undefined;
      submitSetup("user", "pass", "pass");
      expect(dom.setupErrorMsg.textContent).toContain("Koneksi server terputus");
      expect(dom.setupSubmitBtn.disabled).toBe(false);
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("login", () => {
    it("shows an error when username or password is missing", () => {
      login("", "");
      expect(dom.loginErrorMsg.textContent).toBe("Isi username dan password!");
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("sends auth over an open socket and stores credentials in-memory", () => {
      globalThis.ws = { readyState: WebSocket.OPEN };
      login("admin", "secret");
      expect(store.adminUsername).toBe("admin");
      expect(store.adminPassword).toBe("secret");
      expect(wsSend).toHaveBeenCalledWith("auth", { username: "admin", password: "secret" });
      expect(dom.adminSubmitBtn.disabled).toBe(true);
    });

    it("shows a connection error when socket isn't open", () => {
      globalThis.ws = undefined;
      login("admin", "secret");
      expect(dom.loginErrorMsg.textContent).toContain("Koneksi server terputus");
      expect(dom.adminSubmitBtn.disabled).toBe(false);
    });
  });

  describe("logout", () => {
    it("stops local audio playback and resets last loaded video id", () => {
      const pause = vi.fn();
      const load = vi.fn();
      getOrInitAudio.mockReturnValue({ pause, src: "x", removeAttribute: vi.fn(), load });
      globalThis.location = { pathname: "/admin", href: "" };

      logout();

      expect(pause).toHaveBeenCalled();
      expect(load).toHaveBeenCalled();
      expect(resetLastLoadedVideoId).toHaveBeenCalled();
    });

    it("sends 'stop' to the server when logging out as admin", () => {
      getOrInitAudio.mockReturnValue(null);
      store.userRole = "admin";
      globalThis.location = { pathname: "/admin", href: "" };

      logout();

      expect(wsSend).toHaveBeenCalledWith("stop");
      expect(store.userRole).toBe("portal");
    });

    it("does not send 'stop' when logging out as a regular client", () => {
      getOrInitAudio.mockReturnValue(null);
      store.userRole = "client";
      globalThis.location = { pathname: "/admin", href: "" };

      logout();

      expect(wsSend).not.toHaveBeenCalledWith("stop");
    });

    it("sends logout with the session token when one exists, and clears local storage", () => {
      getOrInitAudio.mockReturnValue(null);
      globalThis.safeStorage.get.mockReturnValue("tok-123");
      globalThis.location = { pathname: "/admin", href: "" };

      logout();

      expect(wsSend).toHaveBeenCalledWith("logout", { token: "tok-123" });
      expect(globalThis.safeStorage.remove).toHaveBeenCalledWith("lunawave_session_token");
    });

    it("redirects to /admin (async) when not already there", async () => {
      vi.useFakeTimers();
      getOrInitAudio.mockReturnValue(null);
      globalThis.location = { pathname: "/", href: "" };
      globalThis.ws = { close: vi.fn(), readyState: WebSocket.OPEN };

      logout();
      expect(globalThis.location.href).toBe("");
      vi.advanceTimersByTime(150);
      expect(globalThis.location.href).toBe("/admin");
      expect(globalThis.ws.close).toHaveBeenCalled();

      vi.useRealTimers();
    });

    it("re-applies role UI immediately (no redirect) when already on /admin", () => {
      getOrInitAudio.mockReturnValue(null);
      globalThis.location = { pathname: "/admin", href: "" };
      globalThis.ws = { close: vi.fn(), readyState: WebSocket.OPEN };

      logout();

      expect(renderHeader).toHaveBeenCalled();
      expect(globalThis.ws.close).toHaveBeenCalled();
    });
  });

  describe("initAuthBusSubscriptions", () => {
    it("triggers applyRoleUI when 'auth:role-changed' is emitted on the bus", () => {
      initAuthBusSubscriptions();
      store.userRole = "client";

      emit("auth:role-changed");

      expect(switchTab).toHaveBeenCalledWith("home");
      expect(renderHeader).toHaveBeenCalled();
    });

    it("triggers logout when 'auth:logout' is emitted on the bus", () => {
      globalThis.location = { pathname: "/admin", href: "" };
      getOrInitAudio.mockReturnValue(null);
      initAuthBusSubscriptions();

      emit("auth:logout");

      expect(store.userRole).toBe("portal");
    });
  });
});
