import { describe, it, expect, vi, beforeEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  unlockBrowserAudio: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/bus.js", () => ({ emit: vi.fn() }));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import { initActionModalEvents } from "../../../web/static/shared/js/events/action-modal-events.js";
import { unlockBrowserAudio } from "../../../web/static/shared/js/audio/playback-sync.js";
import { emit } from "../../../web/static/shared/js/bus.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

describe("events/action-modal-events.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.pendingTrack = null;

    Object.assign(dom, {
      actionPlayNow: document.createElement("button"),
      actionEnqueue: document.createElement("button"),
      actionCancel: document.createElement("button"),
      actionDelete: document.createElement("button"),
    });

    Object.assign(store, {
      audio_output: "browser",
      userRole: "admin",
    });

    initActionModalEvents();
  });

  describe("actionPlayNow", () => {
    it("unlocks browser audio and plays the pending track when output is browser", () => {
      globalThis.pendingTrack = { video_id: "v1" };
      dom.actionPlayNow.click();

      expect(unlockBrowserAudio).toHaveBeenCalledWith(true);
      expect(wsSend).toHaveBeenCalledWith("play_track", { video_id: "v1" });
      expect(emit).toHaveBeenCalledWith("search:action-modal-close");
    });

    it("does not unlock audio when output is not browser", () => {
      store.audio_output = "server";
      globalThis.pendingTrack = { video_id: "v1" };
      dom.actionPlayNow.click();

      expect(unlockBrowserAudio).not.toHaveBeenCalled();
      expect(wsSend).toHaveBeenCalledWith("play_track", { video_id: "v1" });
    });

    it("still closes the modal when there is no pending track", () => {
      globalThis.pendingTrack = null;
      dom.actionPlayNow.click();

      expect(wsSend).not.toHaveBeenCalled();
      expect(emit).toHaveBeenCalledWith("search:action-modal-close");
    });
  });

  describe("actionEnqueue", () => {
    it("queues the pending track and closes the modal", () => {
      globalThis.pendingTrack = { video_id: "v2" };
      dom.actionEnqueue.click();

      expect(wsSend).toHaveBeenCalledWith("queue_add", { video_id: "v2" });
      expect(emit).toHaveBeenCalledWith("search:action-modal-close");
    });

    it("does not send when there is no pending track", () => {
      globalThis.pendingTrack = null;
      dom.actionEnqueue.click();

      expect(wsSend).not.toHaveBeenCalled();
      expect(emit).toHaveBeenCalledWith("search:action-modal-close");
    });
  });

  describe("actionCancel", () => {
    it("closes the modal without sending anything", () => {
      dom.actionCancel.click();

      expect(wsSend).not.toHaveBeenCalled();
      expect(emit).toHaveBeenCalledWith("search:action-modal-close");
    });
  });

  describe("actionDelete", () => {
    it("deletes the pending track for admins and closes the modal", () => {
      globalThis.pendingTrack = { video_id: "v3" };
      dom.actionDelete.click();

      expect(wsSend).toHaveBeenCalledWith("delete_download", { video_id: "v3" });
      expect(emit).toHaveBeenCalledWith("search:action-modal-close");
    });

    it("is a no-op for non-admins", () => {
      store.userRole = "client";
      globalThis.pendingTrack = { video_id: "v3" };
      dom.actionDelete.click();

      expect(wsSend).not.toHaveBeenCalled();
      expect(emit).not.toHaveBeenCalled();
    });

    it("still closes the modal for admins even with no pending track", () => {
      globalThis.pendingTrack = null;
      dom.actionDelete.click();

      expect(wsSend).not.toHaveBeenCalled();
      expect(emit).toHaveBeenCalledWith("search:action-modal-close");
    });
  });

  it("is safe to call when none of the dom elements exist", () => {
    Object.assign(dom, {
      actionPlayNow: null,
      actionEnqueue: null,
      actionCancel: null,
      actionDelete: null,
    });
    expect(() => initActionModalEvents()).not.toThrow();
  });
});
