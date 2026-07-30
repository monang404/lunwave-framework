import { describe, it, expect, vi, beforeEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";
import { emit, on } from "../../../web/static/shared/js/bus.js";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  getOrInitAudio: vi.fn(),
  syncBrowserAudio: vi.fn(),
  updateMediaSession: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ renderHeader: vi.fn() }));

import {
  applyFullState,
  renderFullState,
  initFullStateBusSubscriptions,
} from "../../../web/static/shared/js/render/full-state.js";
import {
  getOrInitAudio,
  syncBrowserAudio,
  updateMediaSession,
} from "../../../web/static/shared/js/audio/playback-sync.js";
import { renderHeader } from "../../../web/static/shared/js/ws.js";

function selectWithOptions(values) {
  const sel = document.createElement("select");
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = String(v);
    sel.appendChild(opt);
  }
  return sel;
}

describe("render/full-state.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.title = "";
    Object.assign(dom, {
      ssSpeedSelect: selectWithOptions(["0.75", "1.00", "1.25"]),
    });
    Object.assign(store, {
      userRole: "admin",
      audio_output: "server",
      playback_speed: null,
      current_track: null,
      position: 0,
    });
  });

  describe("applyFullState", () => {
    it("merges the incoming data into the store", () => {
      applyFullState({ status: "PLAYING", position: 42 });
      expect(store.status).toBe("PLAYING");
      expect(store.position).toBe(42);
    });

    it("emits player:position with the new position", () => {
      const handler = vi.fn();
      on("player:position", handler);
      applyFullState({ position: 7 });
      expect(handler).toHaveBeenCalledWith(7);
    });

    it("syncs the browser audio playback rate when output is browser", () => {
      const fakeAudio = { playbackRate: 1 };
      getOrInitAudio.mockReturnValue(fakeAudio);
      applyFullState({ audio_output: "browser", playback_speed: 1.5 });
      expect(fakeAudio.playbackRate).toBe(1.5);
    });

    it("does not touch audio playbackRate when output is not browser", () => {
      applyFullState({ audio_output: "server", playback_speed: 1.5 });
      expect(getOrInitAudio).not.toHaveBeenCalled();
    });

    it("syncs the speed dropdown to the server value", () => {
      applyFullState({ playback_speed: 1.25 });
      expect(dom.ssSpeedSelect.value).toBe("1.25");
    });

    it("does not touch the dropdown when there is no dom.ssSpeedSelect", () => {
      dom.ssSpeedSelect = null;
      expect(() => applyFullState({ playback_speed: 1.25 })).not.toThrow();
    });

    it("triggers a full re-render", () => {
      applyFullState({ current_track: { title: "T", artist: "A" } });
      expect(renderHeader).toHaveBeenCalled();
      expect(document.title).toBe("T - A");
    });

    it("syncs browser audio for non-portal roles", () => {
      applyFullState({ userRole: "admin" });
      expect(syncBrowserAudio).toHaveBeenCalled();
    });

    it("does not sync browser audio for the 'portal' role", () => {
      applyFullState({ userRole: "portal" });
      expect(syncBrowserAudio).not.toHaveBeenCalled();
    });
  });

  describe("renderFullState", () => {
    it("calls renderHeader and updateMediaSession", () => {
      renderFullState();
      expect(renderHeader).toHaveBeenCalled();
      expect(updateMediaSession).toHaveBeenCalled();
    });

    it("emits all the expected render-refresh events", () => {
      const events = [
        "now-playing:changed",
        "player:progress",
        "player:bar-changed",
        "radio:changed",
        "queue:changed",
        "lyrics:changed",
        "settings:sheet-changed",
        "search:playing-state",
        "discover:playing-state",
      ];
      const handlers = events.map((e) => {
        const h = vi.fn();
        on(e, h);
        return h;
      });
      renderFullState();
      handlers.forEach((h) => expect(h).toHaveBeenCalled());
    });

    it("sets the document title from the current track", () => {
      store.current_track = { title: "Kisah Cintaku", artist: "Sheila On 7" };
      renderFullState();
      expect(document.title).toBe("Kisah Cintaku - Sheila On 7");
    });

    it("falls back to the app title when there is no current track", () => {
      store.current_track = null;
      renderFullState();
      expect(document.title).toBe("LunaWave — Midnight Audio Experience");
    });
  });

  describe("initFullStateBusSubscriptions", () => {
    it("wires state:full to applyFullState", () => {
      initFullStateBusSubscriptions();
      emit("state:full", { status: "PAUSED" });
      expect(store.status).toBe("PAUSED");
    });

    it("wires state:full-render to renderFullState", () => {
      initFullStateBusSubscriptions();
      emit("state:full-render");
      expect(renderHeader).toHaveBeenCalled();
    });
  });
});
