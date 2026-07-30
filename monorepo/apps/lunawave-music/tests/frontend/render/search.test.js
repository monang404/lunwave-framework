import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";
import { emit } from "../../../web/static/shared/js/bus.js";

vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import {
  buildSrThumbHtml,
  renderSearchResults,
  updateSearchPlayingState,
  playSearchTrack,
  showActionModal,
  hideActionModal,
  initSearchBusSubscriptions,
} from "../../../web/static/shared/js/render/search.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

function el(tag = "div") {
  return document.createElement(tag);
}
function elWithStyle(tag = "div") {
  return Object.assign(el(tag), { style: {} });
}

describe("render/search.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.pendingTrack = null;
    globalThis.loadLazyCovers = vi.fn();

    Object.assign(dom, {
      searchResults: elWithStyle(),
      searchMsg: elWithStyle(),
      actionTitle: el(),
      actionDelete: elWithStyle(),
      actionSheet: el(),
      mainOverlay: el(),
    });

    Object.assign(store, {
      search_results: [],
      current_track: null,
      status: "PAUSED",
      userRole: "admin",
    });
  });

  afterEach(() => {
    delete globalThis.pendingTrack;
    delete globalThis.loadLazyCovers;
  });

  describe("buildSrThumbHtml", () => {
    it("builds a lazy-cover img with escaped data attributes from the track", () => {
      const html = buildSrThumbHtml({
        video_id: "v1",
        title: '<b>T</b>',
        artist: "A",
        thumbnail: "thumb.jpg",
      });
      expect(html).toContain('data-vid="v1"');
      expect(html).toContain("data-title=\"&lt;b&gt;T&lt;/b&gt;\"");
      expect(html).toContain('data-artist="A"');
      expect(html).toContain('data-thumb="thumb.jpg"');
    });

    it("tolerates a track with missing fields", () => {
      expect(() => buildSrThumbHtml({})).not.toThrow();
    });
  });

  describe("renderSearchResults", () => {
    it("stores the results and shows a 'not found' message when empty", () => {
      renderSearchResults([]);
      expect(store.search_results).toEqual([]);
      expect(dom.searchMsg.textContent).toBe("Tidak ditemukan hasil.");
      expect(dom.searchMsg.style.display).toBe("block");
      expect(dom.searchResults.style.display).toBe("none");
    });

    it("shows a 'not found' message when results is null/undefined", () => {
      renderSearchResults(null);
      expect(store.search_results).toEqual([]);
      expect(dom.searchMsg.style.display).toBe("block");
    });

    it("renders one .sr-item per track with title/meta/duration", () => {
      renderSearchResults([
        { video_id: "v1", title: "kisah cintaku", artist: "Sheila On 7", duration: 245 },
      ]);
      expect(dom.searchMsg.style.display).toBe("none");
      expect(dom.searchResults.style.display).toBe("flex");

      const item = dom.searchResults.querySelector(".sr-item");
      expect(item.dataset.videoId).toBe("v1");
      expect(JSON.parse(item.dataset.searchTrackStr).video_id).toBe("v1");
      expect(item.querySelector(".sr-title").textContent.length).toBeGreaterThan(0);
      expect(item.querySelector(".sr-meta").textContent).toBe("Sheila On 7");
      expect(item.querySelector(".sr-duration").textContent).toBe("04:05");
      expect(item.querySelector(".sr-more-btn")).toBeTruthy();
    });

    it("truncates long artist names to 22 chars + ellipsis", () => {
      renderSearchResults([
        { video_id: "v1", title: "T", artist: "A".repeat(30), duration: 10 },
      ]);
      const meta = dom.searchResults.querySelector(".sr-meta");
      expect(meta.textContent).toBe("A".repeat(22) + "...");
    });

    it("clicking the 3-dots button opens the action modal without playing the track", () => {
      renderSearchResults([{ video_id: "v1", title: "T", artist: "A", duration: 10 }]);
      const moreBtn = dom.searchResults.querySelector(".sr-more-btn");
      const event = new MouseEvent("click", { bubbles: true, cancelable: true });
      const stopSpy = vi.spyOn(event, "stopPropagation");
      moreBtn.dispatchEvent(event);

      expect(stopSpy).toHaveBeenCalled();
      expect(globalThis.pendingTrack.video_id).toBe("v1");
      expect(dom.actionSheet.classList.contains("open")).toBe(true);
    });

    it("re-renders playing state and triggers lazy cover loading after building results", () => {
      store.current_track = { video_id: "v1" };
      store.status = "PLAYING";
      renderSearchResults([{ video_id: "v1", title: "T", artist: "A", duration: 10 }]);

      const item = dom.searchResults.querySelector(".sr-item");
      expect(item.classList.contains("current")).toBe(true);
      expect(item.classList.contains("playing")).toBe(true);
      expect(globalThis.loadLazyCovers).toHaveBeenCalled();
    });
  });

  describe("updateSearchPlayingState", () => {
    it("is a no-op when dom.searchResults is missing", () => {
      dom.searchResults = null;
      expect(() => updateSearchPlayingState()).not.toThrow();
    });

    it("marks the currently playing item as current+playing and others as neither", () => {
      dom.searchResults.innerHTML = `
        <div class="sr-item" data-video-id="v1"></div>
        <div class="sr-item" data-video-id="v2"></div>
      `;
      store.current_track = { video_id: "v2" };
      store.status = "PLAYING";
      updateSearchPlayingState();

      const [item1, item2] = dom.searchResults.querySelectorAll(".sr-item");
      expect(item1.classList.contains("current")).toBe(false);
      expect(item2.classList.contains("current")).toBe(true);
      expect(item2.classList.contains("playing")).toBe(true);
    });

    it("marks current but not playing when paused", () => {
      dom.searchResults.innerHTML = `<div class="sr-item" data-video-id="v1"></div>`;
      store.current_track = { video_id: "v1" };
      store.status = "PAUSED";
      updateSearchPlayingState();

      const item = dom.searchResults.querySelector(".sr-item");
      expect(item.classList.contains("current")).toBe(true);
      expect(item.classList.contains("playing")).toBe(false);
    });

    it("triggers lazy cover loading when available", () => {
      updateSearchPlayingState();
      expect(globalThis.loadLazyCovers).toHaveBeenCalled();
    });

    it("does not throw when loadLazyCovers is unavailable", () => {
      delete globalThis.loadLazyCovers;
      expect(() => updateSearchPlayingState()).not.toThrow();
    });
  });

  describe("playSearchTrack", () => {
    it("plays the track for admins", () => {
      playSearchTrack({ video_id: "v1" });
      expect(wsSend).toHaveBeenCalledWith("play_track", { video_id: "v1" });
    });

    it("does nothing for non-admins", () => {
      store.userRole = "client";
      playSearchTrack({ video_id: "v1" });
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("does nothing when there is no track", () => {
      playSearchTrack(null);
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("showActionModal / hideActionModal", () => {
    it("shows the title, sheet and overlay, and stores the pending track", () => {
      showActionModal({ title: "Kangen", video_id: "v1" });
      expect(globalThis.pendingTrack.title).toBe("Kangen");
      expect(dom.actionTitle.textContent).toBe("Kangen");
      expect(dom.actionSheet.classList.contains("open")).toBe(true);
      expect(dom.mainOverlay.classList.contains("open")).toBe(true);
    });

    it("shows the delete button for locally cached/downloaded tracks", () => {
      showActionModal({ title: "T", is_cached: true });
      expect(dom.actionDelete.style.display).toBe("block");
    });

    it("hides the delete button for tracks that are not cached/local", () => {
      showActionModal({ title: "T" });
      expect(dom.actionDelete.style.display).toBe("none");
    });

    it("hideActionModal closes the sheet/overlay and clears the pending track", () => {
      showActionModal({ title: "T" });
      hideActionModal();
      expect(dom.actionSheet.classList.contains("open")).toBe(false);
      expect(dom.mainOverlay.classList.contains("open")).toBe(false);
      expect(globalThis.pendingTrack).toBeNull();
    });

    it("does not throw when actionSheet/mainOverlay are missing", () => {
      dom.actionSheet = null;
      dom.mainOverlay = null;
      expect(() => showActionModal({ title: "T" })).not.toThrow();
      expect(() => hideActionModal()).not.toThrow();
    });
  });

  describe("initSearchBusSubscriptions", () => {
    it("wires search:results to renderSearchResults", () => {
      initSearchBusSubscriptions();
      emit("search:results", [{ video_id: "v1", title: "T", artist: "A", duration: 5 }]);
      expect(dom.searchResults.querySelectorAll(".sr-item").length).toBe(1);
    });

    it("wires search:playing-state to updateSearchPlayingState", () => {
      dom.searchResults.innerHTML = `<div class="sr-item" data-video-id="v1"></div>`;
      store.current_track = { video_id: "v1" };
      store.status = "PLAYING";
      initSearchBusSubscriptions();
      emit("search:playing-state");
      expect(dom.searchResults.querySelector(".sr-item").classList.contains("playing")).toBe(true);
    });

    it("wires search:action-modal-open to showActionModal", () => {
      initSearchBusSubscriptions();
      emit("search:action-modal-open", { title: "Opened" });
      expect(dom.actionTitle.textContent).toBe("Opened");
    });

    it("wires search:action-modal-close to hideActionModal", () => {
      showActionModal({ title: "T" });
      initSearchBusSubscriptions();
      emit("search:action-modal-close");
      expect(globalThis.pendingTrack).toBeNull();
    });
  });
});
