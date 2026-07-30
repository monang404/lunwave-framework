// utils/cover-art.js
// Diekstrak dari utils/toast.js (PATCH-2026-07-24, lanjutan recovery frontend)
// karena bagian toast (showConnectionToast/hideConnectionToast/showLogToast)
// butuh dom.js sehingga melanggar rule dependency-cruiser `utils-must-be-leaf`
// (utils/* wajib jadi leaf, tidak boleh import modul shared/js lain).
// File ini hanya berisi fungsi murni yang cuma menyentuh browser API global
// (localStorage, fetch, canvas, IntersectionObserver) -- bukan modul lain di
// shared/js -- jadi sah sebagai leaf util. Bagian toast (yang butuh dom.js)
// dipindah ke render/toast.js.

globalThis.safeStorage = {
    get: function(key) {
        try {
            let val = localStorage.getItem(key);
            if (val === null && key.startsWith("lunawave_")) {
                let legacyKey = key.replace("lunawave_", "ytgui_");
                val = localStorage.getItem(legacyKey);
                if (val !== null) {
                    localStorage.setItem(key, val);
                    localStorage.removeItem(legacyKey);
                }
            }
            return val;
        } catch { return null; }
    },
    set: function(key, value) {
        try { localStorage.setItem(key, value); } catch { /* best-effort, aman diabaikan */ }
    },
    remove: function(key) {
        try {
            localStorage.removeItem(key);
            if (key.startsWith("lunawave_")) {
                localStorage.removeItem(key.replace("lunawave_", "ytgui_"));
            }
        } catch { /* best-effort, aman diabaikan */ }
    }
};

globalThis.cleanTrackTitle = function(title) {
    if (!title) return "";
    return title.replace(/[[(].*?(official|music video|lyric|audio|live|performance).*?[\])]/gi, '')
                .replace(/#\S+/g, '')
                .replace(/\s{2,}/g, ' ')
                .replace(/\s+-\s*$/, '')
                .trim();
};

globalThis.getCoverArt = async function(track) {
    if (!track) return "";
    if (!track.video_id) return track.thumbnail || "";

    const cacheKey = "cover_" + track.video_id;
    const cachedStr = globalThis.safeStorage.get(cacheKey);
    if (cachedStr) {
        try {
            if (cachedStr.startsWith("{")) {
                const cached = JSON.parse(cachedStr);
                // 7 days TTL
                if (Date.now() - cached.ts < 7 * 24 * 60 * 60 * 1000) {
                    return cached.url;
                }
            } else {
                // legacy format without TTL
                return cachedStr;
            }
        } catch { /* best-effort, aman diabaikan */ }
    }

    const ytFallback = `https://i.ytimg.com/vi/${track.video_id}/hqdefault.jpg`;

    if (!track.title || !track.artist) {
        return track.thumbnail || ytFallback;
    }

    const saveCache = (url) => {
        globalThis.safeStorage.set(cacheKey, JSON.stringify({url: url, ts: Date.now()}));
        return url;
    };

    try {
        const cleanTitle = globalThis.cleanTrackTitle(track.title);
        const query = encodeURIComponent(track.artist + " " + cleanTitle);
        const res = await fetch(`https://itunes.apple.com/search?term=${query}&media=music&limit=1`);
        if (!res.ok) throw new Error("iTunes API failed");

        const data = await res.json();
        if (data.results && data.results.length > 0) {
            let artworkUrl = data.results[0].artworkUrl100;
            if (artworkUrl) {
                artworkUrl = artworkUrl.replace("100x100bb", "600x600bb");
                return saveCache(artworkUrl);
            }
        }
    } catch (e) {
        console.warn("Cover fetch error for", track.title, e);
    }

    return saveCache(ytFallback);
};

let _lazyCoverObserver = null;

globalThis.loadLazyCovers = function() {
    if (!_lazyCoverObserver) {
        _lazyCoverObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    observer.unobserve(img);
                    img.classList.add('loaded');
                    const vid = img.getAttribute('data-vid');
                    const title = img.getAttribute('data-title');
                    const artist = img.getAttribute('data-artist');
                    const defaultThumb = img.getAttribute('data-thumb');

                    if (!vid) return;

                    const track = { video_id: vid, title: title, artist: artist, thumbnail: defaultThumb };
                    globalThis.getCoverArtFast(img, track);
                }
            });
        }, { rootMargin: '200px' });
    }

    const images = document.querySelectorAll('img.lazy-cover:not(.observed)');
    images.forEach((img) => {
        img.classList.add('observed');
        _lazyCoverObserver.observe(img);
    });
};

// PATCH-COVER-FAST-LOAD-01: tampilkan thumbnail YouTube instan dulu (sudah
// tersedia tanpa network round-trip tambahan), baru upgrade ke artwork
// iTunes di background begitu selesai. Sebelumnya <img> dibiarkan kosong
// sampai fetch iTunes kelar, jadi cover terasa lambat muncul.
globalThis.getCoverArtFast = function(img, track) {
    if (!track) return;
    const ytFallback = track.thumbnail ||
        (track.video_id ? `https://i.ytimg.com/vi/${track.video_id}/hqdefault.jpg` : '');

    // Kalau sudah ada cache resolved (hi-res) yang masih valid, langsung pasang
    // itu — nggak perlu flash ke YT thumbnail dulu tiap re-render.
    if (track.video_id) {
        const cacheKey = "cover_" + track.video_id;
        const cachedStr = globalThis.safeStorage.get(cacheKey);
        if (cachedStr) {
            try {
                if (cachedStr.startsWith("{")) {
                    const cached = JSON.parse(cachedStr);
                    if (Date.now() - cached.ts < 7 * 24 * 60 * 60 * 1000) {
                        img.src = cached.url;
                        return;
                    }
                } else {
                    img.src = cachedStr;
                    return;
                }
            } catch { /* best-effort, aman diabaikan */ }
        }
    }

    // Belum ada cache: pasang thumbnail YT dulu biar keliatan cepat...
    if (ytFallback) img.src = ytFallback;

    // ...lalu resolve artwork lebih bagus di background dan upgrade diam-diam.
    globalThis.getCoverArt(track).then(coverUrl => {
        if (coverUrl && img.isConnected) img.src = coverUrl;
    });
};

globalThis.extractDominantColor = function(imgEl, callback) {
    if (!imgEl.complete || imgEl.naturalWidth === 0) {
        imgEl.addEventListener('load', () => globalThis.extractDominantColor(imgEl, callback), { once: true });
        return;
    }

    try {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        canvas.width = 50;
        canvas.height = 50;
        ctx.drawImage(imgEl, 0, 0, 50, 50);

        const data = ctx.getImageData(0, 0, 50, 50).data;
        let bestR = 0, bestG = 0, bestB = 0;
        let maxScore = -1;

        for (let i = 0; i < data.length; i += 16) {
            let r = data[i], g = data[i+1], b = data[i+2];
            let max = Math.max(r, g, b), min = Math.min(r, g, b);
            let l = (max + min) / 2;

            // Skip colors that are too dark or too bright
            if (l < 20 || l > 240) continue;

            let s = 0;
            if (max !== min) {
                s = l > 127 ? (max - min) / (510 - max - min) : (max - min) / (max + min);
            }

            let score = s * 100;
            if (score > maxScore) {
                maxScore = score;
                bestR = r; bestG = g; bestB = b;
            }
        }

        if (maxScore === -1) {
            let r = 0, g = 0, b = 0, count = 0;
            for (let i = 0; i < data.length; i += 16) {
                r += data[i]; g += data[i+1]; b += data[i+2]; count++;
            }
            bestR = Math.floor(r / count);
            bestG = Math.floor(g / count);
            bestB = Math.floor(b / count);
        }

        if (callback) callback({r: bestR, g: bestG, b: bestB});
    } catch (e) {
        console.warn("Color extraction failed:", e);
        if (callback) callback("var(--bg-elevated)");
    }
};

export const loadLazyCovers = globalThis.loadLazyCovers;

export const getCoverArt = globalThis.getCoverArt;

export const getCoverArtFast = globalThis.getCoverArtFast;

export const extractDominantColor = globalThis.extractDominantColor;

export const cleanTrackTitle = globalThis.cleanTrackTitle;
