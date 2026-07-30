import { describe, it, expect } from "vitest";
import { TABS } from "../../web/static/shared/js/config.js";

describe("config.js", () => {
  it("exports the expected list of tabs, in order", () => {
    expect(TABS).toEqual(["home", "search", "radio", "discover"]);
  });

  it("TABS is an array of exactly 4 unique string entries", () => {
    expect(Array.isArray(TABS)).toBe(true);
    expect(TABS).toHaveLength(4);
    expect(new Set(TABS).size).toBe(TABS.length);
    TABS.forEach((tab) => expect(typeof tab).toBe("string"));
  });
});
