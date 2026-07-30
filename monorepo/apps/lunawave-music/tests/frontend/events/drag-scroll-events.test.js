import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { initDragScrollEvents } from "../../../web/static/shared/js/events/drag-scroll-events.js";

// initDragScrollEvents() attaches several permanent document-level
// listeners (mousedown/mouseup/mouseleave/mousemove/click/dragstart) with
// no teardown hook. Calling it fresh each test would stack up listeners
// (the way platform/keyboard.js and events/keyboard-shortcut-events.js do),
// so we capture everything it registers via a spy and remove it all in
// afterEach to keep each test isolated to a single set of listeners.
let registered = [];

function captureAndInit() {
  const addSpy = vi.spyOn(document, "addEventListener");
  initDragScrollEvents();
  registered = addSpy.mock.calls.map(([type, handler, options]) => [type, handler, options]);
  addSpy.mockRestore();
}

function mouseEvent(type, opts = {}) {
  return new MouseEvent(type, { bubbles: true, cancelable: true, ...opts });
}

describe("events/drag-scroll-events.js", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div class="card-row" id="row"><div id="child">x</div></div>
      <div id="outside">y</div>
    `;
    captureAndInit();
  });

  afterEach(() => {
    for (const [type, handler, options] of registered) {
      document.removeEventListener(type, handler, options);
    }
    registered = [];
  });

  it("registers the expected set of document listeners", () => {
    const types = registered.map(([type]) => type).sort();
    expect(types).toEqual(
      ["click", "dragstart", "mousedown", "mouseleave", "mousemove", "mouseup"].sort()
    );
  });

  it("starts a drag on mousedown inside a draggable row and sets grabbing cursor", () => {
    const row = document.getElementById("row");
    const child = document.getElementById("child");
    Object.defineProperty(row, "offsetLeft", { value: 0, configurable: true });

    child.dispatchEvent(mouseEvent("mousedown", { clientX: 10, buttons: 1 }));

    expect(row.style.cursor).toBe("grabbing");
  });

  it("does nothing on mousedown outside a draggable row", () => {
    const outside = document.getElementById("outside");
    outside.dispatchEvent(mouseEvent("mousedown", { clientX: 10, buttons: 1 }));

    // No row picked up, so a subsequent mousemove should not throw or scroll anything.
    expect(() =>
      document.dispatchEvent(mouseEvent("mousemove", { clientX: 50, buttons: 1 }))
    ).not.toThrow();
  });

  it("drags: scrolls the row and prevents default once the movement passes the threshold", () => {
    const row = document.getElementById("row");
    Object.defineProperty(row, "offsetLeft", { value: 0, configurable: true });
    row.scrollLeft = 100;

    row.dispatchEvent(mouseEvent("mousedown", { clientX: 10, buttons: 1 }));

    const moveEvent = mouseEvent("mousemove", { clientX: 30, buttons: 1 });
    const preventSpy = vi.spyOn(moveEvent, "preventDefault");
    document.dispatchEvent(moveEvent);

    expect(preventSpy).toHaveBeenCalled();
    // walk = 20 (pageX-based), scrollLeft = 100 - 20*1.5 = 70
    expect(row.scrollLeft).toBe(70);
  });

  it("stops the drag when the mouse button is released mid-move (buttons !== 1)", () => {
    const row = document.getElementById("row");
    Object.defineProperty(row, "offsetLeft", { value: 0, configurable: true });

    row.dispatchEvent(mouseEvent("mousedown", { clientX: 10, buttons: 1 }));
    document.dispatchEvent(mouseEvent("mousemove", { clientX: 30, buttons: 0 }));

    expect(row.style.cursor).toBe("");
  });

  it("stops the drag on mouseup and resets the cursor", () => {
    const row = document.getElementById("row");
    Object.defineProperty(row, "offsetLeft", { value: 0, configurable: true });

    row.dispatchEvent(mouseEvent("mousedown", { clientX: 10, buttons: 1 }));
    expect(row.style.cursor).toBe("grabbing");

    document.dispatchEvent(mouseEvent("mouseup"));
    expect(row.style.cursor).toBe("");
  });

  it("stops the drag on mouseleave", () => {
    const row = document.getElementById("row");
    Object.defineProperty(row, "offsetLeft", { value: 0, configurable: true });

    row.dispatchEvent(mouseEvent("mousedown", { clientX: 10, buttons: 1 }));
    document.dispatchEvent(mouseEvent("mouseleave"));
    expect(row.style.cursor).toBe("");
  });

  it("suppresses the click that follows a drag (capture phase) and resets the dragging flag", () => {
    const row = document.getElementById("row");
    Object.defineProperty(row, "offsetLeft", { value: 0, configurable: true });

    row.dispatchEvent(mouseEvent("mousedown", { clientX: 10, buttons: 1 }));
    document.dispatchEvent(mouseEvent("mousemove", { clientX: 30, buttons: 1 })); // triggers isDragging=true

    const clickEvent = mouseEvent("click");
    const preventSpy = vi.spyOn(clickEvent, "preventDefault");
    const stopSpy = vi.spyOn(clickEvent, "stopPropagation");
    document.dispatchEvent(clickEvent);

    expect(preventSpy).toHaveBeenCalled();
    expect(stopSpy).toHaveBeenCalled();

    // A second click (no drag happened this time) should pass through untouched.
    const secondClick = mouseEvent("click");
    const secondPrevent = vi.spyOn(secondClick, "preventDefault");
    document.dispatchEvent(secondClick);
    expect(secondPrevent).not.toHaveBeenCalled();
  });

  it("prevents native dragstart on draggable rows", () => {
    const row = document.getElementById("row");
    const event = new Event("dragstart", { bubbles: true, cancelable: true });
    const preventSpy = vi.spyOn(event, "preventDefault");
    row.dispatchEvent(event);
    expect(preventSpy).toHaveBeenCalled();
  });

  it("does not prevent dragstart outside draggable rows", () => {
    const outside = document.getElementById("outside");
    const event = new Event("dragstart", { bubbles: true, cancelable: true });
    const preventSpy = vi.spyOn(event, "preventDefault");
    outside.dispatchEvent(event);
    expect(preventSpy).not.toHaveBeenCalled();
  });
});
