import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../web/static/shared/js/dom.js";
import { store } from "../../web/static/shared/js/store.js";

vi.mock("../../web/static/shared/js/services/auth.js", () => ({
  applyRoleUI: vi.fn(),
}));
vi.mock("../../web/static/shared/js/ws.js", () => ({
  renderHeader: vi.fn(),
  wsSend: vi.fn(),
}));

import { initPortal, initSetupCheck } from "../../web/static/shared/js/portal.js";
import { applyRoleUI } from "../../web/static/shared/js/services/auth.js";

function classListMock() {
  return { add: vi.fn(), remove: vi.fn(), contains: vi.fn() };
}

describe("portal.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.safeStorage = undefined;
    Object.assign(dom, {
      portalScreen: { classList: classListMock() },
      setupScreen: { classList: classListMock() },
    });
    store.userRole = "portal";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    globalThis.safeStorage = undefined;
    vi.restoreAllMocks();
  });

  describe("initPortal", () => {
    it("uses safeStorage role when present and not 'client'", () => {
      globalThis.safeStorage = { get: vi.fn().mockReturnValue("admin") };
      initPortal();
      expect(store.userRole).toBe("admin");
      expect(applyRoleUI).toHaveBeenCalled();
    });

    it("falls back to 'portal' role when stored role is 'client'", () => {
      globalThis.safeStorage = { get: vi.fn().mockReturnValue("client") };
      initPortal();
      expect(store.userRole).toBe("portal");
    });

    it("falls back to 'portal' role when no role is stored", () => {
      globalThis.safeStorage = { get: vi.fn().mockReturnValue(null) };
      initPortal();
      expect(store.userRole).toBe("portal");
    });

    it("reads from localStorage when safeStorage is unavailable", () => {
      globalThis.safeStorage = undefined;
      const getItemSpy = vi
        .spyOn(Storage.prototype, "getItem")
        .mockReturnValue("admin");
      initPortal();
      expect(getItemSpy).toHaveBeenCalledWith("lunawave_user_role");
      expect(store.userRole).toBe("admin");
    });
  });

  describe("initSetupCheck", () => {
    it("shows setup screen when the server reports setup is required", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ setup_required: true }),
      });

      await initSetupCheck();

      expect(dom.portalScreen.classList.remove).toHaveBeenCalledWith("portal-active");
      expect(dom.setupScreen.classList.add).toHaveBeenCalledWith("portal-active");
      expect(applyRoleUI).not.toHaveBeenCalled();
    });

    it("falls through to normal login flow when setup is not required", async () => {
      globalThis.safeStorage = { get: vi.fn().mockReturnValue("admin") };
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ setup_required: false }),
      });

      await initSetupCheck();

      expect(dom.setupScreen.classList.remove).toHaveBeenCalledWith("portal-active");
      // initPortal() should have run as part of the fallthrough
      expect(applyRoleUI).toHaveBeenCalled();
    });

    it("fails open to the normal login flow when the response is not ok", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
      const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

      await initSetupCheck();

      expect(warnSpy).toHaveBeenCalled();
      expect(dom.setupScreen.classList.remove).toHaveBeenCalledWith("portal-active");
      expect(applyRoleUI).toHaveBeenCalled();
    });

    it("fails open to the normal login flow when fetch throws (network error)", async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new Error("network down"));
      const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

      await initSetupCheck();

      expect(warnSpy).toHaveBeenCalled();
      expect(dom.setupScreen.classList.remove).toHaveBeenCalledWith("portal-active");
      expect(applyRoleUI).toHaveBeenCalled();
    });

    it("is safe to call when portalScreen/setupScreen are missing from dom", async () => {
      Object.assign(dom, { portalScreen: null, setupScreen: null });
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ setup_required: true }),
      });

      await expect(initSetupCheck()).resolves.toBeUndefined();
    });
  });
});
