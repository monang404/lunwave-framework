import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { emit } from "../../../web/static/shared/js/bus.js";

vi.mock("../../../web/static/shared/js/render/search.js", () => ({
  buildSrThumbHtml: vi.fn(() => "<img class=\"lazy-cover\">"),
  playSearchTrack: vi.fn(),
  showActionModal: vi.fn(),
}));

import {
  enterDiscoverSearchLoading,
  exitDiscoverSearchMode,
  renderDiscoverSearchResults,
  handleDiscoverSearchError,
  initDiscoverSearchBusSubscriptions,
} from "../../../web/static/shared/js/render/discover-search.js";
import { playSearchTrack, showActionModal } from "../../../web/static/shared/js/render/search.js";

function elStyle() {
  return Object.assign(document.createElement("div"), { style: {} });
}

describe("render/discover-search.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.loadLazyCovers = vi.fn();

    Object.assign(dom, {
      tasteBlock: elStyle(),
      filterBar: elStyle(),
      filterScopeHint: elStyle(),
      rowForYouLabel: elStyle(),
      rowForYou: elStyle(),
      rowGenreAffinityLabel: elStyle(),
      rowGenreAffinity: elStyle(),
      rowUnheardLabel: elStyle(),
      rowUnheard: elStyle(),
      discoverSearchStatus: elStyle(),
      discoverSearchResults: elStyle(),
    });

    // Ensure a known default: not in search mode (module-scope flag reset).
    exitDiscoverSearchMode();
    vi.clearAllMocks();
  });

  afterEach(() => {
    delete globalThis.loadLazyCovers;
  });

  describe("enterDiscoverSearchLoading", () => {
    it("hides the personalization blocks and shows a loading spinner", () => {
      enterDiscoverSearchLoading("peterpan");
      expect(dom.tasteBlock.style.display).toBe("none");
      expect(dom.filterBar.style.display).toBe("none");
      expect(dom.discoverSearchStatus.innerHTML).toContain("Mencari...");
      expect(dom.discoverSearchStatus.style.display).toBe("block");
      expect(dom.discoverSearchResults.innerHTML).toBe("");
      expect(dom.discoverSearchResults.style.display).toBe("none");
    });

    it("does not throw when the personalization/status elements are missing", () => {
      Object.assign(dom, {
        tasteBlock: null,
        discoverSearchStatus: null,
        discoverSearchResults: null,
      });
      expect(() => enterDiscoverSearchLoading("q")).not.toThrow();
    });
  });

  describe("exitDiscoverSearchMode", () => {
    it("re-shows the personalization blocks and clears status/results", () => {
      enterDiscoverSearchLoading("q");
      exitDiscoverSearchMode();

      expect(dom.tasteBlock.style.display).toBe("");
      expect(dom.filterBar.style.display).toBe("");
      expect(dom.discoverSearchStatus.innerHTML).toBe("");
      expect(dom.discoverSearchStatus.style.display).toBe("none");
      expect(dom.discoverSearchResults.innerHTML).toBe("");
      expect(dom.discoverSearchResults.style.display).toBe("none");
    });

    it("deactivates search mode so results/errors are then ignored", () => {
      enterDiscoverSearchLoading("q");
      exitDiscoverSearchMode();
      renderDiscoverSearchResults([{ video_id: "v1", title: "T", artist: "A", duration: 10 }]);
      expect(dom.discoverSearchResults.innerHTML).toBe("");
    });
  });

  describe("renderDiscoverSearchResults", () => {
    it("ignores stale results when search mode is not active", () => {
      renderDiscoverSearchResults([{ video_id: "v1", title: "T", artist: "A", duration: 10 }]);
      expect(dom.discoverSearchResults.innerHTML).toBe("");
    });

    it("shows a 'not found' status for an empty result set", () => {
      enterDiscoverSearchLoading("q");
      renderDiscoverSearchResults([]);
      expect(dom.discoverSearchResults.style.display).toBe("none");
      expect(dom.discoverSearchStatus.textContent).toBe("Tidak ditemukan hasil.");
      expect(dom.discoverSearchStatus.style.display).toBe("block");
    });

    it("renders one .sr-item per track and clears the status", () => {
      enterDiscoverSearchLoading("q");
      renderDiscoverSearchResults([
        { video_id: "v1", title: "kisah cintaku", artist: "Sheila On 7", duration: 245 },
      ]);
      expect(dom.discoverSearchStatus.style.display).toBe("none");
      expect(dom.discoverSearchResults.style.display).toBe("flex");
      const item = dom.discoverSearchResults.querySelector(".sr-item");
      expect(item.dataset.videoId).toBe("v1");
      expect(item.querySelector(".sr-duration").textContent).toBe("04:05");
    });

    it("truncates long artist names", () => {
      enterDiscoverSearchLoading("q");
      renderDiscoverSearchResults([
        { video_id: "v1", title: "T", artist: "B".repeat(30), duration: 10 },
      ]);
      const meta = dom.discoverSearchResults.querySelector(".sr-meta");
      expect(meta.textContent).toBe("B".repeat(22) + "...");
    });

    it("clicking a result plays the track", () => {
      enterDiscoverSearchLoading("q");
      renderDiscoverSearchResults([{ video_id: "v1", title: "T", artist: "A", duration: 10 }]);
      dom.discoverSearchResults.querySelector(".sr-item").click();
      expect(playSearchTrack).toHaveBeenCalledWith(
        expect.objectContaining({ video_id: "v1" })
      );
    });

    it("clicking the 3-dots button opens the action modal instead of playing", () => {
      enterDiscoverSearchLoading("q");
      renderDiscoverSearchResults([{ video_id: "v1", title: "T", artist: "A", duration: 10 }]);
      const moreBtn = dom.discoverSearchResults.querySelector(".sr-more-btn");
      const event = new MouseEvent("click", { bubbles: true, cancelable: true });
      const stopSpy = vi.spyOn(event, "stopPropagation");
      moreBtn.dispatchEvent(event);

      expect(stopSpy).toHaveBeenCalled();
      expect(showActionModal).toHaveBeenCalledWith(
        expect.objectContaining({ video_id: "v1" })
      );
      expect(playSearchTrack).not.toHaveBeenCalled();
    });

    it("triggers lazy cover loading after rendering results", () => {
      enterDiscoverSearchLoading("q");
      renderDiscoverSearchResults([{ video_id: "v1", title: "T", artist: "A", duration: 10 }]);
      expect(globalThis.loadLazyCovers).toHaveBeenCalled();
    });

    it("is a no-op when dom.discoverSearchResults is missing", () => {
      enterDiscoverSearchLoading("q");
      dom.discoverSearchResults = null;
      expect(() =>
        renderDiscoverSearchResults([{ video_id: "v1", title: "T", artist: "A", duration: 10 }])
      ).not.toThrow();
    });
  });

  describe("handleDiscoverSearchError", () => {
    it("does nothing when search mode is not active", () => {
      handleDiscoverSearchError();
      expect(dom.discoverSearchStatus.textContent).toBe("");
    });

    it("shows an error message and clears results while active", () => {
      enterDiscoverSearchLoading("q");
      handleDiscoverSearchError();
      expect(dom.discoverSearchResults.innerHTML).toBe("");
      expect(dom.discoverSearchResults.style.display).toBe("none");
      expect(dom.discoverSearchStatus.textContent).toBe("Terjadi kesalahan saat mencari. Coba lagi.");
      expect(dom.discoverSearchStatus.style.display).toBe("block");
    });
  });

  describe("initDiscoverSearchBusSubscriptions", () => {
    it("wires discover:search-loading-enter to enterDiscoverSearchLoading", () => {
      initDiscoverSearchBusSubscriptions();
      emit("discover:search-loading-enter", "q");
      expect(dom.discoverSearchStatus.style.display).toBe("block");
    });

    it("wires discover:search-results to renderDiscoverSearchResults", () => {
      initDiscoverSearchBusSubscriptions();
      emit("discover:search-loading-enter", "q");
      emit("discover:search-results", [{ video_id: "v1", title: "T", artist: "A", duration: 10 }]);
      expect(dom.discoverSearchResults.querySelectorAll(".sr-item").length).toBe(1);
    });

    it("wires discover:search-error to handleDiscoverSearchError", () => {
      initDiscoverSearchBusSubscriptions();
      emit("discover:search-loading-enter", "q");
      emit("discover:search-error");
      expect(dom.discoverSearchStatus.textContent).toContain("kesalahan");
    });

    it("wires discover:search-loading-exit to exitDiscoverSearchMode", () => {
      initDiscoverSearchBusSubscriptions();
      emit("discover:search-loading-enter", "q");
      emit("discover:search-loading-exit");
      expect(dom.tasteBlock.style.display).toBe("");
    });
  });
});
