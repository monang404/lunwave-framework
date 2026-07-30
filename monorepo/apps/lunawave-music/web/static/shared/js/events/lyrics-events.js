import { emit } from "../bus.js";
import { dom } from "../dom.js";
import { closeMainOverlay } from "./settings-events.js";
import { store } from "/framework/static/js/core/store.js";
import { syncLocalLyrics, wsSend } from "../ws.js";

const btnSyncMinus = document.getElementById("btn-sync-minus");
const btnSyncPlus = document.getElementById("btn-sync-plus");
const lyricsWrap = document.getElementById("lyrics-wrap");
const lyricSyncCtrls = document.getElementById("lyric-sync-ctrls");
let lyricSyncHideTimeout = null;

function showLyricSync() {
    if (lyricSyncCtrls) {
        lyricSyncCtrls.classList.add("active");
        if (lyricSyncHideTimeout) clearTimeout(lyricSyncHideTimeout);
        lyricSyncHideTimeout = setTimeout(() => {
            lyricSyncCtrls.classList.remove("active");
        }, 3000);
    }
}

export function initLyricsEvents() {
    if (dom.btnLyrics) {
        dom.btnLyrics.addEventListener("click", () => {
            if (dom.lyricsSheet) dom.lyricsSheet.classList.add("open");
            if (dom.mainOverlay) dom.mainOverlay.classList.add("open");
            emit("lyrics:changed");
        });
    }

    if (dom.lyricsCloseBtn) {
        dom.lyricsCloseBtn.addEventListener("click", () => {
            if (dom.lyricsSheet) dom.lyricsSheet.classList.remove("open");
            if (typeof closeMainOverlay === "function") closeMainOverlay();
        });
    }

    if (dom.lyricOffsetMinus) {
        dom.lyricOffsetMinus.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            store.lyrics_offset = (store.lyrics_offset || 0) - 0.5;
            emit("lyrics:offset-display");
            if (typeof syncLocalLyrics === "function") syncLocalLyrics();
            wsSend("lyrics_offset", { offset: store.lyrics_offset });
        });
    }

    if (dom.lyricOffsetPlus) {
        dom.lyricOffsetPlus.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            store.lyrics_offset = (store.lyrics_offset || 0) + 0.5;
            emit("lyrics:offset-display");
            if (typeof syncLocalLyrics === "function") syncLocalLyrics();
            wsSend("lyrics_offset", { offset: store.lyrics_offset });
        });
    }

    if (lyricsWrap && lyricSyncCtrls) {
        lyricsWrap.addEventListener("mousemove", showLyricSync);
        lyricsWrap.addEventListener("touchstart", showLyricSync, { passive: true });
        lyricsWrap.addEventListener("click", showLyricSync);

        if (btnSyncMinus) {
            btnSyncMinus.addEventListener("click", (e) => {
                e.stopPropagation();
                if (store.userRole !== "admin") return;
                store.lyrics_offset = (store.lyrics_offset || 0) - 0.5;
                emit("lyrics:offset-display");
                if (typeof syncLocalLyrics === "function") syncLocalLyrics();
                wsSend("lyrics_offset", { offset: store.lyrics_offset });
                showLyricSync();
            });
        }
        if (btnSyncPlus) {
            btnSyncPlus.addEventListener("click", (e) => {
                e.stopPropagation();
                if (store.userRole !== "admin") return;
                store.lyrics_offset = (store.lyrics_offset || 0) + 0.5;
                emit("lyrics:offset-display");
                if (typeof syncLocalLyrics === "function") syncLocalLyrics();
                wsSend("lyrics_offset", { offset: store.lyrics_offset });
                showLyricSync();
            });
        }
    }
}
