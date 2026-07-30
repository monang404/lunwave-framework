import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { dom } from "../../../web/static/shared/js/dom.js";
import { store } from "../../../web/static/shared/js/store.js";
import { emit } from "../../../web/static/shared/js/bus.js";
import { renderQueue, initQueueBusSubscriptions } from "../../../web/static/shared/js/render/queue.js";

function el(tag = "div") {
  return document.createElement(tag);
}

describe("render/queue.js", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.isDraggingQueue = false;
    globalThis.loadLazyCovers = vi.fn();
    document.body.removeAttribute("data-queue-empty");

    Object.assign(dom, {
      queueList: el(),
      radioQueueList: el(),
      queueFooter: el(),
    });

    Object.assign(store, {
      queue: [],
      radio_queue: [],
      playback_mode: "QUEUE",
      current_track: null,
      status: "PAUSED",
    });
  });

  afterEach(() => {
    delete globalThis.isDraggingQueue;
    delete globalThis.loadLazyCovers;
  });

  it("bails out entirely while the queue is being dragged", () => {
    globalThis.isDraggingQueue = true;
    dom.queueList.innerHTML = "<div>untouched</div>";
    renderQueue();
    expect(dom.queueList.innerHTML).toBe("<div>untouched</div>");
  });

  it("sets data-queue-empty=true on an empty queue and shows the empty-state message", () => {
    renderQueue();
    expect(document.body.dataset.queueEmpty).toBe("true");
    expect(dom.queueList.querySelector(".queue-empty")).toBeTruthy();
  });

  it("sets data-queue-empty=false once tracks are queued", () => {
    store.queue = [{ video_id: "v1", title: "T", artist: "A", duration: 100 }];
    renderQueue();
    expect(document.body.dataset.queueEmpty).toBe("false");
  });

  describe("queue list items", () => {
    it("renders one .queue-item per queued track with title/duration/index", () => {
      store.queue = [
        { video_id: "v1", title: "Kangen", artist: "Dewa 19", duration: 245 },
        { video_id: "v2", title: "Sephia", artist: "Sheila On 7", duration: 200 },
      ];
      renderQueue();

      const items = dom.queueList.querySelectorAll(".queue-item");
      expect(items.length).toBe(2);
      expect(items[0].querySelector(".qi-title").textContent).toBe("Kangen");
      expect(items[0].querySelector(".qi-dur").textContent).toBe("Dewa 19 · 04:05");
      expect(items[0].querySelector(".qi-index").textContent).toBe("1");
      expect(items[1].querySelector(".qi-index").textContent).toBe("2");
    });

    it("prepends the current track (as index -1) when this is the active mode", () => {
      store.current_track = { video_id: "cur", title: "Current", artist: "A", duration: 10 };
      store.queue = [{ video_id: "v1", title: "Next", artist: "B", duration: 20 }];
      store.playback_mode = "QUEUE";
      renderQueue();

      const items = dom.queueList.querySelectorAll(".queue-item");
      expect(items.length).toBe(2);
      expect(items[0].classList.contains("current")).toBe(true);
      expect(items[0].querySelector(".qi-title").textContent).toBe("Current");
    });

    it("does not prepend the current track when this list is not the active mode", () => {
      store.current_track = { video_id: "cur", title: "Current", artist: "A", duration: 10 };
      store.queue = [{ video_id: "v1", title: "Next", artist: "B", duration: 20 }];
      store.playback_mode = "RADIO"; // queue list is not the active mode now
      renderQueue();

      const items = dom.queueList.querySelectorAll(".queue-item");
      expect(items.length).toBe(1);
      expect(items[0].querySelector(".qi-title").textContent).toBe("Next");
    });

    it("shows a play-triangle for the current (not playing) item and an equalizer while playing", () => {
      store.current_track = { video_id: "cur", title: "Current", artist: "A", duration: 10 };
      store.playback_mode = "QUEUE";
      store.status = "PAUSED";
      renderQueue();
      let current = dom.queueList.querySelector(".queue-item.current");
      expect(current.querySelector(".qi-index").textContent).toBe("▶");

      store.status = "PLAYING";
      renderQueue();
      current = dom.queueList.querySelector(".queue-item.current");
      expect(current.querySelector(".qi-index").innerHTML).toContain("eq-anim-icon");
    });

    it("hides remove/drag controls for the current item and shows them for others", () => {
      store.current_track = { video_id: "cur", title: "Current", artist: "A", duration: 10 };
      store.queue = [{ video_id: "v1", title: "Next", artist: "B", duration: 20 }];
      store.playback_mode = "QUEUE";
      renderQueue();

      const [current, other] = dom.queueList.querySelectorAll(".queue-item");
      expect(current.querySelector(".qi-remove").style.display).toBe("none");
      expect(current.querySelector(".qi-drag").style.display).toBe("none");
      expect(other.querySelector(".qi-remove").style.display).toBe("block");
      expect(other.querySelector(".qi-remove").dataset.index).toBe("0");
    });

    it("reuses existing DOM nodes on re-render and trims extras when the list shrinks", () => {
      store.queue = [
        { video_id: "v1", title: "A", artist: "x", duration: 10 },
        { video_id: "v2", title: "B", artist: "x", duration: 10 },
      ];
      renderQueue();
      const firstNode = dom.queueList.children[0];

      store.queue = [{ video_id: "v1", title: "A-updated", artist: "x", duration: 10 }];
      renderQueue();

      expect(dom.queueList.children.length).toBe(1);
      expect(dom.queueList.children[0]).toBe(firstNode);
      expect(firstNode.querySelector(".qi-title").textContent).toBe("A-updated");
    });
  });

  describe("radio queue list", () => {
    it("shows the radio empty-state hint distinct from the manual queue one", () => {
      renderQueue();
      expect(dom.radioQueueList.querySelector(".queue-empty").textContent).toContain("Acak Ulang");
      expect(dom.queueList.querySelector(".queue-empty").textContent).toContain("Discover");
    });

    it("renders radio-queue-item nodes with title/artist and lazy-cover image", () => {
      store.radio_queue = [{ video_id: "r1", title: "Radio Track", artist: "Artist", duration: 90 }];
      renderQueue();

      const item = dom.radioQueueList.querySelector(".radio-queue-item");
      expect(item.querySelector(".radio-queue-title").textContent).toBe("Radio Track");
      expect(item.querySelector(".radio-queue-artist").textContent).toBe("Artist · 01:30");
      expect(item.querySelector(".lazy-cover")).toBeTruthy();
    });

    it("marks the current radio item as current+playing and sets lazy-cover dataset", () => {
      store.playback_mode = "RADIO";
      store.status = "PLAYING";
      store.current_track = { video_id: "r1", title: "Now", artist: "A", duration: 60, thumbnail: "t.jpg" };
      renderQueue();

      const item = dom.radioQueueList.querySelector(".radio-queue-item.current");
      expect(item.classList.contains("playing")).toBe(true);
      const img = item.querySelector(".lazy-cover");
      expect(img.dataset.vid).toBe("r1");
      expect(img.dataset.thumb).toBe("t.jpg");
    });

    it("does not reset the cover image when the track hasn't actually changed", () => {
      store.radio_queue = [{ video_id: "r1", title: "T", artist: "A", duration: 10 }];
      renderQueue();
      const img = dom.radioQueueList.querySelector(".lazy-cover");
      img.classList.add("loaded");
      img.src = "https://example.com/loaded.jpg";

      renderQueue(); // same track again
      expect(img.classList.contains("loaded")).toBe(true);
    });

    it("triggers lazy cover loading for a non-empty radio list", () => {
      store.radio_queue = [{ video_id: "r1", title: "T", artist: "A", duration: 10 }];
      renderQueue();
      expect(globalThis.loadLazyCovers).toHaveBeenCalled();
    });

    it("is a no-op when dom.radioQueueList is missing", () => {
      dom.radioQueueList = null;
      expect(() => renderQueue()).not.toThrow();
    });
  });

  describe("footer", () => {
    it("shows RADIO mode label when in radio mode", () => {
      store.playback_mode = "RADIO";
      renderQueue();
      expect(dom.queueFooter.innerHTML).toContain("RADIO");
    });

    it("shows QUEUE mode with track count and total duration when non-empty", () => {
      store.queue = [
        { video_id: "v1", title: "A", artist: "x", duration: 60 },
        { video_id: "v2", title: "B", artist: "x", duration: 120 },
      ];
      renderQueue();
      expect(dom.queueFooter.innerHTML).toContain("QUEUE");
      expect(dom.queueFooter.innerHTML).toContain("2 lagu");
      expect(dom.queueFooter.innerHTML).toContain("03:00");
    });

    it("shows just 'QUEUE' with no count/duration when the queue is empty", () => {
      renderQueue();
      expect(dom.queueFooter.innerHTML).toContain("QUEUE");
      expect(dom.queueFooter.innerHTML).not.toContain("lagu");
    });

    it("is a no-op when dom.queueFooter is missing", () => {
      dom.queueFooter = null;
      expect(() => renderQueue()).not.toThrow();
    });
  });

  it("initQueueBusSubscriptions wires queue:changed to renderQueue", () => {
    initQueueBusSubscriptions();
    store.queue = [{ video_id: "v1", title: "T", artist: "A", duration: 10 }];
    emit("queue:changed");
    expect(dom.queueList.querySelectorAll(".queue-item").length).toBe(1);
  });
});
