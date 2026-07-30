import { describe, it, expect, vi } from "vitest";
import { on, off, emit } from "../../web/static/shared/js/bus.js";

describe("bus.js", () => {
  it("calls a subscribed handler with the emitted payload", () => {
    const handler = vi.fn();
    on("test:event", handler);
    emit("test:event", { foo: "bar" });
    expect(handler).toHaveBeenCalledWith({ foo: "bar" });
  });

  it("supports multiple handlers for the same event", () => {
    const h1 = vi.fn();
    const h2 = vi.fn();
    on("test:multi", h1);
    on("test:multi", h2);
    emit("test:multi", 1);
    expect(h1).toHaveBeenCalledWith(1);
    expect(h2).toHaveBeenCalledWith(1);
  });

  it("does not call handler after off() removes it", () => {
    const handler = vi.fn();
    on("test:off", handler);
    off("test:off", handler);
    emit("test:off", "payload");
    expect(handler).not.toHaveBeenCalled();
  });

  it("does nothing (no throw) when emitting an event with no listeners", () => {
    expect(() => emit("test:nobody-listens", 123)).not.toThrow();
  });

  it("off() on an event that was never registered does not throw", () => {
    expect(() => off("test:never-registered", () => {})).not.toThrow();
  });

  it("catches errors thrown inside a handler and still calls other handlers", () => {
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const throwing = vi.fn(() => {
      throw new Error("boom");
    });
    const safe = vi.fn();
    on("test:error", throwing);
    on("test:error", safe);

    expect(() => emit("test:error", "x")).not.toThrow();
    expect(throwing).toHaveBeenCalled();
    expect(safe).toHaveBeenCalledWith("x");
    expect(consoleErrorSpy).toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });

  it("only removes the specific handler, keeping others subscribed", () => {
    const h1 = vi.fn();
    const h2 = vi.fn();
    on("test:partial-off", h1);
    on("test:partial-off", h2);
    off("test:partial-off", h1);
    emit("test:partial-off", "payload");
    expect(h1).not.toHaveBeenCalled();
    expect(h2).toHaveBeenCalledWith("payload");
  });
});
