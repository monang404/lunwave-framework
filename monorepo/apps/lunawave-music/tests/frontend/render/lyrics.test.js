import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";
import { emit } from "../../../web/static/shared/js/bus.js";
import {
  renderLyrics,
  updateOffsetDisplay,
  initLyricsBusSubscriptions,
} from "../../../web/static/shared/js/render/lyrics.js";

function el(tag = "div") {
  return document.createElement(tag);
}

describe("render/lyrics.js", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Element.prototype.scrollIntoView = vi.fn();
    globalThis.isScrollingLyrics = false;
    document.body.removeAttribute("data-has-lyrics");

    Object.assign(dom, {
      lyricsSheet: el(),
      lyricsContent: el(),
      lyricsCurrent: Object.assign(el(), { className: "" }),
      lyricsPrev: el(),
      lyricsNext: el(),
      lyricsTextContainer: Object.assign(el(), { style: {} }),
      homeEqualizer: Object.assign(el(), { style: {} }),
    });

    Object.assign(store, {
      lyrics_lines: null,
      lyrics_index: 0,
      status: "PAUSED",
      lyrics_offset: 0,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    delete globalThis.isScrollingLyrics;
  });

  describe("renderSheetLyrics (via renderLyrics)", () => {
    it("does nothing when the lyrics sheet is not open", () => {
      store.lyrics_lines = ["a", "b"];
      renderLyrics();
      expect(dom.lyricsContent.innerHTML).toBe("");
    });

    it("shows a fallback message when there are no lyrics", () => {
      dom.lyricsSheet.classList.add("open");
      store.lyrics_lines = [];
      renderLyrics();
      expect(dom.lyricsContent.innerHTML).toContain("Tidak ada lirik tersedia");
    });

    it("renders a window of lines around the current index with past/active/future classes", () => {
      dom.lyricsSheet.classList.add("open");
      store.lyrics_lines = ["l0", "l1", "l2", "l3", "l4"];
      store.lyrics_index = 2;
      renderLyrics();

      expect(dom.lyricsContent.querySelectorAll(".lyric-line.past").length).toBe(2);
      expect(dom.lyricsContent.querySelectorAll(".lyric-line.active").length).toBe(1);
      expect(dom.lyricsContent.querySelectorAll(".lyric-line.future").length).toBe(2);
      expect(dom.lyricsContent.querySelector(".lyric-line.active").textContent).toBe("l2");
    });

    it("escapes HTML in lyric lines", () => {
      dom.lyricsSheet.classList.add("open");
      store.lyrics_lines = ["<script>alert(1)</script>"];
      store.lyrics_index = 0;
      renderLyrics();
      expect(dom.lyricsContent.innerHTML).not.toContain("<script>alert(1)</script>");
      expect(dom.lyricsContent.innerHTML).toContain("&lt;script&gt;");
    });

    it("scrolls the active line into view when not currently scrolling", () => {
      dom.lyricsSheet.classList.add("open");
      store.lyrics_lines = ["l0", "l1"];
      store.lyrics_index = 0;
      renderLyrics();
      expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
    });

    it("does not auto-scroll while the user is actively scrolling", () => {
      dom.lyricsSheet.classList.add("open");
      globalThis.isScrollingLyrics = true;
      store.lyrics_lines = ["l0", "l1"];
      renderLyrics();
      expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
    });

    it("binds wheel/touchmove listeners only once and sets isScrollingLyrics for 3s", () => {
      dom.lyricsSheet.classList.add("open");
      store.lyrics_lines = ["l0"];
      renderLyrics();
      expect(dom.lyricsContent._scrollBound).toBe(true);

      dom.lyricsContent.dispatchEvent(new Event("wheel"));
      expect(globalThis.isScrollingLyrics).toBe(true);

      vi.advanceTimersByTime(3000);
      expect(globalThis.isScrollingLyrics).toBe(false);
    });
  });

  describe("renderHomeLyrics (via renderLyrics)", () => {
    it("does nothing when the home lyrics elements are missing", () => {
      dom.lyricsCurrent = null;
      expect(() => renderLyrics()).not.toThrow();
    });

    it("marks data-has-lyrics=false and shows the equalizer when playing with no lyrics", () => {
      store.lyrics_lines = [];
      store.status = "PLAYING";
      renderLyrics();
      expect(document.body.getAttribute("data-has-lyrics")).toBe("false");
      expect(dom.lyricsTextContainer.style.display).toBe("none");
      expect(dom.homeEqualizer.style.display).toBe("flex");
    });

    it("hides the equalizer when paused with no lyrics", () => {
      store.lyrics_lines = [];
      store.status = "PAUSED";
      renderLyrics();
      expect(dom.homeEqualizer.style.display).toBe("none");
    });

    it("shows the lyrics container and hides the equalizer when lyrics exist", () => {
      store.lyrics_lines = ["Kisah ini", "Tentang cinta"];
      store.lyrics_index = 0;
      renderLyrics();
      expect(document.body.getAttribute("data-has-lyrics")).toBe("true");
      expect(dom.lyricsTextContainer.style.display).toBe("flex");
      expect(dom.homeEqualizer.style.display).toBe("none");
    });

    it("fills prev/current/next with the right lines and pads the edges with &nbsp;", () => {
      store.lyrics_lines = ["A", "B", "C"];
      store.lyrics_index = 0;
      renderLyrics();
      expect(dom.lyricsPrev.innerHTML).toBe("&nbsp;");
      expect(dom.lyricsCurrent.innerHTML).toBe("A");
      expect(dom.lyricsNext.innerHTML).toBe("B");

      store.lyrics_index = 2;
      renderLyrics();
      expect(dom.lyricsPrev.innerHTML).toBe("B");
      expect(dom.lyricsCurrent.innerHTML).toBe("C");
      expect(dom.lyricsNext.innerHTML).toBe("&nbsp;");
    });

    it("adds a pop animation class and removes it after 300ms", () => {
      store.lyrics_lines = ["A"];
      renderLyrics();
      expect(dom.lyricsCurrent.className).toBe("lyrics-line current lyric-pop");
      vi.advanceTimersByTime(300);
      expect(dom.lyricsCurrent.className).toBe("lyrics-line current");
    });

    it("resets the pop timeout on rapid successive renders", () => {
      store.lyrics_lines = ["A", "B"];
      renderLyrics();
      vi.advanceTimersByTime(200);
      store.lyrics_index = 1;
      renderLyrics();
      vi.advanceTimersByTime(200);
      // First timeout was cleared; still within the pop window.
      expect(dom.lyricsCurrent.className).toBe("lyrics-line current lyric-pop");
      vi.advanceTimersByTime(100);
      expect(dom.lyricsCurrent.className).toBe("lyrics-line current");
    });
  });

  describe("updateOffsetDisplay", () => {
    it("is a no-op when #sync-val does not exist", () => {
      document.body.innerHTML = "";
      expect(() => updateOffsetDisplay()).not.toThrow();
    });

    it("shows a '+' sign and one decimal for a positive offset", () => {
      document.body.innerHTML = `<span id="sync-val"></span>`;
      store.lyrics_offset = 1.5;
      updateOffsetDisplay();
      expect(document.getElementById("sync-val").textContent).toBe("+1.5s");
    });

    it("shows no extra sign for a negative offset", () => {
      document.body.innerHTML = `<span id="sync-val"></span>`;
      store.lyrics_offset = -2;
      updateOffsetDisplay();
      expect(document.getElementById("sync-val").textContent).toBe("-2.0s");
    });

    it("defaults to 0.0s when there is no offset set", () => {
      document.body.innerHTML = `<span id="sync-val"></span>`;
      store.lyrics_offset = 0;
      updateOffsetDisplay();
      expect(document.getElementById("sync-val").textContent).toBe("+0.0s");
    });
  });

  describe("initLyricsBusSubscriptions", () => {
    it("wires lyrics:changed to renderLyrics", () => {
      initLyricsBusSubscriptions();
      store.lyrics_lines = ["hi"];
      emit("lyrics:changed");
      expect(dom.lyricsCurrent.innerHTML).toBe("hi");
    });

    it("wires lyrics:offset-display to updateOffsetDisplay", () => {
      document.body.innerHTML = `<span id="sync-val"></span>`;
      initLyricsBusSubscriptions();
      store.lyrics_offset = 0.5;
      emit("lyrics:offset-display");
      expect(document.getElementById("sync-val").textContent).toBe("+0.5s");
    });
  });
});
