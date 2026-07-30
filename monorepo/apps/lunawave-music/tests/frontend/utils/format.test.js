import { describe, it, expect } from "vitest";
import * as formatUtils from "../../../web/static/shared/js/utils/format.js";

describe("formatTime", () => {
  it("formats seconds to mm:ss", () => {
    expect(formatUtils.formatTime(90)).toBe("01:30");
  });

  it("formats hours correctly", () => {
    expect(formatUtils.formatTime(3661)).toBe("61:01");
  });

  it("handles zero", () => {
    expect(formatUtils.formatTime(0)).toBe("00:00");
  });

  it("handles negative", () => {
    expect(formatUtils.formatTime(-10)).toBe("00:00");
  });
});

describe("escapeHtml", () => {
  it("escapes special characters", () => {
    expect(formatUtils.escapeHtml("<div id=\"test\">O'Hare & Co</div>")).toBe("&lt;div id=&quot;test&quot;&gt;O&#039;Hare &amp; Co&lt;/div&gt;");
  });

  it("handles empty string", () => {
    expect(formatUtils.escapeHtml("")).toBe("");
  });
});

describe("formatDurationLong", () => {
  it("formats sub-hour durations as mm:ss", () => {
    expect(formatUtils.formatDurationLong(90)).toBe("01:30");
  });

  it("formats durations over an hour as hh:mm:ss", () => {
    expect(formatUtils.formatDurationLong(3661)).toBe("01:01:01");
  });

  it("handles zero", () => {
    expect(formatUtils.formatDurationLong(0)).toBe("00:00:00");
  });

  it("handles negative values", () => {
    expect(formatUtils.formatDurationLong(-5)).toBe("00:00:00");
  });
});
