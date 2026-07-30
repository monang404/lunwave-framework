import { ws, wsConnect, wsSend } from "/framework/static/js/core/transport.js";
import { routeMessage } from "/framework/static/js/core/router.js";
import { syncLocalLyrics } from "./ws/message-handlers/playback-messages.js";
import { renderHeader } from "./ws/message-handlers/auth-messages.js";

export {
    ws,
    wsConnect,
    wsSend,
    routeMessage as handleServerMessage,
    syncLocalLyrics,
    renderHeader
};

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { wsConnect, wsSend, handleServerMessage: routeMessage };
}
