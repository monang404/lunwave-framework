import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";

vi.mock("../../../web/static/shared/js/bus.js", () => ({ emit: vi.fn() }));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import { initDiscoverSearchEvents } from "../../../web/static/shared/js/events/discover-search-events.js";
import { emit } from "../../../web/static/shared/js/bus.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

function el(tag = "div") {
  return document.createElement(tag);
}

describe("events/discover-search-events.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    globalThis.getDecade = undefined;

    Object.assign(store, {
      discover_for_you: [],
      discover_genre_affinity_artists: [],
      discover_unheard: [],
    });

    Object.assign(dom, {
      discoverSearchInput: Object.assign(document.createElement("input"), { value: "" }),
      discoverSearchClearBtn: Object.assign(el(), { style: {} }),
      discoverSearchFilterRow: Object.assign(el(), { style: {} }),
      discoverSearchKategoriToggle: (() => {
        const wrap = el();
        wrap.innerHTML = `
          <button data-kategori="all" class="active">Semua</button>
          <button data-kategori="lagu">Lagu</button>
        `;
        return wrap;
      })(),
      discoverSearchDecadeBtn: el("button"),
      discoverSearchDecadeContainer: el(),
      discoverSearchDecadeChips: el(),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    globalThis.store = undefined;
    globalThis.getDecade = undefined;
  });

  it("does nothing when discoverSearchInput is absent (markup not present)", () => {
    dom.discoverSearchInput = null;
    expect(() => initDiscoverSearchEvents()).not.toThrow();
  });

  it("clearBtn resets the input, filters and emits search-loading-exit", () => {
    initDiscoverSearchEvents();
    dom.discoverSearchInput.value = "test query";
    dom.discoverSearchClearBtn.click();

    expect(dom.discoverSearchInput.value).toBe("");
    expect(dom.discoverSearchClearBtn.style.display).toBe("none");
    expect(dom.discoverSearchFilterRow.style.display).toBe("none");
    expect(emit).toHaveBeenCalledWith("discover:search-loading-exit");
  });

  it("typing debounces the search request by 500ms and shows the filter row", () => {
    initDiscoverSearchEvents();
    dom.discoverSearchInput.value = "peterpan";
    dom.discoverSearchInput.dispatchEvent(new Event("input"));

    expect(dom.discoverSearchFilterRow.style.display).toBe("");
    expect(dom.discoverSearchClearBtn.style.display).toBe("block");
    expect(wsSend).not.toHaveBeenCalled();

    vi.advanceTimersByTime(500);

    expect(emit).toHaveBeenCalledWith("discover:search-loading-enter", "peterpan");
    expect(wsSend).toHaveBeenCalledWith("discover_search", {
      query: "peterpan",
      kategori: "all",
      decade: "all",
    });
  });

  it("clearing the input (empty/whitespace) resets filters instead of searching", () => {
    initDiscoverSearchEvents();
    dom.discoverSearchInput.value = "   ";
    dom.discoverSearchInput.dispatchEvent(new Event("input"));

    expect(dom.discoverSearchFilterRow.style.display).toBe("none");
    expect(emit).toHaveBeenCalledWith("discover:search-loading-exit");

    vi.advanceTimersByTime(500);
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("re-typing cancels the previous debounce timer", () => {
    initDiscoverSearchEvents();
    dom.discoverSearchInput.value = "she";
    dom.discoverSearchInput.dispatchEvent(new Event("input"));
    vi.advanceTimersByTime(300);

    dom.discoverSearchInput.value = "sheila on 7";
    dom.discoverSearchInput.dispatchEvent(new Event("input"));
    vi.advanceTimersByTime(300);
    expect(wsSend).not.toHaveBeenCalled();

    vi.advanceTimersByTime(200);
    expect(wsSend).toHaveBeenCalledTimes(1);
    expect(wsSend).toHaveBeenCalledWith("discover_search", {
      query: "sheila on 7",
      kategori: "all",
      decade: "all",
    });
  });

  it("Enter triggers an immediate search and stops propagation, bypassing the debounce", () => {
    initDiscoverSearchEvents();
    dom.discoverSearchInput.value = "dewa 19";
    const event = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true });
    const stopSpy = vi.spyOn(event, "stopPropagation");
    dom.discoverSearchInput.dispatchEvent(event);

    expect(stopSpy).toHaveBeenCalled();
    expect(wsSend).toHaveBeenCalledWith("discover_search", {
      query: "dewa 19",
      kategori: "all",
      decade: "all",
    });
  });

  it("Enter with an empty query does nothing besides stopping propagation", () => {
    initDiscoverSearchEvents();
    dom.discoverSearchInput.value = "  ";
    const event = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true });
    dom.discoverSearchInput.dispatchEvent(event);
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("non-Enter keydown still stops propagation but triggers no search", () => {
    initDiscoverSearchEvents();
    dom.discoverSearchInput.value = "test";
    const event = new KeyboardEvent("keydown", { key: "a", bubbles: true, cancelable: true });
    const stopSpy = vi.spyOn(event, "stopPropagation");
    dom.discoverSearchInput.dispatchEvent(event);
    expect(stopSpy).toHaveBeenCalled();
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("clicking a kategori button activates it and re-searches with the current query", () => {
    initDiscoverSearchEvents();
    dom.discoverSearchInput.value = "query1";
    const laguBtn = dom.discoverSearchKategoriToggle.querySelector('[data-kategori="lagu"]');
    laguBtn.click();

    expect(laguBtn.classList.contains("active")).toBe(true);
    expect(wsSend).toHaveBeenCalledWith("discover_search", {
      query: "query1",
      kategori: "lagu",
      decade: "all",
    });
  });

  it("clicking a kategori button with an empty query does not trigger a search", () => {
    initDiscoverSearchEvents();
    const laguBtn = dom.discoverSearchKategoriToggle.querySelector('[data-kategori="lagu"]');
    laguBtn.click();
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("clicking outside the kategori buttons (but within the toggle) is ignored", () => {
    initDiscoverSearchEvents();
    dom.discoverSearchKategoriToggle.click();
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("decadeBtn toggles the dropdown open state and stops propagation", () => {
    initDiscoverSearchEvents();
    const event = new MouseEvent("click", { bubbles: true, cancelable: true });
    const stopSpy = vi.spyOn(event, "stopPropagation");
    dom.discoverSearchDecadeBtn.dispatchEvent(event);

    expect(stopSpy).toHaveBeenCalled();
    expect(dom.discoverSearchDecadeContainer.classList.contains("open")).toBe(true);
  });

  it("clicking anywhere else in the document closes the decade dropdown", () => {
    initDiscoverSearchEvents();
    dom.discoverSearchDecadeContainer.classList.add("open");
    document.body.click();
    expect(dom.discoverSearchDecadeContainer.classList.contains("open")).toBe(false);
  });

  it("BUG: buildDecadeOptions checks globalThis.store (never set anywhere in the app) " +
     "instead of the imported store, so decades never actually render in production",
    () => {
      store.discover_for_you = [{ tahun_aktif: "2003" }];
      store.discover_genre_affinity_artists = [{ tahun_aktif: "1998" }];
      // globalThis.store intentionally left unset, matching real app behavior.
      initDiscoverSearchEvents();

      const buttons = dom.discoverSearchDecadeChips.querySelectorAll("button");
      expect(buttons.length).toBe(1); // only the "Semua Era" fallback
      expect(dom.discoverSearchDecadeChips.innerHTML).toContain("Semua Era");
    }
  );

  it("renders decades derived from personalization lists when globalThis.store happens to be set", () => {
    store.discover_for_you = [{ tahun_aktif: "2003" }];
    store.discover_genre_affinity_artists = [{ tahun_aktif: "1998" }];
    globalThis.store = store;
    initDiscoverSearchEvents();

    expect(dom.discoverSearchDecadeChips.innerHTML).toContain('data-value="2000"');
    expect(dom.discoverSearchDecadeChips.innerHTML).toContain('data-value="1990"');
    expect(dom.discoverSearchDecadeChips.innerHTML).toContain("Semua Era");
  });

  it("selecting a decade chip activates it, updates the button label, and re-searches", () => {
    store.discover_unheard = [{ tahun_aktif: "2010" }];
    globalThis.store = store;
    initDiscoverSearchEvents();
    dom.discoverSearchInput.value = "query2";

    const chip = dom.discoverSearchDecadeChips.querySelector('[data-value="2010"]');
    chip.click();

    expect(chip.classList.contains("active")).toBe(true);
    expect(dom.discoverSearchDecadeBtn.innerHTML).toContain("2010an");
    expect(wsSend).toHaveBeenCalledWith("discover_search", {
      query: "query2",
      kategori: "all",
      decade: "2010",
    });
  });

  it("clicking a decade chip with an empty query does not search", () => {
    store.discover_unheard = [{ tahun_aktif: "2010" }];
    globalThis.store = store;
    initDiscoverSearchEvents();
    const chip = dom.discoverSearchDecadeChips.querySelector('[data-value="2010"]');
    chip.click();
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("uses globalThis.getDecade override when present (and globalThis.store is set)", () => {
    globalThis.getDecade = vi.fn().mockReturnValue(1970);
    globalThis.store = store;
    store.discover_for_you = [{ tahun_aktif: "1975" }];
    initDiscoverSearchEvents();

    expect(globalThis.getDecade).toHaveBeenCalledWith("1975");
    expect(dom.discoverSearchDecadeChips.innerHTML).toContain('data-value="1970"');
  });

  it("skips artists whose year cannot be resolved to a decade", () => {
    store.discover_for_you = [{ tahun_aktif: null }, { tahun_aktif: "not-a-year" }];
    initDiscoverSearchEvents();
    // Only the "Semua Era" fallback option should be present.
    const buttons = dom.discoverSearchDecadeChips.querySelectorAll("button");
    expect(buttons.length).toBe(1);
  });
});
