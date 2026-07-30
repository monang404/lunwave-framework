import { describe, it, expect, vi, beforeEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";

vi.mock("../../../web/static/shared/js/audio/playback-sync.js", () => ({
  unlockBrowserAudio: vi.fn(),
}));
vi.mock("../../../web/static/shared/js/ws.js", () => ({ wsSend: vi.fn() }));

import { initQueueDragDrop, initQueueEvents } from "../../../web/static/shared/js/events/queue-events.js";
import { unlockBrowserAudio } from "../../../web/static/shared/js/audio/playback-sync.js";
import { wsSend } from "../../../web/static/shared/js/ws.js";

function buildQueueItem(index) {
  const item = document.createElement("div");
  item.className = "queue-item";
  item.dataset.index = String(index);
  item.setPointerCapture = vi.fn();
  item.releasePointerCapture = vi.fn();

  const handle = document.createElement("span");
  handle.className = "qi-drag";
  item.appendChild(handle);

  const removeBtn = document.createElement("button");
  removeBtn.className = "qi-remove";
  removeBtn.dataset.index = String(index);
  item.appendChild(removeBtn);

  return { item, handle, removeBtn };
}

function pointerEvent(type, { clientX = 0, clientY = 0, pointerId = 1, target } = {}) {
  const event = new PointerEvent(type, { clientX, clientY, pointerId, bubbles: true });
  if (target) Object.defineProperty(event, "target", { value: target });
  return event;
}

describe("events/queue-events.js", () => {
  let queueList;
  let itemA;
  let itemB;

  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = "";
    document.elementFromPoint = vi.fn();

    queueList = document.createElement("div");
    document.body.appendChild(queueList);

    const a = buildQueueItem(0);
    const b = buildQueueItem(1);
    itemA = a.item;
    itemB = b.item;
    queueList.appendChild(itemA);
    queueList.appendChild(itemB);

    dom.queueList = queueList;

    Object.assign(store, { userRole: "admin", audio_output: "browser" });

    initQueueEvents();
    initQueueDragDrop();
  });

  describe("click handling", () => {
    it("removes an item via the qi-remove button, stopping propagation to select", () => {
      itemA.querySelector(".qi-remove").dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(wsSend).toHaveBeenCalledWith("queue_remove", { index: 0 });
    });

    it("selects a queue item on click and unlocks browser audio", () => {
      itemB.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(unlockBrowserAudio).toHaveBeenCalledWith(true);
      expect(wsSend).toHaveBeenCalledWith("queue_select", { index: 1 });
    });

    it("ignores clicks on the drag handle itself", () => {
      itemA.querySelector(".qi-drag").dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(wsSend).not.toHaveBeenCalled();
    });

    it("does nothing for a non-admin", () => {
      store.userRole = "client";
      itemB.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(wsSend).not.toHaveBeenCalled();
    });
  });

  describe("drag to reorder", () => {
    it("starts dragging when pointerdown originates on the drag handle", () => {
      const handle = itemA.querySelector(".qi-drag");
      queueList.dispatchEvent(pointerEvent("pointerdown", { target: handle, pointerId: 7 }));
      expect(itemA.classList.contains("dragging")).toBe(true);
      expect(itemA.setPointerCapture).toHaveBeenCalledWith(7);
    });

    it("does not start dragging for a non-admin", () => {
      store.userRole = "client";
      const handle = itemA.querySelector(".qi-drag");
      queueList.dispatchEvent(pointerEvent("pointerdown", { target: handle }));
      expect(itemA.classList.contains("dragging")).toBe(false);
    });

    it("does not start dragging when pointerdown is not on a drag handle", () => {
      queueList.dispatchEvent(pointerEvent("pointerdown", { target: itemA }));
      expect(itemA.classList.contains("dragging")).toBe(false);
    });

    it("highlights the item under the pointer during pointermove", () => {
      const handle = itemA.querySelector(".qi-drag");
      queueList.dispatchEvent(pointerEvent("pointerdown", { target: handle }));

      document.elementFromPoint.mockReturnValue(itemB);
      document.dispatchEvent(pointerEvent("pointermove", { clientX: 10, clientY: 10 }));
      expect(itemB.classList.contains("drag-over")).toBe(true);
    });

    it("sends queue_reorder on pointerup when dropped on a different item", () => {
      const handle = itemA.querySelector(".qi-drag");
      queueList.dispatchEvent(pointerEvent("pointerdown", { target: handle }));

      document.elementFromPoint.mockReturnValue(itemB);
      document.dispatchEvent(pointerEvent("pointerup", { clientX: 10, clientY: 10 }));

      expect(wsSend).toHaveBeenCalledWith("queue_reorder", { from_index: 0, to_index: 1 });
      expect(itemA.classList.contains("dragging")).toBe(false);
    });

    it("does not send queue_reorder when dropped back on the same item", () => {
      const handle = itemA.querySelector(".qi-drag");
      queueList.dispatchEvent(pointerEvent("pointerdown", { target: handle }));

      document.elementFromPoint.mockReturnValue(itemA);
      document.dispatchEvent(pointerEvent("pointerup", { clientX: 5, clientY: 5 }));

      expect(wsSend).not.toHaveBeenCalledWith("queue_reorder", expect.anything());
    });

    it("cleans up drag state on pointercancel without sending a reorder", () => {
      const handle = itemA.querySelector(".qi-drag");
      queueList.dispatchEvent(pointerEvent("pointerdown", { target: handle }));
      document.dispatchEvent(new PointerEvent("pointercancel", { pointerId: 1, bubbles: true }));

      expect(itemA.classList.contains("dragging")).toBe(false);
      expect(wsSend).not.toHaveBeenCalled();
    });
  });
});
