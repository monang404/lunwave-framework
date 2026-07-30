import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";

vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import { switchTab } from "../../../web/static/shared/js/render/navigation.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

function panel() {
  return document.createElement("div");
}

describe("render/navigation.js switchTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    document.body.innerHTML = `
      <button class="nav-btn" data-tab="home"></button>
      <button class="nav-btn" data-tab="search"></button>
      <button class="nav-btn" data-tab="radio"></button>
      <button class="nav-btn" data-tab="discover"></button>
    `;
    Object.assign(dom, {
      tabHome: panel(),
      tabSearch: panel(),
      tabRadio: panel(),
      tabDiscover: panel(),
      searchInput: Object.assign(document.createElement("input"), { value: "" }),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("updates store.active_tab and body dataset", () => {
    switchTab("radio");
    expect(store.active_tab).toBe("radio");
    expect(document.body.dataset.activeTab).toBe("radio");
  });

  it("shows the matching panel and hides the others", () => {
    switchTab("search");
    expect(dom.tabSearch.classList.contains("active")).toBe(true);
    expect(dom.tabHome.classList.contains("active")).toBe(false);
    expect(dom.tabRadio.classList.contains("active")).toBe(false);
    expect(dom.tabDiscover.classList.contains("active")).toBe(false);
  });

  it("marks the matching nav-btn as selected and the rest as not", () => {
    switchTab("discover");
    const btns = document.querySelectorAll(".nav-btn");
    btns.forEach((btn) => {
      if (btn.dataset.tab === "discover") {
        expect(btn.classList.contains("active")).toBe(true);
        expect(btn.getAttribute("aria-selected")).toBe("true");
      } else {
        expect(btn.classList.contains("active")).toBe(false);
        expect(btn.getAttribute("aria-selected")).toBe("false");
      }
    });
  });

  it("focuses the search input after 100ms when switching to search", () => {
    switchTab("search");
    const focusSpy = vi.spyOn(dom.searchInput, "focus");
    vi.advanceTimersByTime(100);
    expect(focusSpy).toHaveBeenCalled();
  });

  it("does not schedule a focus for non-search tabs", () => {
    switchTab("home");
    const focusSpy = vi.spyOn(dom.searchInput, "focus");
    vi.advanceTimersByTime(200);
    expect(focusSpy).not.toHaveBeenCalled();
  });

  it("requests a fresh discover feed via wsSend for the discover tab", () => {
    switchTab("discover");
    expect(wsSend).toHaveBeenCalledWith("discover");
  });

  it("requests a fresh discover feed via wsSend for the home tab too", () => {
    switchTab("home");
    expect(wsSend).toHaveBeenCalledWith("discover");
  });

  it("does not call wsSend for tabs other than home/discover", () => {
    switchTab("radio");
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("does not throw when a target panel element is missing", () => {
    dom.tabRadio = null;
    expect(() => switchTab("radio")).not.toThrow();
  });
});
