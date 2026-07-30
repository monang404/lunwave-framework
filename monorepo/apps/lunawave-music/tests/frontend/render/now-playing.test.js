import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";
import { emit } from "../../../web/static/shared/js/bus.js";
import {
  renderNowPlaying,
  syncPlayerStateAttr,
  initNowPlayingBusSubscriptions,
} from "../../../web/static/shared/js/render/now-playing.js";

function el(tag = "div") {
  return document.createElement(tag);
}
function elWithStyle(tag = "div") {
  return Object.assign(el(tag), { style: {} });
}

describe("render/now-playing.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.removeAttribute("data-player-state");
    globalThis.getCoverArt = vi.fn().mockResolvedValue(null);
    globalThis.extractDominantColor = vi.fn();

    Object.assign(dom, {
      vinylCover: Object.assign(elWithStyle("img"), { src: "" }),
      vinylIcon: elWithStyle(),
      vinylRecord: el(),
      npThumbIcon: elWithStyle(),
      npEqAnim: elWithStyle(),
      homeEqualizer: elWithStyle(),
      tabHome: el(),
      npTitle: el(),
      npArtist: el(),
      npDurMeta: el(),
    });

    Object.assign(store, {
      current_track: null,
      status: "PAUSED",
      userRole: "admin",
      audio_output: "server",
      lyrics_lines: null,
    });
  });

  afterEach(() => {
    delete globalThis.getCoverArt;
    delete globalThis.extractDominantColor;
  });

  describe("vinyl cover", () => {
    it("clears the cover and shows the icon when there is no current track", () => {
      renderNowPlaying();
      expect(dom.vinylCover.getAttribute("src")).toBe("");
      expect(dom.vinylCover.style.display).toBe("none");
      expect(dom.vinylIcon.style.display).toBe("block");
    });

    it("fetches and applies cover art for a track with a video_id", async () => {
      const track = { video_id: "v1", title: "T" };
      store.current_track = track;
      globalThis.getCoverArt.mockResolvedValue("cover.jpg");
      renderNowPlaying();

      expect(dom.vinylCover.style.display).toBe("none");
      expect(dom.vinylIcon.style.display).toBe("block");

      await Promise.resolve();
      await Promise.resolve();

      expect(dom.vinylCover.src).toContain("cover.jpg");
      expect(dom.vinylCover.style.display).toBe("block");
      expect(dom.vinylIcon.style.display).toBe("none");
    });

    it("ignores a stale cover-art response for a track that has since changed", async () => {
      const track = { video_id: "v1", title: "T" };
      store.current_track = track;
      globalThis.getCoverArt.mockResolvedValue("stale.jpg");
      renderNowPlaying();

      store.current_track = { video_id: "v2", title: "Other" };
      await Promise.resolve();
      await Promise.resolve();

      expect(dom.vinylCover.getAttribute("src")).toBe("");
    });

    it("extracts a dominant color and applies it as CSS variables on tabHome", async () => {
      store.current_track = { video_id: "v1", title: "T" };
      globalThis.getCoverArt.mockResolvedValue("cover.jpg");
      globalThis.extractDominantColor.mockImplementation((_img, cb) => cb({ r: 1, g: 2, b: 3 }));
      const setPropertySpy = vi.spyOn(dom.tabHome.style, "setProperty");
      renderNowPlaying();
      await Promise.resolve();
      await Promise.resolve();

      expect(setPropertySpy).toHaveBeenCalledWith("--color-r", 1);
      expect(setPropertySpy).toHaveBeenCalledWith("--color-g", 2);
      expect(setPropertySpy).toHaveBeenCalledWith("--color-b", 3);
    });

    it("does nothing when vinylCover is absent", () => {
      dom.vinylCover = null;
      expect(() => renderNowPlaying()).not.toThrow();
    });
  });

  describe("playing state / equalizer", () => {
    it("shows the equalizer animation and uses visualizer-active for client/browser output", () => {
      store.status = "PLAYING";
      store.userRole = "client";
      renderNowPlaying();
      expect(dom.npThumbIcon.style.display).toBe("none");
      expect(dom.npEqAnim.style.display).toBe("flex");
      expect(dom.vinylRecord.classList.contains("visualizer-active")).toBe(true);
      expect(dom.vinylRecord.classList.contains("playing")).toBe(true); // set separately below
    });

    it("uses the plain 'playing' record animation for admin/server output", () => {
      store.status = "PLAYING";
      store.userRole = "admin";
      store.audio_output = "server";
      renderNowPlaying();
      expect(dom.vinylRecord.classList.contains("playing")).toBe(true);
      expect(dom.vinylRecord.classList.contains("visualizer-active")).toBe(false);
    });

    it("resets thumb/eq/record classes when not playing", () => {
      store.status = "PAUSED";
      dom.vinylRecord.classList.add("playing", "visualizer-active");
      renderNowPlaying();
      expect(dom.npThumbIcon.style.display).toBe("block");
      expect(dom.npEqAnim.style.display).toBe("none");
      expect(dom.vinylRecord.classList.contains("playing")).toBe(false);
      expect(dom.vinylRecord.classList.contains("visualizer-active")).toBe(false);
    });

    it("shows the home equalizer only while playing with no lyrics", () => {
      store.status = "PLAYING";
      store.lyrics_lines = null;
      renderNowPlaying();
      expect(dom.homeEqualizer.style.display).toBe("flex");
    });

    it("hides the home equalizer once lyrics are available", () => {
      store.status = "PLAYING";
      store.lyrics_lines = ["a"];
      renderNowPlaying();
      expect(dom.homeEqualizer.style.display).toBe("none");
    });
  });

  describe("title/artist text", () => {
    it("shows a loading spinner and the raw title while LOADING", () => {
      store.status = "LOADING";
      store.current_track = { title: "Kisah Cintaku" };
      renderNowPlaying();
      expect(dom.npTitle.innerHTML).toContain("Memuat");
      expect(dom.npArtist.textContent).toBe("Kisah Cintaku");
    });

    it("title-cases the cleaned track title and shows the artist when a track is playing", () => {
      store.status = "PLAYING";
      store.current_track = { title: "kisah cintaku", artist: "sheila on 7", duration: 180 };
      renderNowPlaying();
      expect(dom.npTitle.textContent).toBe("Kisah Cintaku");
      expect(dom.npArtist.textContent).toBe("sheila on 7");
    });

    it("shows a placeholder when there is no current track", () => {
      store.current_track = null;
      renderNowPlaying();
      expect(dom.npTitle.textContent).toBe("Belum ada lagu yang diputar");
      expect(dom.npArtist.textContent).toBe("Cari lagu untuk memulai");
    });
  });

  describe("duration meta", () => {
    it("formats the duration for the current track", () => {
      store.current_track = { title: "T", duration: 125 };
      renderNowPlaying();
      expect(dom.npDurMeta.textContent).toBe("02:05");
    });

    it("clears the duration when there is no current track", () => {
      store.current_track = null;
      renderNowPlaying();
      expect(dom.npDurMeta.textContent).toBe("");
    });
  });

  describe("syncPlayerStateAttr", () => {
    it("sets IDLE when there is no current track", () => {
      store.current_track = null;
      syncPlayerStateAttr();
      expect(document.body.getAttribute("data-player-state")).toBe("IDLE");
    });

    it("sets IDLE for a track with no video_id unless status is LOADING", () => {
      store.current_track = { title: "T" };
      store.status = "PAUSED";
      syncPlayerStateAttr();
      expect(document.body.getAttribute("data-player-state")).toBe("IDLE");
    });

    it("reflects LOADING even without a video_id yet", () => {
      store.current_track = { title: "T" };
      store.status = "LOADING";
      syncPlayerStateAttr();
      expect(document.body.getAttribute("data-player-state")).toBe("LOADING");
    });

    it("reflects the live status for a track with a video_id", () => {
      store.current_track = { video_id: "v1" };
      store.status = "PLAYING";
      syncPlayerStateAttr();
      expect(document.body.getAttribute("data-player-state")).toBe("PLAYING");
    });
  });

  describe("initNowPlayingBusSubscriptions", () => {
    it("wires now-playing:changed to renderNowPlaying", () => {
      initNowPlayingBusSubscriptions();
      store.current_track = { title: "T", artist: "A" };
      emit("now-playing:changed");
      expect(dom.npArtist.textContent).toBe("A");
    });

    it("wires now-playing:sync-state-attr to syncPlayerStateAttr", () => {
      initNowPlayingBusSubscriptions();
      store.current_track = { video_id: "v1" };
      store.status = "PLAYING";
      emit("now-playing:sync-state-attr");
      expect(document.body.getAttribute("data-player-state")).toBe("PLAYING");
    });
  });
});
