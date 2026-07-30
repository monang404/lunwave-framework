import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";
import { emit, on } from "../../../web/static/shared/js/bus.js";

vi.mock("../../../web/static/shared/js/render/navigation.js", () => ({
  switchTab: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/render/toast.js", () => ({
  showLogToast: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import {
  getDecade,
  buildDecadeChips,
  renderDiscoverPersonalization,
  initDiscoverFilterEvents,
  handleArtistDetail,
  initDiscoverPersonalizeBusSubscriptions,
} from "../../../web/static/shared/js/render/discover-personalize.js";
import { switchTab } from "../../../web/static/shared/js/render/navigation.js";
import { showLogToast } from "../../../web/static/shared/js/render/toast.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

function el(tag = "div") {
  return document.createElement(tag);
}
function elStyle(tag = "div") {
  return Object.assign(el(tag), { style: {} });
}

describe("render/discover-personalize.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.loadLazyCovers = vi.fn();
    globalThis.pendingArtistDetail = null;
    document.body.innerHTML = `
      <button id="decade-dropdown-btn"></button>
      <div id="decade-dropdown-container"></div>
    `;

    Object.assign(dom, {
      tasteBar: el(),
      tasteLegend: el(),
      decadeChips: el(),
      rowForYou: el(),
      rowGenreAffinity: el(),
      rowUnheard: el(),
      rowGenreAffinityLabel: elStyle(),
      rowGenreAffinitySub: el(),
      kategoriToggle: (() => {
        const wrap = el();
        wrap.innerHTML = `
          <button data-kategori="all" class="active">Semua</button>
          <button data-kategori="band">Band</button>
        `;
        return wrap;
      })(),
      adsCloseBtn: el("button"),
      adsPlayAll: el("button"),
      adsName: el(),
      adsTags: el(),
      adsCoverImg: Object.assign(el("img"), { src: "" }),
      adsTrackList: el(),
      artistDetailSheet: el(),
      mainOverlay: el(),
    });

    Object.assign(store, {
      discover_taste_spectrum: [],
      discover_for_you: [],
      discover_genre_affinity_artists: [],
      discover_genre_affinity_genre: "",
      discover_unheard: [],
      userRole: "admin",
    });

    // _discActiveKategori/_discActiveDecade are module-scope singletons with
    // no reset hook, so a previous test's filter selection ("band", "1980",
    // etc.) would otherwise silently leak into later tests and filter out
    // artists that don't happen to match. Force both back to "all" here.
    buildDecadeChips([]);
    initDiscoverFilterEvents();
    dom.kategoriToggle.querySelector('[data-kategori="all"]').click();
    dom.decadeChips.querySelector('[data-value="all"]').click();
    vi.clearAllMocks();
  });

  afterEach(() => {
    delete globalThis.loadLazyCovers;
    delete globalThis.pendingArtistDetail;
  });

  describe("getDecade", () => {
    it("floors a year to its decade", () => {
      expect(getDecade("2003")).toBe(2000);
      expect(getDecade("1998")).toBe(1990);
    });
    it("returns null for falsy or unparsable years", () => {
      expect(getDecade(null)).toBeNull();
      expect(getDecade("")).toBeNull();
      expect(getDecade("abc")).toBeNull();
    });
  });

  describe("buildDecadeChips", () => {
    it("renders 'Semua Era' plus the sorted set of decades found in the artist list", () => {
      buildDecadeChips([{ tahun_aktif: "2005" }, { tahun_aktif: "1998" }, { tahun_aktif: "2001" }]);
      const buttons = dom.decadeChips.querySelectorAll("button");
      const values = Array.from(buttons).map((b) => b.dataset.value);
      expect(values).toEqual(["all", "1990", "2000"]);
    });

    it("is a no-op when dom.decadeChips is missing", () => {
      dom.decadeChips = null;
      expect(() => buildDecadeChips([])).not.toThrow();
    });
  });

  describe("renderDiscoverPersonalization / taste spectrum", () => {
    it("shows a fallback message when there is no taste spectrum yet", () => {
      renderDiscoverPersonalization();
      expect(dom.tasteLegend.innerHTML).toContain("Dengarkan beberapa lagu dulu");
    });

    it("renders taste segments and legend items proportional to the spectrum", () => {
      store.discover_taste_spectrum = [{ genre: "Pop", pct: 60 }, { genre: "Rock", pct: 40 }];
      renderDiscoverPersonalization();
      expect(dom.tasteBar.querySelectorAll(".taste-seg").length).toBe(2);
      expect(dom.tasteLegend.innerHTML).toContain("60%");
      expect(dom.tasteLegend.innerHTML).toContain("Rock");
    });

    it("is a no-op for the taste spectrum when tasteBar/tasteLegend are missing", () => {
      dom.tasteBar = null;
      dom.tasteLegend = null;
      expect(() => renderDiscoverPersonalization()).not.toThrow();
    });
  });

  describe("renderDiscoverPersonalization / genre-affinity row", () => {
    it("hides the row when there is no affinity genre", () => {
      store.discover_genre_affinity_genre = "";
      renderDiscoverPersonalization();
      expect(dom.rowGenreAffinityLabel.style.display).toBe("none");
      expect(dom.rowGenreAffinity.style.display).toBe("none");
      expect(dom.rowGenreAffinitySub.textContent).toBe("Karena Kamu Suka");
    });

    it("shows the row and genre-specific label when an affinity genre exists", () => {
      store.discover_genre_affinity_genre = "Jazz";
      renderDiscoverPersonalization();
      expect(dom.rowGenreAffinityLabel.style.display).toBe("");
      expect(dom.rowGenreAffinity.style.display).toBe("");
      expect(dom.rowGenreAffinitySub.textContent).toBe("Karena Kamu Suka Jazz");
    });
  });

  describe("renderDiscoverPersonalization / card rows", () => {
    it("shows an empty message per row when there are no artists", () => {
      renderDiscoverPersonalization();
      expect(dom.rowForYou.innerHTML).toContain("Belum ada rekomendasi");
      expect(dom.rowGenreAffinity.innerHTML).toContain("Tidak ada artis");
      expect(dom.rowUnheard.innerHTML).toContain("Tidak ada artis");
    });

    it("renders artist cards with match-percent badges for 'for you'", () => {
      store.discover_for_you = [{ nama: "Sheila On 7", match_pct: 92, kategori: "band" }];
      renderDiscoverPersonalization();
      const card = dom.rowForYou.querySelector(".artist-card");
      expect(card.dataset.artist).toBe("Sheila On 7");
      expect(dom.rowForYou.innerHTML).toContain("92%");
    });

    it("renders 'new' badges and the undiscovered class for the unheard row", () => {
      store.discover_unheard = [{ nama: "New Artist" }];
      renderDiscoverPersonalization();
      expect(dom.rowUnheard.innerHTML).toContain("Baru");
      expect(dom.rowUnheard.querySelector(".artist-card").classList.contains("undiscovered")).toBe(true);
    });

    it("shows a decade badge and cover fallback icon when no cover image exists", () => {
      store.discover_for_you = [{ nama: "A", tahun_aktif: "1999" }];
      renderDiscoverPersonalization();
      expect(dom.rowForYou.innerHTML).toContain("1990an");
      expect(dom.rowForYou.innerHTML).toContain("art-fallback");
    });

    it("clicking a card opens the artist detail sheet and requests details via wsSend", () => {
      store.discover_for_you = [{ nama: "Dewa 19" }];
      renderDiscoverPersonalization();
      dom.rowForYou.querySelector(".artist-card").click();

      expect(dom.artistDetailSheet.classList.contains("open")).toBe(true);
      expect(dom.mainOverlay.classList.contains("open")).toBe(true);
      expect(dom.adsName.textContent).toBe("Dewa 19");
      expect(wsSend).toHaveBeenCalledWith("get_artist_detail", { artist: "Dewa 19" });
    });

    it("triggers lazy cover loading after rendering a non-empty row", () => {
      store.discover_for_you = [{ nama: "A" }];
      renderDiscoverPersonalization();
      expect(globalThis.loadLazyCovers).toHaveBeenCalled();
    });
  });

  describe("initDiscoverFilterEvents / kategori toggle", () => {
    it("activates the clicked kategori button and re-filters the rows", () => {
      store.discover_for_you = [
        { nama: "Band A", kategori: "band" },
        { nama: "Solo B", kategori: "solo" },
      ];
      initDiscoverFilterEvents();
      const bandBtn = dom.kategoriToggle.querySelector('[data-kategori="band"]');
      bandBtn.click();

      expect(bandBtn.classList.contains("active")).toBe(true);
      expect(dom.rowForYou.innerHTML).toContain("Band A");
      expect(dom.rowForYou.innerHTML).not.toContain("Solo B");
    });

    it("ignores clicks that don't hit a button", () => {
      initDiscoverFilterEvents();
      expect(() => dom.kategoriToggle.click()).not.toThrow();
    });
  });

  describe("initDiscoverFilterEvents / decade dropdown", () => {
    it("toggles the dropdown open and stops propagation", () => {
      const btn = document.getElementById("decade-dropdown-btn");
      const container = document.getElementById("decade-dropdown-container");
      const event = new MouseEvent("click", { bubbles: true, cancelable: true });
      const stopSpy = vi.spyOn(event, "stopPropagation");
      btn.dispatchEvent(event);

      expect(stopSpy).toHaveBeenCalled();
      expect(container.classList.contains("open")).toBe(true);
    });

    it("closes the dropdown on an outside document click", () => {
      const container = document.getElementById("decade-dropdown-container");
      container.classList.add("open");
      document.body.click();
      expect(container.classList.contains("open")).toBe(false);
    });
  });

  describe("initDiscoverFilterEvents / decade chips", () => {
    it("selecting a decade chip activates it, updates the dropdown label, and re-filters", () => {
      store.discover_for_you = [{ nama: "Old", tahun_aktif: "1985" }, { nama: "New", tahun_aktif: "2015" }];
      buildDecadeChips(store.discover_for_you);

      const chip = dom.decadeChips.querySelector('[data-value="1980"]');
      chip.click();

      expect(chip.classList.contains("active")).toBe(true);
      expect(document.getElementById("decade-dropdown-btn").innerHTML).toContain("1980an");
      expect(dom.rowForYou.innerHTML).toContain("Old");
      expect(dom.rowForYou.innerHTML).not.toContain("New");
    });

    it("ignores clicks that don't hit a dropdown item", () => {
      buildDecadeChips([]);
      initDiscoverFilterEvents();
      expect(() => dom.decadeChips.click()).not.toThrow();
    });
  });

  describe("artist detail sheet close/play-all", () => {
    it("adsCloseBtn closes the sheet and emits overlay:main-close", () => {
      const handler = vi.fn();
      on("overlay:main-close", handler);
      initDiscoverFilterEvents();
      dom.artistDetailSheet.classList.add("open");
      dom.adsCloseBtn.click();

      expect(dom.artistDetailSheet.classList.contains("open")).toBe(false);
      expect(handler).toHaveBeenCalled();
      expect(globalThis.pendingArtistDetail).toBeNull();
    });

    it("adsPlayAll enqueues the artist's songs, toasts, closes the sheet, and switches to home for admins", () => {
      initDiscoverFilterEvents();
      globalThis.pendingArtistDetail = "Peterpan";
      dom.adsPlayAll.click();

      expect(wsSend).toHaveBeenCalledWith("enqueue_artist_songs", { artist: "Peterpan" });
      expect(showLogToast).toHaveBeenCalledWith(expect.stringContaining("Peterpan"));
      expect(switchTab).toHaveBeenCalledWith("home");
    });

    it("adsPlayAll shows a toast instead for non-admins and does not enqueue", () => {
      store.userRole = "client";
      initDiscoverFilterEvents();
      globalThis.pendingArtistDetail = "Peterpan";
      dom.adsPlayAll.click();

      expect(wsSend).not.toHaveBeenCalled();
      expect(showLogToast).toHaveBeenCalledWith("Hanya admin yang bisa memutar musik");
    });

    it("adsPlayAll does nothing when there is no pending artist", () => {
      initDiscoverFilterEvents();
      globalThis.pendingArtistDetail = null;
      dom.adsPlayAll.click();
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("handleArtistDetail", () => {
    it("does nothing when the sheet is not open", () => {
      handleArtistDetail({ nama: "X" });
      expect(dom.adsName.textContent).toBe("");
    });

    it("shows a not-found message when data is empty", () => {
      dom.artistDetailSheet.classList.add("open");
      handleArtistDetail(null);
      expect(dom.adsTrackList.innerHTML).toContain("Artis tidak ditemukan");
    });

    it("populates name, cover, tags and track list from the response", () => {
      dom.artistDetailSheet.classList.add("open");
      handleArtistDetail({
        nama: "Sheila On 7",
        cover: "cover.jpg",
        kategori: "band",
        tahun_aktif: "1996",
        genres: ["Pop", "Rock"],
        songs: [{ title: "Sephia", duration: 245 }],
      });
      expect(dom.adsName.textContent).toBe("Sheila On 7");
      expect(dom.adsCoverImg.src).toContain("cover.jpg");
      expect(dom.adsTags.innerHTML).toContain("Band");
      expect(dom.adsTags.innerHTML).toContain("Pop");
      expect(dom.adsTrackList.innerHTML).toContain("Sephia");
      expect(dom.adsTrackList.innerHTML).toContain("04:05");
    });

    it("shows an empty-tracks message when the artist has no songs", () => {
      dom.artistDetailSheet.classList.add("open");
      handleArtistDetail({ nama: "X", songs: [] });
      expect(dom.adsTrackList.innerHTML).toContain("Belum ada lagu");
    });
  });

  describe("initDiscoverPersonalizeBusSubscriptions", () => {
    it("wires discover:personalization-changed to renderDiscoverPersonalization", () => {
      initDiscoverPersonalizeBusSubscriptions();
      store.discover_for_you = [{ nama: "Wired" }];
      emit("discover:personalization-changed");
      expect(dom.rowForYou.innerHTML).toContain("Wired");
    });

    it("wires discover:artist-detail to handleArtistDetail", () => {
      dom.artistDetailSheet.classList.add("open");
      initDiscoverPersonalizeBusSubscriptions();
      emit("discover:artist-detail", { nama: "Wired Artist", songs: [] });
      expect(dom.adsName.textContent).toBe("Wired Artist");
    });
  });
});
