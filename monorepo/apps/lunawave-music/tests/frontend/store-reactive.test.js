import { describe, it, expect, vi, beforeEach } from "vitest";
import { store, onStoreChange, onAnyStoreChange, createStore } from "../../web/static/shared/js/store.js";

describe("Reactive Store", () => {
  beforeEach(() => {
    // Reset properties to default to prevent cross-test contamination on the singleton
    const defaults = createStore();
    for (const key in defaults) {
      if (store[key] !== defaults[key]) {
         store[key] = defaults[key];
      }
    }
  });

  it("(1) subscribe to specific field and change value -> callback called with correct args", () => {
    const callback = vi.fn();
    const unsubscribe = onStoreChange("status", callback);

    store.status = "PLAYING";

    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith("PLAYING", "IDLE");

    unsubscribe();
  });

  it("(2) assign identical value -> callback NOT called", () => {
    const callback = vi.fn();
    const unsubscribe = onStoreChange("status", callback);

    store.status = "IDLE";

    expect(callback).not.toHaveBeenCalled();

    unsubscribe();
  });

  it("(3) unsubscribe -> callback not called again", () => {
    const callback = vi.fn();
    const unsubscribe = onStoreChange("status", callback);

    unsubscribe();

    store.status = "PAUSED";

    expect(callback).not.toHaveBeenCalled();
  });

  it("(4) onAnyStoreChange called for ANY field change", () => {
    const callback = vi.fn();
    const unsubscribe = onAnyStoreChange(callback);

    store.volume = 50;

    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith("volume", 50, 80);

    store.playback_mode = "REPEAT";
    expect(callback).toHaveBeenCalledTimes(2);
    expect(callback).toHaveBeenCalledWith("playback_mode", "REPEAT", "QUEUE");

    unsubscribe();
  });

  it("(5) unassigned field does not trigger false notify", () => {
    const callback = vi.fn();
    const unsubscribe = onStoreChange("loop_mode", callback);

    const mode = store.loop_mode;
    expect(mode).toBe("off");

    expect(callback).not.toHaveBeenCalled();

    unsubscribe();
  });
});
