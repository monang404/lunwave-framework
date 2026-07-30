import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { emit } from "../../../web/static/shared/js/bus.js";
import {
  showConnectionToast,
  hideConnectionToast,
  showLogToast,
  initToastBusSubscriptions,
} from "../../../web/static/shared/js/render/toast.js";

describe("render/toast.js", () => {
  beforeEach(() => {
    Object.assign(dom, {
      connectionToast: Object.assign(document.createElement("div"), { textContent: "", className: "" }),
      logToast: document.createElement("div"),
    });
  });

  it("showConnectionToast sets the text and 'active <type>' class", () => {
    showConnectionToast("Terputus", "error");
    expect(dom.connectionToast.textContent).toBe("Terputus");
    expect(dom.connectionToast.className).toBe("active error");
  });

  it("hideConnectionToast clears the className", () => {
    dom.connectionToast.className = "active error";
    hideConnectionToast();
    expect(dom.connectionToast.className).toBe("");
  });

  describe("showLogToast", () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it("sets the text, activates the toast, and auto-hides after 3s", () => {
      showLogToast("Lagu ditambahkan");
      expect(dom.logToast.textContent).toBe("Lagu ditambahkan");
      expect(dom.logToast.classList.contains("active")).toBe(true);

      vi.advanceTimersByTime(3000);
      expect(dom.logToast.classList.contains("active")).toBe(false);
    });

    it("resets the auto-hide timer when called again before it fires", () => {
      showLogToast("Pesan 1");
      vi.advanceTimersByTime(2000);
      showLogToast("Pesan 2");
      vi.advanceTimersByTime(2000);
      // Still active: the first timer was cleared, second one has 1s left.
      expect(dom.logToast.classList.contains("active")).toBe(true);

      vi.advanceTimersByTime(1000);
      expect(dom.logToast.classList.contains("active")).toBe(false);
    });
  });

  describe("initToastBusSubscriptions", () => {
    it("wires toast:log to showLogToast", () => {
      initToastBusSubscriptions();
      emit("toast:log", { message: "hello" });
      expect(dom.logToast.textContent).toBe("hello");
    });

    it("wires toast:connection-show to showConnectionToast", () => {
      initToastBusSubscriptions();
      emit("toast:connection-show", { text: "Tersambung", type: "ok" });
      expect(dom.connectionToast.textContent).toBe("Tersambung");
      expect(dom.connectionToast.className).toBe("active ok");
    });

    it("wires toast:connection-hide to hideConnectionToast", () => {
      dom.connectionToast.className = "active ok";
      initToastBusSubscriptions();
      emit("toast:connection-hide");
      expect(dom.connectionToast.className).toBe("");
    });
  });
});
