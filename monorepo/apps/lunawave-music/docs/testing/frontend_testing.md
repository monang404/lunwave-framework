# Frontend Testing

> Test frontend menggunakan **Vitest** — fokus ke pure functions saja.
> Jangan paksa test DOM-heavy demi angka coverage.
> Prioritas keseluruhan: **Opsional** (rendah dibanding unit & integration test backend).

---

## Runner: Vitest

**Mengapa Vitest?**

- Ringan — tidak butuh build step besar
- Kompatibel vanilla JS tanpa bundler/framework
- ESM native — cocok dengan struktur module JS LunaWave
- API mirip Jest — kurva belajar minimal

### Setup

```bash
# Install (satu kali)
npm install -D vitest

# Jalankan
npx vitest run tests/frontend/

# Watch mode (development)
npx vitest tests/frontend/
```

### Konfigurasi Minimal (`vitest.config.js`)

```javascript
// vitest.config.js
export default {
  test: {
    environment: "node",   // bukan jsdom — kita test pure functions, bukan DOM
    include: ["tests/frontend/**/*.test.js"],
  },
};
```

---

## Target Test

Fokus ke **pure function** saja. Jangan test render, DOM, atau WebSocket connection langsung.

| Kode | Test | Prioritas |
|---|---|---|
| `utils/format.js` | `tests/frontend/utils/format.test.js` | Tinggi |
| `store.js` | `tests/frontend/store.test.js` | Sedang |
| `ws.js` *(bagian routing saja, bukan render)* | `tests/frontend/ws-routing.test.js` | Sedang |
| `utils/toast.js`, `render/*.js`, `events/*.js` | — | Manual / e2e smoke (Playwright) |

---

## Detail Per File

### `format.test.js` — Tinggi

`utils/format.js` berisi pure functions tanpa dependency apapun.
Test ini paling mudah ditulis dan paling bernilai.

```javascript
// tests/frontend/utils/format.test.js
import { describe, it, expect } from "vitest";
import { formatDuration, formatFileSize, truncateTitle } from "../../../static/utils/format.js";

describe("formatDuration", () => {
  it("formats seconds to mm:ss", () => {
    expect(formatDuration(90)).toBe("1:30");
  });

  it("formats hours correctly", () => {
    expect(formatDuration(3661)).toBe("1:01:01");
  });

  it("handles zero", () => {
    expect(formatDuration(0)).toBe("0:00");
  });
});

describe("truncateTitle", () => {
  it("truncates long titles", () => {
    expect(truncateTitle("A".repeat(100), 50)).toHaveLength(50);
  });

  it("preserves short titles", () => {
    expect(truncateTitle("Short", 50)).toBe("Short");
  });
});
```

---

### `store.test.js` — Sedang

`store.js` mengelola state aplikasi. Test fokus ke mutasi state yang bisa diprediksi.

```javascript
// tests/frontend/store.test.js
import { describe, it, expect, beforeEach } from "vitest";
import { createStore } from "../../../static/store.js";

describe("Store", () => {
  let store;

  beforeEach(() => {
    store = createStore();  // fresh store tiap test
  });

  it("initial state has expected shape", () => {
    expect(store.state.status).toBe("idle");
    expect(store.state.queue).toEqual([]);
    expect(store.state.currentTrack).toBeNull();
  });

  it("updateTrack mutates currentTrack", () => {
    store.updateTrack({ id: "1", title: "Test" });
    expect(store.state.currentTrack.title).toBe("Test");
  });

  it("addToQueue appends track", () => {
    store.addToQueue({ id: "1" });
    store.addToQueue({ id: "2" });
    expect(store.state.queue).toHaveLength(2);
  });
});
```

> **Syarat:** `store.js` harus ditulis sebagai module yang bisa di-import (export function `createStore`) — bukan object global. Jika saat ini masih global, refactor ke module factory dulu.

---

### `ws-routing.test.js` — Sedang

Test routing logic WebSocket — bukan koneksi asli, hanya fungsi yang memetakan message ke handler.

```javascript
// tests/frontend/ws-routing.test.js
import { describe, it, expect, vi } from "vitest";
import { routeMessage } from "../../../static/ws.js";

describe("WebSocket Message Router", () => {
  it("routes track_started to playback handler", () => {
    const handler = vi.fn();
    routeMessage({ type: "track_started", data: {} }, { onTrackStarted: handler });
    expect(handler).toHaveBeenCalledOnce();
  });

  it("routes download_progress to download handler", () => {
    const handler = vi.fn();
    routeMessage({ type: "download_progress", data: { percent: 50 } }, { onDownloadProgress: handler });
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({ percent: 50 }));
  });

  it("ignores unknown message types gracefully", () => {
    expect(() => {
      routeMessage({ type: "unknown_event" }, {});
    }).not.toThrow();
  });
});
```

> **Syarat:** `ws.js` harus mengeksport fungsi `routeMessage` yang bisa ditest secara isolasi. Jika saat ini routing tertanam dalam event handler WebSocket, pisahkan ke fungsi tersendiri.

---

## Yang Tidak Ditest

| Kategori | Contoh | Alasan |
|---|---|---|
| DOM manipulation | `render/*.js` | Butuh jsdom atau browser asli |
| Event listeners | `events/*.js` | Butuh DOM tree |
| WebSocket connection | `ws.js` koneksi asli | Side effect network |
| Toast notifications | `utils/toast.js` | DOM-dependent |

Untuk kategori ini, gunakan **manual QA checklist** atau **Playwright e2e smoke test** di masa depan.

---

## Struktur Folder Test Frontend

```
tests/
└── frontend/
    ├── utils/
    │   └── format.test.js       # Pure functions — prioritas tinggi
    ├── store.test.js       # State mutations
    └── ws-routing.test.js  # Message routing logic
```

---

## Referensi Terkait

- Strategi testing keseluruhan → [testing_strategy.md](testing_strategy.md)
- Arsitektur modul JS → [../frontend/ui_architecture.md](../frontend/ui_architecture.md)
- State management detail → [../frontend/state_management.md](../frontend/state_management.md)
- WebSocket routing detail → [../frontend/routing.md](../frontend/routing.md)
