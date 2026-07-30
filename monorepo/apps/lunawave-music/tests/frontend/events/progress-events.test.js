import { describe, it, expect, vi, beforeEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  getOrInitAudio: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import { initProgressEvents } from "../../../web/static/shared/js/events/progress-events.js";
import { getOrInitAudio } from "../../../web/static/shared/js/audio/playback-sync.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

function makeTrack() {
  const track = document.createElement("div");
  track.id = "player-bar-track";
  track.getBoundingClientRect = vi.fn().mockReturnValue({ left: 0, width: 200 });
  track.setPointerCapture = vi.fn();
  track.releasePointerCapture = vi.fn();
  const thumb = document.createElement("div");
  thumb.className = "pb-thumb";
  thumb.style.left = "";
  track.appendChild(thumb);
  return track;
}

function pointerEvent(type, clientX, pointerId = 1) {
  return new PointerEvent(type, { clientX, pointerId, bubbles: true });
}

describe("events/progress-events.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = '<div id="player-bar"></div>';

    Object.assign(dom, {
      pbProgressTrack: makeTrack(),
      pbProgressFill: document.createElement("div"),
      pbTimePos: document.createElement("span"),
    });

    Object.assign(store, {
      userRole: "admin",
      audio_output: "browser",
      current_track: { duration: 100 },
    });

    initProgressEvents();
  });

  it("does nothing on pointerdown for a non-admin", () => {
    store.userRole = "client";
    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointerdown", 50));
    expect(dom.pbProgressTrack.setPointerCapture).not.toHaveBeenCalled();
  });

  it("pointerdown captures the pointer and updates the fill/time immediately", () => {
    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointerdown", 50));
    expect(dom.pbProgressTrack.setPointerCapture).toHaveBeenCalledWith(1);
    expect(dom.pbProgressFill.style.width).toBe("25%"); // 50/200
    expect(dom.pbTimePos.textContent).not.toBe("");
  });

  it("pointermove only updates while dragging", () => {
    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointermove", 100));
    expect(dom.pbProgressFill.style.width).toBe("");

    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointerdown", 0));
    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointermove", 100));
    expect(dom.pbProgressFill.style.width).toBe("50%");
  });

  it("pointerup seeks the live browser audio and notifies the server", () => {
    const audio = { src: "song.mp3", currentTime: 0 };
    getOrInitAudio.mockReturnValue(audio);

    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointerdown", 0));
    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointerup", 100));

    expect(dom.pbProgressTrack.releasePointerCapture).toHaveBeenCalledWith(1);
    expect(audio.currentTime).toBe(50); // 50% of 100s duration
    expect(wsSend).toHaveBeenCalledWith("seek", { position: 50 });
  });

  it("pointerup does not send seek when track has no duration", () => {
    store.current_track = { duration: 0 };
    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointerdown", 0));
    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointerup", 100));
    expect(wsSend).not.toHaveBeenCalledWith("seek", expect.anything());
  });

  it("pointerup is a no-op if pointerdown never happened (not dragging)", () => {
    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointerup", 100));
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("pointercancel releases capture without sending a seek", () => {
    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointerdown", 0));
    dom.pbProgressTrack.dispatchEvent(
      new PointerEvent("pointercancel", { pointerId: 1, bubbles: true })
    );
    expect(dom.pbProgressTrack.releasePointerCapture).toHaveBeenCalledWith(1);
    expect(wsSend).not.toHaveBeenCalled();
  });

  it("clamps percentage between 0 and 1 for out-of-range clientX", () => {
    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointerdown", -50));
    expect(dom.pbProgressFill.style.width).toBe("0%");

    dom.pbProgressTrack.dispatchEvent(pointerEvent("pointerdown", 999));
    expect(dom.pbProgressFill.style.width).toBe("100%");
  });
});
