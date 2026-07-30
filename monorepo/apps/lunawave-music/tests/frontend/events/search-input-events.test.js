import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";

vi.mock("../../../web/static/shared/js/render/search.js", () => ({
  playSearchTrack: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import { initSearchInputEvents } from "../../../web/static/shared/js/events/search-input-events.js";
import { playSearchTrack } from "../../../web/static/shared/js/render/search.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

function el(tag = "div") {
  return document.createElement(tag);
}

describe("events/search-input-events.js", () => {
  let historyStore;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    document.body.innerHTML = `
      <button id="search-clear-btn" style="display:none;"></button>
      <div id="search-header"></div>
    `;

    historyStore = {};
    globalThis.safeStorage = {
      get: vi.fn((k) => historyStore[k]),
      set: vi.fn((k, v) => { historyStore[k] = v; }),
      remove: vi.fn((k) => { delete historyStore[k]; }),
    };

    Object.assign(dom, {
      searchInput: Object.assign(document.createElement("input"), { value: "" }),
      searchMsg: Object.assign(el(), { style: {} }),
      searchResults: Object.assign(el(), { style: {} }),
      searchHistoryContainer: Object.assign(el(), { style: {} }),
      searchHistoryList: el(),
      searchHistoryClear: el("button"),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    globalThis.safeStorage = undefined;
  });

  it("does not throw when none of the optional elements exist", () => {
    document.body.innerHTML = "";
    Object.assign(dom, {
      searchInput: null,
      searchMsg: null,
      searchResults: null,
      searchHistoryContainer: null,
      searchHistoryList: null,
      searchHistoryClear: null,
    });
    expect(() => initSearchInputEvents()).not.toThrow();
  });

  describe("search-clear-btn", () => {
    it("clears the input, hides itself, dispatches input, and focuses the field", () => {
      initSearchInputEvents();
      const clearBtn = document.getElementById("search-clear-btn");
      dom.searchInput.value = "sheila";
      const focusSpy = vi.spyOn(dom.searchInput, "focus");

      clearBtn.click();

      expect(dom.searchInput.value).toBe("");
      expect(clearBtn.style.display).toBe("none");
      expect(focusSpy).toHaveBeenCalled();
      // dispatching 'input' with an empty value should reset the message.
      expect(dom.searchMsg.textContent).toBe("Ketik nama lagu atau artis");
    });
  });

  describe("search-header collapse", () => {
    it("collapses the header immediately when the field already has focus (initial call)", () => {
      dom.searchInput.value = "";
      document.body.appendChild(dom.searchInput);
      dom.searchInput.focus();
      initSearchInputEvents();

      const header = document.getElementById("search-header");
      expect(header.classList.contains("collapsed")).toBe(true);
    });

    it("expands the header when the input has no value and is not focused", () => {
      initSearchInputEvents();
      const header = document.getElementById("search-header");
      expect(header.classList.contains("collapsed")).toBe(false);
    });

    it("collapses on input with a value and expands again once cleared and blurred", () => {
      document.body.appendChild(dom.searchInput);
      initSearchInputEvents();
      const header = document.getElementById("search-header");

      dom.searchInput.value = "dewa";
      dom.searchInput.dispatchEvent(new Event("input"));
      expect(header.classList.contains("collapsed")).toBe(true);

      dom.searchInput.value = "";
      dom.searchInput.dispatchEvent(new Event("blur"));
      expect(header.classList.contains("collapsed")).toBe(false);
    });
  });

  describe("typing a query", () => {
    it("shows the clear button and debounces a search for a new query", () => {
      initSearchInputEvents();
      document.body.appendChild(document.getElementById("search-clear-btn"));
      const clearBtn = document.getElementById("search-clear-btn");

      dom.searchInput.value = "peterpan";
      dom.searchInput.dispatchEvent(new Event("input"));

      expect(clearBtn.style.display).toBe("block");
      expect(dom.searchHistoryContainer.style.display).toBe("none");
      expect(wsSend).not.toHaveBeenCalled();

      vi.advanceTimersByTime(500);

      expect(wsSend).toHaveBeenCalledWith("search", { query: "peterpan" });
      expect(dom.searchMsg.style.display).toBe("block");
      expect(historyStore["lunawave_search_history"]).toContain('"peterpan"');
    });

    it("clearing the query shows the placeholder message and re-renders history", () => {
      historyStore["lunawave_search_history"] = JSON.stringify(["dulu"]);
      initSearchInputEvents();

      dom.searchInput.value = "";
      dom.searchInput.dispatchEvent(new Event("input"));

      expect(dom.searchMsg.textContent).toBe("Ketik nama lagu atau artis");
      expect(dom.searchResults.innerHTML).toBe("");
      expect(dom.searchHistoryContainer.style.display).toBe("block");
      expect(dom.searchHistoryList.innerHTML).toContain("dulu");
    });

    it("does not restart the debounce timer for the same query typed twice", () => {
      initSearchInputEvents();
      dom.searchInput.value = "sama";
      dom.searchInput.dispatchEvent(new Event("input"));
      vi.advanceTimersByTime(500);
      expect(wsSend).toHaveBeenCalledTimes(1);

      dom.searchInput.dispatchEvent(new Event("input"));
      vi.advanceTimersByTime(500);
      expect(wsSend).toHaveBeenCalledTimes(1);
    });

    it("Enter triggers an immediate search bypassing the debounce", () => {
      initSearchInputEvents();
      dom.searchInput.value = "dewa 19";
      dom.searchInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));

      expect(wsSend).toHaveBeenCalledWith("search", { query: "dewa 19" });
    });

    it("Enter with an empty/whitespace query does nothing", () => {
      initSearchInputEvents();
      dom.searchInput.value = "   ";
      dom.searchInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("ignores non-Enter keys", () => {
      initSearchInputEvents();
      dom.searchInput.value = "test";
      dom.searchInput.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("search history", () => {
    it("renders history entries on focus when the field is empty", () => {
      historyStore["lunawave_search_history"] = JSON.stringify(["a", "b"]);
      initSearchInputEvents();
      dom.searchInput.value = "";
      dom.searchInput.dispatchEvent(new Event("focus"));

      expect(dom.searchHistoryContainer.style.display).toBe("block");
      expect(dom.searchMsg.style.display).toBe("none");
      expect(dom.searchHistoryList.innerHTML).toContain("a");
      expect(dom.searchHistoryList.innerHTML).toContain("b");
    });

    it("does not render history on focus when the field already has a value", () => {
      initSearchInputEvents();
      dom.searchInput.value = "abc";
      dom.searchInput.dispatchEvent(new Event("focus"));
      expect(dom.searchMsg.style.display).not.toBe("none");
    });

    it("gracefully falls back to an empty history on malformed stored JSON", () => {
      historyStore["lunawave_search_history"] = "not-json";
      initSearchInputEvents();
      dom.searchInput.value = "";
      dom.searchInput.dispatchEvent(new Event("focus"));
      expect(dom.searchHistoryContainer.style.display).toBe("none");
    });

    it("clicking a history item fills the input, searches, and hides the history/results panels", () => {
      historyStore["lunawave_search_history"] = JSON.stringify(["sheila on 7"]);
      initSearchInputEvents();
      dom.searchInput.value = "";
      dom.searchInput.dispatchEvent(new Event("focus"));

      const item = dom.searchHistoryList.querySelector(".search-history-item");
      item.click();

      expect(dom.searchInput.value).toBe("sheila on 7");
      expect(dom.searchMsg.style.display).toBe("block");
      expect(dom.searchHistoryContainer.style.display).toBe("none");
      expect(dom.searchResults.style.display).toBe("none");
      expect(wsSend).toHaveBeenCalledWith("search", { query: "sheila on 7" });
    });

    it("ignores clicks in the history list that don't hit an item", () => {
      historyStore["lunawave_search_history"] = JSON.stringify(["x"]);
      initSearchInputEvents();
      dom.searchHistoryList.click();
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("search-history-clear removes stored history and re-renders (now empty)", () => {
      historyStore["lunawave_search_history"] = JSON.stringify(["x"]);
      initSearchInputEvents();
      dom.searchHistoryClear.click();

      expect(globalThis.safeStorage.remove).toHaveBeenCalledWith("lunawave_search_history");
      expect(dom.searchHistoryContainer.style.display).toBe("none");
    });

    it("caps stored history at 10 entries and moves re-searched queries to the front", () => {
      historyStore["lunawave_search_history"] = JSON.stringify(
        Array.from({ length: 10 }, (_, i) => `q${i}`)
      );
      initSearchInputEvents();
      dom.searchInput.value = "q5";
      dom.searchInput.dispatchEvent(new Event("input"));
      vi.advanceTimersByTime(500);

      const saved = JSON.parse(historyStore["lunawave_search_history"]);
      expect(saved.length).toBe(10);
      expect(saved[0]).toBe("q5");
    });
  });

  describe("search results delegation", () => {
    it("plays the track when a valid .sr-item is clicked", () => {
      initSearchInputEvents();
      dom.searchResults.innerHTML = `<div class="sr-item" data-search-track-str='{"video_id":"v1"}'>row</div>`;
      dom.searchResults.querySelector(".sr-item").click();

      expect(playSearchTrack).toHaveBeenCalledWith({ video_id: "v1" });
    });

    it("swallows malformed track JSON without throwing", () => {
      initSearchInputEvents();
      dom.searchResults.innerHTML = `<div class="sr-item" data-search-track-str="not-json">row</div>`;
      const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});

      expect(() => dom.searchResults.querySelector(".sr-item").click()).not.toThrow();
      expect(errSpy).toHaveBeenCalled();
      expect(playSearchTrack).not.toHaveBeenCalled();
    });

    it("ignores clicks that don't hit a .sr-item", () => {
      initSearchInputEvents();
      dom.searchResults.innerHTML = `<div>plain</div>`;
      dom.searchResults.firstChild.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(playSearchTrack).not.toHaveBeenCalled();
    });
  });
});
