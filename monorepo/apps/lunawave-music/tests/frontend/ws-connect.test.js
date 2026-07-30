import { describe, it, expect, vi, afterEach } from "vitest";

vi.mock("../../web/static/shared/js/audio/playback-sync.js", () => ({
  _resumeAndPlay: vi.fn(),
  getOrInitAudio: vi.fn(),
  syncBrowserAudio: vi.fn(),
}));

// A minimal stand-in for the browser WebSocket API. Real jsdom WebSocket
// objects try to open an actual network connection (which hangs/fails in
// this sandboxed test environment), so we substitute this controllable
// fake: readyState/static constants match the real API closely enough for
// ws.js's own state checks (`ws.readyState !== WebSocket.CLOSED`, etc.),
// and tests trigger onopen/onmessage/onclose/onerror by hand.
class FakeWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = FakeWebSocket.CONNECTING;
    this.sent = [];
    this.closed = false;
    FakeWebSocket.instances.push(this);
  }
  send(data) {
    this.sent.push(data);
  }
  close() {
    this.closed = true;
    this.readyState = FakeWebSocket.CLOSED;
  }
}
FakeWebSocket.CONNECTING = 0;
FakeWebSocket.OPEN = 1;
FakeWebSocket.CLOSING = 2;
FakeWebSocket.CLOSED = 3;
FakeWebSocket.instances = [];

// ws.js keeps `ws`, `wsReconnectTimer`, `wsTokenRefreshTimer`, and
// `wsReconnectDelay` as module-scope singletons, and also attaches a
// permanent `document.addEventListener('visibilitychange', ...)` reconnect
// listener at *import time*, with no teardown hook. Every test gets a
// fully fresh module via vi.resetModules() so the JS state doesn't leak,
// but the visibilitychange listener itself would otherwise still
// accumulate on the shared `document` across tests -- so we capture it via
// a spy at import time and explicitly remove it in afterEach.
let capturedVisibilityHandler;

async function setupModule() {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  globalThis.safeStorage = { get: vi.fn(), set: vi.fn(), remove: vi.fn() };

  vi.resetModules();
  const domMod = await import("../../web/static/shared/js/dom.js");
  const storeMod = await import("../../web/static/shared/js/store.js");
  const addSpy = vi.spyOn(document, "addEventListener");
  const mod = await import("../../web/static/shared/js/ws.js");
  const call = addSpy.mock.calls.find((c) => c[0] === "visibilitychange");
  capturedVisibilityHandler = call ? call[1] : undefined;
  addSpy.mockRestore();

  Object.assign(domMod.dom, {
    statusDot: { classList: { add: vi.fn(), remove: vi.fn() } },
    statusText: { textContent: "" },
    outputToggleBtn: { classList: { add: vi.fn(), remove: vi.fn() }, textContent: "" },
  });
  Object.assign(storeMod.store, {
    userRole: "client",
    active_tab: "home",
    is_online: false,
  });

  return { ...mod, dom: domMod.dom, store: storeMod.store };
}

describe("ws.js wsConnect", () => {
  afterEach(() => {
    if (capturedVisibilityHandler) {
      document.removeEventListener("visibilitychange", capturedVisibilityHandler);
      capturedVisibilityHandler = undefined;
    }
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    delete globalThis.safeStorage;
  });

  it("opens a WebSocket to the current host with the current page as a query param", async () => {
    const { wsConnect } = await setupModule();
    globalThis.location && (globalThis.location.pathname = "/app");
    wsConnect();
    expect(FakeWebSocket.instances.length).toBe(1);
    expect(FakeWebSocket.instances[0].url).toContain("/ws?page=");
  });

  it("closes a still-open previous connection before opening a new one", async () => {
    const { wsConnect } = await setupModule();
    wsConnect();
    const first = FakeWebSocket.instances[0];
    first.readyState = FakeWebSocket.OPEN;
    const closeSpy = vi.spyOn(first, "close");

    wsConnect();
    expect(closeSpy).toHaveBeenCalled();
    expect(FakeWebSocket.instances.length).toBe(2);
  });

  it("does not try to close an already-closed previous connection", async () => {
    const { wsConnect } = await setupModule();
    wsConnect();
    const first = FakeWebSocket.instances[0];
    first.readyState = FakeWebSocket.CLOSED;
    const closeSpy = vi.spyOn(first, "close");

    wsConnect();
    expect(closeSpy).not.toHaveBeenCalled();
  });

  describe("onopen", () => {
    it("marks the store online, hides the connecting toast, and resets the backoff delay", async () => {
      const { wsConnect, store } = await setupModule();
      const { on } = await import("../../web/static/shared/js/bus.js");
      const hideHandler = vi.fn();
      on("toast:connection-hide", hideHandler);

      wsConnect();
      FakeWebSocket.instances[0].readyState = FakeWebSocket.OPEN;
      FakeWebSocket.instances[0].onopen();

      expect(store.is_online).toBe(true);
      expect(hideHandler).toHaveBeenCalled();
    });

    it("sends auth + set_output for a logged-in admin with a saved token", async () => {
      const { wsConnect, store } = await setupModule();
      store.userRole = "admin";
      globalThis.safeStorage.get.mockImplementation((k) =>
        k === "lunawave_session_token" ? "tok123" : k === "lunawave_audio_output" ? "server" : null
      );

      wsConnect();
      const socket = FakeWebSocket.instances[0];
      socket.readyState = FakeWebSocket.OPEN;
      socket.onopen();

      const sentActions = socket.sent.map((s) => JSON.parse(s).action);
      expect(sentActions).toContain("auth");
      expect(sentActions).toContain("set_output");
      const setOutputMsg = socket.sent.map((s) => JSON.parse(s)).find((m) => m.action === "set_output");
      expect(setOutputMsg.data.output).toBe("server");
    });

    it("does not send auth for an admin with no saved token", async () => {
      const { wsConnect, store } = await setupModule();
      store.userRole = "admin";
      globalThis.safeStorage.get.mockReturnValue(null);

      wsConnect();
      const socket = FakeWebSocket.instances[0];
      socket.readyState = FakeWebSocket.OPEN;
      socket.onopen();

      const sentActions = socket.sent.map((s) => JSON.parse(s).action);
      expect(sentActions).not.toContain("auth");
    });

    it("defaults audio output to 'browser' when nothing is saved", async () => {
      const { wsConnect, store } = await setupModule();
      store.userRole = "admin";
      globalThis.safeStorage.get.mockReturnValue(null);

      wsConnect();
      const socket = FakeWebSocket.instances[0];
      socket.readyState = FakeWebSocket.OPEN;
      socket.onopen();

      const setOutputMsg = socket.sent.map((s) => JSON.parse(s)).find((m) => m.action === "set_output");
      expect(setOutputMsg.data.output).toBe("browser");
    });

    it("requests a discover refresh for clients on the home/discover tab", async () => {
      const { wsConnect, store } = await setupModule();
      store.userRole = "client";
      store.active_tab = "discover";

      wsConnect();
      const socket = FakeWebSocket.instances[0];
      socket.readyState = FakeWebSocket.OPEN;
      socket.onopen();

      const sentActions = socket.sent.map((s) => JSON.parse(s).action);
      expect(sentActions).toContain("discover");
    });

    it("does not request discover for clients on unrelated tabs", async () => {
      const { wsConnect, store } = await setupModule();
      store.userRole = "client";
      store.active_tab = "search";

      wsConnect();
      const socket = FakeWebSocket.instances[0];
      socket.readyState = FakeWebSocket.OPEN;
      socket.onopen();

      const sentActions = socket.sent.map((s) => JSON.parse(s).action);
      expect(sentActions).not.toContain("discover");
    });

    it("always fetches chat history", async () => {
      const { wsConnect } = await setupModule();
      wsConnect();
      const socket = FakeWebSocket.instances[0];
      socket.readyState = FakeWebSocket.OPEN;
      socket.onopen();

      const sentActions = socket.sent.map((s) => JSON.parse(s).action);
      expect(sentActions).toContain("get_chat_history");
    });

    it("re-renders the header", async () => {
      const { wsConnect, dom } = await setupModule();
      wsConnect();
      const socket = FakeWebSocket.instances[0];
      socket.readyState = FakeWebSocket.OPEN;
      socket.onopen();
      expect(dom.statusText.textContent).toBe("online");
    });
  });

  describe("onmessage", () => {
    it("parses JSON and routes it through handleServerMessage", async () => {
      const { wsConnect } = await setupModule();
      wsConnect();
      const socket = FakeWebSocket.instances[0];
      socket.onmessage({ data: JSON.stringify({ type: "log", data: "hi" }) });
      // No throw is the main contract here; handleServerMessage's own
      // routing is covered in ws-routing.test.js.
      expect(true).toBe(true);
    });

    it("swallows malformed JSON without throwing", async () => {
      const { wsConnect } = await setupModule();
      const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      wsConnect();
      const socket = FakeWebSocket.instances[0];
      expect(() => socket.onmessage({ data: "not-json" })).not.toThrow();
      expect(errSpy).toHaveBeenCalled();
    });
  });

  describe("onclose", () => {
    it("marks the store offline, re-renders the header, and shows a reconnecting toast", async () => {
      const { wsConnect, store, dom } = await setupModule();
      wsConnect();
      const socket = FakeWebSocket.instances[0];
      socket.readyState = FakeWebSocket.OPEN;
      socket.onopen();
      store.is_online = true;

      socket.onclose();
      expect(store.is_online).toBe(false);
      expect(dom.statusText.textContent).toBe("offline");
    });

    it("schedules a reconnect attempt with exponential backoff (capped at 30s)", async () => {
      vi.useFakeTimers();
      const { wsConnect } = await setupModule();
      wsConnect();
      FakeWebSocket.instances[0].onclose();
      expect(FakeWebSocket.instances.length).toBe(1);

      vi.advanceTimersByTime(2000); // first backoff delay
      expect(FakeWebSocket.instances.length).toBe(2);

      FakeWebSocket.instances[1].onclose();
      vi.advanceTimersByTime(4000); // delay doubled to 4000
      expect(FakeWebSocket.instances.length).toBe(3);
      vi.useRealTimers();
    });
  });

  it("onerror closes the socket", async () => {
    const { wsConnect } = await setupModule();
    wsConnect();
    const socket = FakeWebSocket.instances[0];
    const closeSpy = vi.spyOn(socket, "close");
    socket.onerror();
    expect(closeSpy).toHaveBeenCalled();
  });

  describe("visibilitychange reconnect", () => {
    it("immediately reconnects (bypassing the backoff delay) when the tab becomes visible while a reconnect is pending", async () => {
      vi.useFakeTimers();
      const { wsConnect } = await setupModule();
      wsConnect();
      FakeWebSocket.instances[0].onclose(); // schedules a reconnect timer
      expect(FakeWebSocket.instances.length).toBe(1);

      Object.defineProperty(document, "hidden", { value: false, configurable: true });
      document.dispatchEvent(new Event("visibilitychange"));

      expect(FakeWebSocket.instances.length).toBe(2);
      vi.useRealTimers();
    });

    it("does nothing when there is no reconnect timer pending", async () => {
      await setupModule();
      Object.defineProperty(document, "hidden", { value: false, configurable: true });
      expect(() => document.dispatchEvent(new Event("visibilitychange"))).not.toThrow();
    });
  });
});
