import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getCoverArt,
  getCoverArtFast,
  extractDominantColor,
  cleanTrackTitle,
} from "../../../web/static/shared/js/utils/cover-art.js";

describe("utils/cover-art.js", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  describe("cleanTrackTitle", () => {
    it("returns empty string for falsy input", () => {
      expect(cleanTrackTitle("")).toBe("");
      expect(cleanTrackTitle(null)).toBe("");
      expect(cleanTrackTitle(undefined)).toBe("");
    });

    it("strips '(Official Video)'-style bracketed noise", () => {
      expect(cleanTrackTitle("Song Title (Official Music Video)")).toBe("Song Title");
    });

    it("strips '[Official Audio]' bracket variants", () => {
      expect(cleanTrackTitle("Song Title [Official Audio]")).toBe("Song Title");
    });

    it("strips hashtags", () => {
      expect(cleanTrackTitle("Song Title #trending #music")).toBe("Song Title");
    });

    it("collapses multiple spaces into one and trims", () => {
      expect(cleanTrackTitle("Song    Title   ")).toBe("Song Title");
    });

    it("strips a trailing dangling dash left after cleanup", () => {
      expect(cleanTrackTitle("Song Title -")).toBe("Song Title");
    });
  });

  describe("globalThis.safeStorage", () => {
    it("get/set/remove work like a normal wrapper around localStorage", () => {
      globalThis.safeStorage.set("lunawave_foo", "bar");
      expect(globalThis.safeStorage.get("lunawave_foo")).toBe("bar");
      globalThis.safeStorage.remove("lunawave_foo");
      expect(globalThis.safeStorage.get("lunawave_foo")).toBeNull();
    });

    it("migrates a legacy ytgui_ key to the lunawave_ namespace on read", () => {
      localStorage.setItem("ytgui_foo", "legacy-value");
      const result = globalThis.safeStorage.get("lunawave_foo");
      expect(result).toBe("legacy-value");
      // migrated: new key now holds the value, legacy key removed
      expect(localStorage.getItem("lunawave_foo")).toBe("legacy-value");
      expect(localStorage.getItem("ytgui_foo")).toBeNull();
    });

    it("remove() also clears the legacy ytgui_ counterpart", () => {
      localStorage.setItem("lunawave_bar", "v");
      localStorage.setItem("ytgui_bar", "v");
      globalThis.safeStorage.remove("lunawave_bar");
      expect(localStorage.getItem("lunawave_bar")).toBeNull();
      expect(localStorage.getItem("ytgui_bar")).toBeNull();
    });

    it("get() swallows localStorage errors and returns null", () => {
      const spy = vi
        .spyOn(Storage.prototype, "getItem")
        .mockImplementation(() => {
          throw new Error("quota");
        });
      expect(globalThis.safeStorage.get("anything")).toBeNull();
      spy.mockRestore();
    });
  });

  describe("getCoverArt", () => {
    it("returns empty string when track is falsy", async () => {
      expect(await getCoverArt(null)).toBe("");
    });

    it("returns track.thumbnail (or empty string) when track has no video_id", async () => {
      expect(await getCoverArt({ thumbnail: "thumb.jpg" })).toBe("thumb.jpg");
      expect(await getCoverArt({})).toBe("");
    });

    it("returns cached URL when a fresh (non-expired) cache entry exists", async () => {
      const track = { video_id: "abc123", title: "T", artist: "A" };
      localStorage.setItem(
        "cover_abc123",
        JSON.stringify({ url: "https://cached.example/art.jpg", ts: Date.now() })
      );
      const fetchSpy = vi.fn();
      vi.stubGlobal("fetch", fetchSpy);

      const result = await getCoverArt(track);
      expect(result).toBe("https://cached.example/art.jpg");
      expect(fetchSpy).not.toHaveBeenCalled();
    });

    it("ignores an expired (>7 day) cache entry and re-fetches", async () => {
      const track = { video_id: "abc123", title: "T", artist: "A" };
      const eightDaysAgo = Date.now() - 8 * 24 * 60 * 60 * 1000;
      localStorage.setItem(
        "cover_abc123",
        JSON.stringify({ url: "https://stale.example/art.jpg", ts: eightDaysAgo })
      );
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: async () => ({ results: [] }),
        })
      );

      const result = await getCoverArt(track);
      expect(result).toBe("https://i.ytimg.com/vi/abc123/hqdefault.jpg");
    });

    it("returns raw legacy cache string (no TTL wrapper) as-is", async () => {
      const track = { video_id: "legacy1", title: "T", artist: "A" };
      localStorage.setItem("cover_legacy1", "https://legacy.example/plain.jpg");
      const result = await getCoverArt(track);
      expect(result).toBe("https://legacy.example/plain.jpg");
    });

    it("falls back to thumbnail/YT default when track has no title/artist", async () => {
      const track = { video_id: "xyz", thumbnail: "custom-thumb.jpg" };
      expect(await getCoverArt(track)).toBe("custom-thumb.jpg");

      const trackNoThumb = { video_id: "xyz2" };
      expect(await getCoverArt(trackNoThumb)).toBe(
        "https://i.ytimg.com/vi/xyz2/hqdefault.jpg"
      );
    });

    it("fetches iTunes artwork, upgrades to 600x600, and caches it", async () => {
      const track = { video_id: "hit1", title: "Some Song (Official Video)", artist: "Artist" };
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: async () => ({
            results: [{ artworkUrl100: "https://itunes.example/100x100bb.jpg" }],
          }),
        })
      );

      const result = await getCoverArt(track);
      expect(result).toBe("https://itunes.example/600x600bb.jpg");
      const cached = JSON.parse(localStorage.getItem("cover_hit1"));
      expect(cached.url).toBe("https://itunes.example/600x600bb.jpg");
    });

    it("falls back to YT thumbnail and caches it when iTunes returns no results", async () => {
      const track = { video_id: "miss1", title: "Song", artist: "Artist" };
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({ ok: true, json: async () => ({ results: [] }) })
      );

      const result = await getCoverArt(track);
      expect(result).toBe("https://i.ytimg.com/vi/miss1/hqdefault.jpg");
    });

    it("falls back to YT thumbnail when fetch throws / response not ok", async () => {
      const track = { video_id: "err1", title: "Song", artist: "Artist" };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

      const result = await getCoverArt(track);
      expect(result).toBe("https://i.ytimg.com/vi/err1/hqdefault.jpg");
    });
  });

  describe("getCoverArtFast", () => {
    it("does nothing when track is falsy", () => {
      const img = document.createElement("img");
      expect(() => getCoverArtFast(img, null)).not.toThrow();
      expect(img.src).toBe("");
    });

    it("sets cached hi-res URL immediately without touching YT fallback first", () => {
      const img = document.createElement("img");
      const track = { video_id: "cached1", title: "T", artist: "A" };
      localStorage.setItem(
        "cover_cached1",
        JSON.stringify({ url: "https://cached.example/hi.jpg", ts: Date.now() })
      );
      getCoverArtFast(img, track);
      expect(img.src).toBe("https://cached.example/hi.jpg");
    });

    it("sets the YT fallback thumbnail immediately when no cache exists", () => {
      const img = document.createElement("img");
      const track = { video_id: "nocache1", title: "T", artist: "A" };
      vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {}))); // never resolves
      getCoverArtFast(img, track);
      expect(img.src).toBe("https://i.ytimg.com/vi/nocache1/hqdefault.jpg");
    });

    it("sets a legacy plain-string cached URL immediately (pre-JSON cache format)", () => {
      const img = document.createElement("img");
      const track = { video_id: "legacyplain1", title: "T", artist: "A" };
      localStorage.setItem("cover_legacyplain1", "https://legacy.example/plain.jpg");
      vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
      getCoverArtFast(img, track);
      expect(img.src).toBe("https://legacy.example/plain.jpg");
    });

    it("upgrades img.src once the background getCoverArt resolves, if still connected", async () => {
      document.body.innerHTML = "";
      const img = document.createElement("img");
      document.body.appendChild(img); // isConnected = true
      const track = { video_id: "upgrade1", title: "Song", artist: "Artist" };
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: async () => ({
            results: [{ artworkUrl100: "https://itunes.example/100x100bb.jpg" }],
          }),
        })
      );

      getCoverArtFast(img, track);
      // Microtask queue: wait for the background promise to settle.
      await new Promise((resolve) => setTimeout(resolve, 0));
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(img.src).toBe("https://itunes.example/600x600bb.jpg");
    });
  });

  describe("extractDominantColor", () => {
    it("waits for the image 'load' event when the image isn't complete yet", () => {
      const img = document.createElement("img");
      Object.defineProperty(img, "complete", { value: false, configurable: true });
      const callback = vi.fn();
      extractDominantColor(img, callback);
      expect(callback).not.toHaveBeenCalled();
    });

    it("invokes the callback (with a fallback since jsdom has no real 2D canvas context)", () => {
      const img = document.createElement("img");
      Object.defineProperty(img, "complete", { value: true, configurable: true });
      Object.defineProperty(img, "naturalWidth", { value: 100, configurable: true });
      const callback = vi.fn();
      expect(() => extractDominantColor(img, callback)).not.toThrow();
      expect(callback).toHaveBeenCalledTimes(1);
    });

    function stubCanvasContext(pixelBytes) {
      vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
        drawImage: vi.fn(),
        getImageData: vi.fn(() => ({ data: pixelBytes })),
      });
    }

    it("picks the most saturated pixel as the dominant color when one stands out", () => {
      const img = document.createElement("img");
      Object.defineProperty(img, "complete", { value: true, configurable: true });
      Object.defineProperty(img, "naturalWidth", { value: 100, configurable: true });

      // 2 sampled pixels (loop steps by 16 bytes/pixel): a dull gray pixel
      // (low saturation) and a vivid red pixel (high saturation) — the red
      // one should win regardless of scan order.
      const data = new Uint8ClampedArray(32);
      data.set([120, 120, 120, 255], 0); // gray, s≈0
      data.set([200, 20, 20, 255], 16);  // red, s high
      stubCanvasContext(data);

      const callback = vi.fn();
      extractDominantColor(img, callback);
      expect(callback).toHaveBeenCalledWith({ r: 200, g: 20, b: 20 });
    });

    it("skips pixels that are too dark or too bright, falling back to an averaged color if none qualify", () => {
      const img = document.createElement("img");
      Object.defineProperty(img, "complete", { value: true, configurable: true });
      Object.defineProperty(img, "naturalWidth", { value: 100, configurable: true });

      // Both sampled pixels are pure white (l=255 > 240) -> skipped by the
      // brightness guard, so the function falls back to averaging all
      // sampled pixels instead.
      const data = new Uint8ClampedArray(32);
      data.set([255, 255, 255, 255], 0);
      data.set([255, 255, 255, 255], 16);
      stubCanvasContext(data);

      const callback = vi.fn();
      extractDominantColor(img, callback);
      expect(callback).toHaveBeenCalledWith({ r: 255, g: 255, b: 255 });
    });

    it("falls back to the CSS variable color when canvas access throws", () => {
      const img = document.createElement("img");
      Object.defineProperty(img, "complete", { value: true, configurable: true });
      Object.defineProperty(img, "naturalWidth", { value: 100, configurable: true });
      vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => {
        throw new Error("canvas unavailable");
      });
      const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

      const callback = vi.fn();
      extractDominantColor(img, callback);

      expect(warnSpy).toHaveBeenCalled();
      expect(callback).toHaveBeenCalledWith("var(--bg-elevated)");
    });

    it("is safe to call without a callback when extraction fails", () => {
      const img = document.createElement("img");
      Object.defineProperty(img, "complete", { value: true, configurable: true });
      Object.defineProperty(img, "naturalWidth", { value: 100, configurable: true });
      vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => {
        throw new Error("canvas unavailable");
      });
      vi.spyOn(console, "warn").mockImplementation(() => {});
      expect(() => extractDominantColor(img, undefined)).not.toThrow();
    });
  });

  describe("loadLazyCovers", () => {
    class FakeIntersectionObserver {
      constructor(cb) {
        FakeIntersectionObserver.instances.push(this);
        this.cb = cb;
        this.observe = vi.fn();
        this.unobserve = vi.fn();
      }
    }
    FakeIntersectionObserver.instances = [];

    // cover-art.js memoizes its IntersectionObserver in a module-scoped
    // `_lazyCoverObserver` variable (created once, reused on every
    // loadLazyCovers() call). Because loadLazyCovers is statically imported
    // once at the top of this file, that memoized observer would survive
    // across tests even though we swap out the FakeIntersectionObserver
    // global and reset its `.instances` list each time -- so after the
    // first test, no *new* instance is ever pushed and
    // FakeIntersectionObserver.instances[0] stays undefined. We use
    // vi.resetModules() + a fresh dynamic import per test to get a clean
    // module instance (and therefore a clean `_lazyCoverObserver`) every
    // time.
    let freshLoadLazyCovers;

    beforeEach(async () => {
      FakeIntersectionObserver.instances = [];
      vi.stubGlobal("IntersectionObserver", FakeIntersectionObserver);
      document.body.innerHTML = "";
      vi.resetModules();
      const mod = await import("../../../web/static/shared/js/utils/cover-art.js");
      freshLoadLazyCovers = mod.loadLazyCovers;
    });

    it("observes lazy-cover images not yet marked as observed", () => {
      const img = document.createElement("img");
      img.className = "lazy-cover";
      document.body.appendChild(img);

      freshLoadLazyCovers();

      expect(img.classList.contains("observed")).toBe(true);
      const observer = FakeIntersectionObserver.instances[0];
      expect(observer.observe).toHaveBeenCalledWith(img);
    });

    it("does not re-observe images already marked observed", () => {
      const img = document.createElement("img");
      img.className = "lazy-cover observed";
      document.body.appendChild(img);

      freshLoadLazyCovers();

      const observer = FakeIntersectionObserver.instances[0];
      expect(observer.observe).not.toHaveBeenCalled();
    });

    it("loads the cover and marks the image loaded when it intersects", () => {
      const img = document.createElement("img");
      img.className = "lazy-cover";
      img.setAttribute("data-vid", "v1");
      img.setAttribute("data-title", "T");
      img.setAttribute("data-artist", "A");
      img.setAttribute("data-thumb", "thumb.jpg");
      document.body.appendChild(img);

      freshLoadLazyCovers();
      const observer = FakeIntersectionObserver.instances[0];

      observer.cb([{ isIntersecting: true, target: img }], observer);

      expect(img.classList.contains("loaded")).toBe(true);
      expect(observer.unobserve).toHaveBeenCalledWith(img);
      // getCoverArtFast should have set the immediate thumbnail
      expect(img.src).toContain("thumb.jpg");
    });

    it("ignores entries with no data-vid attribute", () => {
      const img = document.createElement("img");
      img.className = "lazy-cover";
      document.body.appendChild(img);

      freshLoadLazyCovers();
      const observer = FakeIntersectionObserver.instances[0];

      expect(() => observer.cb([{ isIntersecting: true, target: img }], observer)).not.toThrow();
      expect(img.src).toBe("");
    });
  });
});
