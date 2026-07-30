import { on } from "../bus.js";
import { dom } from "../dom.js";
import { store } from "/framework/static/js/core/store.js";
import { escapeHtml } from "../utils/format.js";

export function renderLyrics() {
    renderSheetLyrics();
    renderHomeLyrics();
}

function renderSheetLyrics() {
    if (!dom.lyricsSheet || !dom.lyricsSheet.classList.contains("open")) return;

    if (!dom.lyricsContent._scrollBound) {
        dom.lyricsContent._scrollBound = true;
        let scrollTimeout;
        const setScrolling = () => {
            globalThis.isScrollingLyrics = true;
            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => globalThis.isScrollingLyrics = false, 3000);
        };
        dom.lyricsContent.addEventListener("wheel", setScrolling, {passive: true});
        dom.lyricsContent.addEventListener("touchmove", setScrolling, {passive: true});
    }

    const lines = store.lyrics_lines;
    const idx = store.lyrics_index;

    if (!lines || lines.length === 0) {
        dom.lyricsContent.innerHTML = '<div style="color:var(--fm-text-5)">Tidak ada lirik tersedia</div>';
        return;
    }

    const start = Math.max(0, idx - 5);
    const end = Math.min(lines.length, idx + 6);

    let html = "";
    for (let i = start; i < end; i++) {
        const text = escapeHtml(lines[i]);
        if (i === idx) {
            html += '<div class="lyric-line active">' + text + '</div>';
        } else if (i < idx) {
            html += '<div class="lyric-line past">' + text + "</div>";
        } else {
            html += '<div class="lyric-line future">' + text + "</div>";
        }
    }
    dom.lyricsContent.innerHTML = html;

    const activeLine = dom.lyricsContent.querySelector(".lyric-line.active");
    if (activeLine && !globalThis.isScrollingLyrics) {
        activeLine.scrollIntoView({ behavior: "smooth", block: "center" });
    }
}

function renderHomeLyrics() {
    if (!dom.lyricsCurrent || !dom.lyricsPrev || !dom.lyricsNext) return;

    if (!store.lyrics_lines || store.lyrics_lines.length === 0) {
        document.body.setAttribute("data-has-lyrics", "false");
        if (dom.lyricsTextContainer) dom.lyricsTextContainer.style.display = "none";
        // Teks "Audio Focus" selalu muncul walau lagu sedang dipause (karena ini bukan visualizer gerak)
        if (dom.homeEqualizer) {
            dom.homeEqualizer.style.display = "flex";
        }
        return;
    }

    document.body.setAttribute("data-has-lyrics", "true");
    if (dom.lyricsTextContainer) dom.lyricsTextContainer.style.display = "flex";
    // Sembunyikan equalizer karena lirik sudah tersedia
    if (dom.homeEqualizer) dom.homeEqualizer.style.display = "none";

    dom.lyricsPrev.className = "lyrics-line prev lyric-pop";
    dom.lyricsCurrent.className = "lyrics-line current lyric-pop";
    dom.lyricsNext.className = "lyrics-line next lyric-pop";

    if (dom.lyricsCurrent._popTimeout) clearTimeout(dom.lyricsCurrent._popTimeout);
    dom.lyricsCurrent._popTimeout = setTimeout(() => {
        if (dom.lyricsPrev) dom.lyricsPrev.className = "lyrics-line prev";
        if (dom.lyricsCurrent) dom.lyricsCurrent.className = "lyrics-line current";
        if (dom.lyricsNext) dom.lyricsNext.className = "lyrics-line next";
    }, 700);

    const idx = store.lyrics_index || 0;
    const lines = store.lyrics_lines;

    dom.lyricsPrev.innerHTML = idx > 0 ? escapeHtml(lines[idx - 1]) : "&nbsp;";
    dom.lyricsCurrent.innerHTML = escapeHtml(lines[idx] || "&nbsp;");
    dom.lyricsNext.innerHTML = idx < lines.length - 1 ? escapeHtml(lines[idx + 1]) : "&nbsp;";
}

export function updateOffsetDisplay() {
    const el = document.getElementById("sync-val");
    if (!el) return;
    const val = store.lyrics_offset || 0;
    const sign = val >= 0 ? '+' : '';
    el.textContent = sign + val.toFixed(1) + 's';
}

export function initLyricsBusSubscriptions() {
    on("lyrics:changed", renderLyrics);
    on("lyrics:offset-display", updateOffsetDisplay);
}
