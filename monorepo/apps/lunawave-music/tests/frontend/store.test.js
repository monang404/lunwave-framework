import { describe, it, expect, beforeEach } from "vitest";
import * as storeModule from "../../web/static/shared/js/store.js";

describe("Store", () => {
  let store;

  beforeEach(() => {
    store = storeModule.createStore();
  });

  it("initial state has expected shape", () => {
    expect(store.status).toBe("IDLE");
    expect(store.queue).toEqual([]);
    expect(store.current_track).toBeNull();
  });

  it("update properties", () => {
    store.status = "PLAYING";
    store.volume = 50;

    expect(store.status).toBe("PLAYING");
    expect(store.volume).toBe(50);
  });
});
