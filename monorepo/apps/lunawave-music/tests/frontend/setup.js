import { vi } from "vitest";

Object.defineProperty(globalThis, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // Deprecated
    removeListener: vi.fn(), // Deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Provide a working in-memory localStorage for environments where jsdom
// does not expose one (e.g. Vitest 4+ without --localstorage-file).
if (typeof globalThis.localStorage === "undefined" || globalThis.localStorage === null) {
  // Define Storage constructor if not present.
  if (typeof globalThis.Storage === "undefined") {
    globalThis.Storage = function Storage() {};
  }

  const _store = {};

  // Implement methods on Storage.prototype so that spyOn(Storage.prototype, ...)
  // intercepts calls on our mock instance.
  Storage.prototype.getItem = function (key) {
    return Object.prototype.hasOwnProperty.call(_store, key) ? _store[key] : null;
  };
  Storage.prototype.setItem = function (key, value) {
    _store[key] = String(value);
  };
  Storage.prototype.removeItem = function (key) {
    delete _store[key];
  };
  Storage.prototype.clear = function () {
    Object.keys(_store).forEach((k) => delete _store[k]);
  };
  Object.defineProperty(Storage.prototype, "length", {
    get() { return Object.keys(_store).length; },
    configurable: true,
  });
  Storage.prototype.key = function (i) {
    return Object.keys(_store)[i] ?? null;
  };

  // Create the singleton instance that inherits from Storage.prototype.
  const _localStorage = Object.create(Storage.prototype);
  Object.defineProperty(globalThis, "localStorage", {
    value: _localStorage,
    writable: true,
    configurable: true,
  });
}
