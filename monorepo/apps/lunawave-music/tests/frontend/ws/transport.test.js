import { describe, it, expect } from "vitest";
import { wsConnect, wsSend } from "../../../web/static/shared/js/ws/transport.js";
import { store } from "../../../web/static/shared/js/store.js";

describe("transport.js", () => {
    it("exports wsConnect and wsSend", () => {
        expect(wsConnect).toBeTypeOf("function");
        expect(wsSend).toBeTypeOf("function");
    });

    it("queue_select clears a stale _pendingToggleTarget (FIX-PAUSE-RACE-01)", () => {
        store._pendingToggleTarget = "playing";
        wsSend("queue_select", { index: 2 });
        expect(store._pendingToggleTarget).toBe(null);
    });

    it("actions not in the clear-list leave _pendingToggleTarget untouched", () => {
        store._pendingToggleTarget = "playing";
        wsSend("toggle_play", {});
        expect(store._pendingToggleTarget).toBe("playing");

        store._pendingToggleTarget = "paused";
        wsSend("set_volume", { value: 50 });
        expect(store._pendingToggleTarget).toBe("paused");
    });
});
