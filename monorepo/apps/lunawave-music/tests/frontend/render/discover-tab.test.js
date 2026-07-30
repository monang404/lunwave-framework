import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";
import { emit } from "../../../web/static/shared/js/bus.js";

vi.mock("../../../web/static/shared/js/render/navigation.js", () => ({
  switchTab: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/render/search.js", () => ({
  showActionModal: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/render/toast.js", () => ({
  showLogToast: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import {
  renderDiscoverTab,
  updateDiscoverPlayingState,
  renderRecentRow,
  initDiscoverTabBusSubscriptions,
} from "../../../web/static/shared/js/render/discover-tab.js";
import { switchTab } from "../../../web/static/shared/js/render/navigation.js";
import { showActionModal } from "../../../web/static/shared/js/render/search.js";
import { showLogToast } from "../../../web/static/shared/js/render/toast.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

function el(tag = "div") {
  return document.createElement(tag);
}

describe("render/discover-tab.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.loadLazyCovers = vi.fn();
    document.body.innerHTML = "";

    Object.assign(dom, {
      discArtists: el(),
      discGenres: el(),
      discFavorites: el(),
      discCached: el(),
      discRecent: el(),
    });

    Object.assign(store, {
      discover_featured_artists: [],
      discover_featured_genres: [],
      discover_favorites: [],
      discover_cached: [],
      discover_recent: [],
      current_track: null,
      status: "PAUSED",
      userRole: "admin",
    });
  });

  afterEach(() => {
    delete globalThis.loadLazyCovers;
  });

  describe("renderDiscoverTab / hashtag clouds (artists & genres)", () => {
    it("renders a hashtag pill per featured artist", () => {
      store.discover_featured_artists = [{ nama: "Sheila On 7", click_count: 3 }];
      renderDiscoverTab();
      const pill = dom.discArtists.querySelector(".hashtag-pill");
      expect(pill.textContent).toBe("#SheilaOn7");
      expect(pill.dataset.artist).toBe("Sheila On 7");
    });

    it("caps the visible hashtag pills and shows a '+N lainnya' expand button", () => {
      store.discover_featured_artists = Array.from({ length: 20 }, (_, i) => ({ nama: `A${i}` }));
      renderDiscoverTab();
      expect(dom.discArtists.querySelectorAll(".hashtag-pill").length).toBe(16);
      const moreBtn = dom.discArtists.querySelector(".hashtag-more-btn");
      expect(moreBtn.dataset.remaining).toBe("4");
    });

    it("expanding the hashtag cloud shows all pills plus a hide button", () => {
      store.discover_featured_artists = Array.from({ length: 20 }, (_, i) => ({ nama: `A${i}` }));
      renderDiscoverTab();
      dom.discArtists.querySelector(".hashtag-more-btn").click();
      expect(dom.discArtists.querySelectorAll(".hashtag-pill").length).toBe(20);
      expect(dom.discArtists.querySelector(".hide-btn")).toBeTruthy();
    });

    it("collapsing back via the hide button restores the capped view", () => {
      store.discover_featured_artists = Array.from({ length: 20 }, (_, i) => ({ nama: `A${i}` }));
      renderDiscoverTab();
      dom.discArtists.querySelector(".hashtag-more-btn").click();
      dom.discArtists.querySelector(".hide-btn").click();
      expect(dom.discArtists.querySelectorAll(".hashtag-pill").length).toBe(16);
    });

    it("shows no expand button when there are 16 or fewer artists", () => {
      store.discover_featured_artists = Array.from({ length: 5 }, (_, i) => ({ nama: `A${i}` }));
      renderDiscoverTab();
      expect(dom.discArtists.querySelector(".hashtag-more-btn")).toBeNull();
    });

    it("clears the container when there are no featured artists", () => {
      dom.discArtists.innerHTML = "<div>stale</div>";
      store.discover_featured_artists = [];
      renderDiscoverTab();
      expect(dom.discArtists.innerHTML).toBe("");
    });

    it("clicking an artist pill enqueues that artist's songs and switches to home for admins", () => {
      store.discover_featured_artists = [{ nama: "Dewa 19" }];
      renderDiscoverTab();
      dom.discArtists.querySelector(".hashtag-pill").click();

      expect(wsSend).toHaveBeenCalledWith("enqueue_artist_songs", { artist: "Dewa 19" });
      expect(showLogToast).toHaveBeenCalledWith(expect.stringContaining("Dewa 19"));
      expect(switchTab).toHaveBeenCalledWith("home");
    });

    it("clicking an artist pill as a non-admin only toasts, without enqueueing", () => {
      store.userRole = "client";
      store.discover_featured_artists = [{ nama: "Dewa 19" }];
      renderDiscoverTab();
      dom.discArtists.querySelector(".hashtag-pill").click();

      expect(wsSend).not.toHaveBeenCalled();
      expect(showLogToast).toHaveBeenCalledWith("Hanya admin yang bisa memutar musik");
    });

    it("renders and handles genre pills the same way, using the genre wsSend event", () => {
      store.discover_featured_genres = [{ nama_genre: "Pop Indonesia" }];
      renderDiscoverTab();
      const pill = dom.discGenres.querySelector(".hashtag-pill");
      expect(pill.dataset.genre).toBe("Pop Indonesia");

      pill.click();
      expect(wsSend).toHaveBeenCalledWith("enqueue_genre_songs", { genre: "Pop Indonesia" });
    });

    it("ignores clicks that don't hit a pill", () => {
      store.discover_featured_artists = [{ nama: "A" }];
      renderDiscoverTab();
      dom.discArtists.click();
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("renderDiscoverTab / favorites & cached track lists", () => {
    it("shows an empty-state message when there are no favorites", () => {
      renderDiscoverTab();
      expect(dom.discFavorites.innerHTML).toContain("Belum ada lagu favorit");
    });

    it("renders .sr-item rows for favorites with escaped title/duration", () => {
      store.discover_favorites = [
        { video_id: "v1", title: "kisah cintaku", artist: "Sheila On 7", duration: 245 },
      ];
      renderDiscoverTab();
      const item = dom.discFavorites.querySelector(".sr-item");
      expect(item.dataset.vid).toBe("v1");
      expect(item.querySelector(".sr-duration").textContent).toBe("04:05");
    });

    it("shows a 'cache' tag for locally stored favorite tracks", () => {
      store.discover_favorites = [{ video_id: "v1", title: "T", artist: "A", duration: 10, local_path: "/x" }];
      renderDiscoverTab();
      expect(dom.discFavorites.innerHTML).toContain("disc-tag");
    });

    it("caps favorites preview at 5 with a 'Lihat Semua' expand button", () => {
      store.discover_favorites = Array.from({ length: 8 }, (_, i) => ({
        video_id: `v${i}`, title: `T${i}`, artist: "A", duration: 10,
      }));
      renderDiscoverTab();
      expect(dom.discFavorites.querySelectorAll(".sr-item").length).toBe(5);
      const expandBtn = dom.discFavorites.querySelector(".list-expand-btn");
      expect(expandBtn.textContent).toContain("Lihat Semua (8)");
    });

    it("expanding the favorites list shows all tracks and re-triggers lazy cover loading", () => {
      store.discover_favorites = Array.from({ length: 8 }, (_, i) => ({
        video_id: `v${i}`, title: `T${i}`, artist: "A", duration: 10,
      }));
      renderDiscoverTab();
      globalThis.loadLazyCovers.mockClear();
      dom.discFavorites.querySelector(".list-expand-btn").click();
      expect(dom.discFavorites.querySelectorAll(".sr-item").length).toBe(8);
      expect(globalThis.loadLazyCovers).toHaveBeenCalled();
    });

    it("shows an empty-state message for the cached list distinct from favorites", () => {
      renderDiscoverTab();
      expect(dom.discCached.innerHTML).toContain("Tidak ada file tersimpan");
    });

    it("renders cached track rows without the cache tag markup used by favorites", () => {
      store.discover_cached = [{ video_id: "v1", title: "T", artist: "A", duration: 10 }];
      renderDiscoverTab();
      expect(dom.discCached.querySelector(".sr-item")).toBeTruthy();
    });

    it("triggers lazy cover loading after a full render pass", () => {
      renderDiscoverTab();
      expect(globalThis.loadLazyCovers).toHaveBeenCalled();
    });

    it("does not throw when the container elements are all missing", () => {
      Object.assign(dom, { discArtists: null, discGenres: null, discFavorites: null, discCached: null, discRecent: null });
      expect(() => renderDiscoverTab()).not.toThrow();
    });
  });

  describe("updateDiscoverPlayingState", () => {
    it("marks the currently playing item as current+playing across all lists", () => {
      dom.discFavorites.innerHTML = `<div class="sr-item" data-vid="v1"></div>`;
      dom.discCached.innerHTML = `<div class="sr-item" data-vid="v1"></div>`;
      dom.discRecent.innerHTML = `<div class="sr-item" data-vid="v1"></div>`;
      document.body.innerHTML += `<div id="home-recent-list"><div class="home-recent-item" data-vid="v1"></div></div>`;

      store.current_track = { video_id: "v1" };
      store.status = "PLAYING";
      updateDiscoverPlayingState();

      expect(dom.discFavorites.querySelector(".sr-item").classList.contains("playing")).toBe(true);
      expect(dom.discCached.querySelector(".sr-item").classList.contains("playing")).toBe(true);
      expect(dom.discRecent.querySelector(".sr-item").classList.contains("playing")).toBe(true);
      expect(document.querySelector(".home-recent-item").classList.contains("playing")).toBe(true);
    });

    it("marks items as current-but-not-playing when paused", () => {
      dom.discFavorites.innerHTML = `<div class="sr-item" data-vid="v1"></div>`;
      store.current_track = { video_id: "v1" };
      store.status = "PAUSED";
      updateDiscoverPlayingState();
      const item = dom.discFavorites.querySelector(".sr-item");
      expect(item.classList.contains("current")).toBe(true);
      expect(item.classList.contains("playing")).toBe(false);
    });

    it("clears state on non-matching items", () => {
      dom.discFavorites.innerHTML = `<div class="sr-item current playing" data-vid="other"></div>`;
      store.current_track = { video_id: "v1" };
      store.status = "PLAYING";
      updateDiscoverPlayingState();
      const item = dom.discFavorites.querySelector(".sr-item");
      expect(item.classList.contains("current")).toBe(false);
      expect(item.classList.contains("playing")).toBe(false);
    });

    it("does not throw when there is no home-recent-list in the document", () => {
      expect(() => updateDiscoverPlayingState()).not.toThrow();
    });
  });

  describe("renderRecentRow", () => {
    beforeEach(() => {
      document.body.innerHTML = `<div id="home-recent-list"></div>`;
    });

    it("does nothing when #home-recent-list is missing", () => {
      document.body.innerHTML = "";
      expect(() => renderRecentRow()).not.toThrow();
    });

    it("shows an empty-state message when there is no recent history", () => {
      store.discover_recent = [];
      renderRecentRow();
      expect(document.getElementById("home-recent-list").textContent).toContain("Belum ada riwayat putar");
    });

    it("renders up to 5 recent tracks, marking the currently playing one", () => {
      store.discover_recent = Array.from({ length: 8 }, (_, i) => ({
        video_id: `v${i}`, title: `T${i}`, artist: "A",
      }));
      store.current_track = { video_id: "v2" };
      renderRecentRow();

      const container = document.getElementById("home-recent-list");
      const items = container.querySelectorAll(".home-recent-item");
      expect(items.length).toBe(5);
      expect(container.querySelector('[data-vid="v2"]').classList.contains("current")).toBe(true);
    });

    it("triggers lazy cover loading after rendering", () => {
      store.discover_recent = [{ video_id: "v1", title: "T", artist: "A" }];
      renderRecentRow();
      expect(globalThis.loadLazyCovers).toHaveBeenCalled();
    });

    it("clicking a recent item plays it for admins", () => {
      store.discover_recent = [{ video_id: "v1", title: "T", artist: "A" }];
      renderRecentRow();
      document.querySelector(".home-recent-item").click();
      expect(wsSend).toHaveBeenCalledWith(
        "play_track",
        expect.objectContaining({ video_id: "v1" })
      );
    });

    it("does not play the track for non-admins", () => {
      store.userRole = "client";
      store.discover_recent = [{ video_id: "v1", title: "T", artist: "A" }];
      renderRecentRow();
      document.querySelector(".home-recent-item").click();
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("clicking the more button opens the action modal instead of playing", () => {
      store.discover_recent = [{ video_id: "v1", title: "T", artist: "A" }];
      renderRecentRow();
      const moreBtn = document.querySelector(".home-recent-more");
      const event = new MouseEvent("click", { bubbles: true, cancelable: true });
      const stopSpy = vi.spyOn(event, "stopPropagation");
      moreBtn.dispatchEvent(event);

      expect(stopSpy).toHaveBeenCalled();
      expect(showActionModal).toHaveBeenCalledWith(expect.objectContaining({ video_id: "v1" }));
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("swallows malformed track JSON on the more button without throwing", () => {
      store.discover_recent = [{ video_id: "v1", title: "T", artist: "A" }];
      renderRecentRow();
      const moreBtn = document.querySelector(".home-recent-more");
      moreBtn.dataset.track = "not-json";
      expect(() => moreBtn.click()).not.toThrow();
      expect(showActionModal).not.toHaveBeenCalled();
    });
  });

  describe("initDiscoverTabBusSubscriptions", () => {
    it("wires discover:tab-changed to renderDiscoverTab", () => {
      initDiscoverTabBusSubscriptions();
      store.discover_featured_artists = [{ nama: "Wired" }];
      emit("discover:tab-changed");
      expect(dom.discArtists.innerHTML).toContain("Wired");
    });

    it("wires discover:recent-changed to renderRecentRow", () => {
      document.body.innerHTML = `<div id="home-recent-list"></div>`;
      store.discover_recent = [{ video_id: "v1", title: "T", artist: "A" }];
      initDiscoverTabBusSubscriptions();
      emit("discover:recent-changed");
      expect(document.querySelector(".home-recent-item")).toBeTruthy();
    });

    it("wires discover:playing-state to updateDiscoverPlayingState", () => {
      dom.discFavorites.innerHTML = `<div class="sr-item" data-vid="v1"></div>`;
      store.current_track = { video_id: "v1" };
      store.status = "PLAYING";
      initDiscoverTabBusSubscriptions();
      emit("discover:playing-state");
      expect(dom.discFavorites.querySelector(".sr-item").classList.contains("playing")).toBe(true);
    });
  });
});
