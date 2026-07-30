import { on } from "../bus.js";
import { dom } from "../dom.js";
import { switchTab } from "./navigation.js";
import { showActionModal } from "./search.js";
import { store } from "/framework/static/js/core/store.js";
import { escapeHtml, formatTime } from "../utils/format.js";
import { cleanTrackTitle } from "../utils/cover-art.js";
import { showLogToast } from "./toast.js";
import { wsSend } from "../ws.js";

const HASHTAG_PALETTE = ['var(--g-pop)','var(--g-rock)','var(--g-indopop)','var(--g-jazz)','var(--g-electronic)','var(--g-other)'];
function getHashtagColor(hashtag) {
    let hash = 0;
    for (let i = 0; i < hashtag.length; i++) hash = (hash * 31 + hashtag.charCodeAt(i)) >>> 0;
    return HASHTAG_PALETTE[hash % HASHTAG_PALETTE.length];
}

const HASHTAG_VISIBLE_CAP = 16;
function renderHashtagCloud(container, items, buildPillHTML, isExpanded = false) {
    if (!container) return;
    if (!items || items.length === 0) { container.innerHTML = ''; return; }
    if (isExpanded) {
        container.innerHTML = items.map(buildPillHTML).join('') +
            `<button class="hashtag-more-btn hide-btn"><i class="ti ti-chevron-up" style="margin-right: 4px;"></i> Sembunyikan</button>`;
        const btn = container.querySelector('.hide-btn');
        if (btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                renderHashtagCloud(container, items, buildPillHTML, false);
            }, { once: true });
        }
    } else {
        const visible = items.slice(0, HASHTAG_VISIBLE_CAP);
        const rest = items.slice(HASHTAG_VISIBLE_CAP);
        container.innerHTML = visible.map(buildPillHTML).join('') +
            (rest.length
                ? `<button class="hashtag-more-btn" data-remaining="${rest.length}">+${rest.length} lainnya</button>`
                : '');
        const btn = container.querySelector('.hashtag-more-btn');
        if (btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                renderHashtagCloud(container, items, buildPillHTML, true);
            }, { once: true });
        }
    }
}

const LIST_PREVIEW_CAP = 5;
function renderTrackList(container, tracks, itemHTMLFn, emptyHTML, isExpanded = false) {
    if (!container) return;
    if (!tracks || tracks.length === 0) { container.innerHTML = emptyHTML; return; }
    if (isExpanded) {
        container.innerHTML = tracks.map(itemHTMLFn).join('') +
            `<button class="list-expand-btn hide-btn"><i class="ti ti-chevron-up" style="margin-right: 4px;"></i> Sembunyikan</button>`;
        const btn = container.querySelector('.hide-btn');
        if (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                renderTrackList(container, tracks, itemHTMLFn, emptyHTML, false);
                if (typeof globalThis.loadLazyCovers === 'function') globalThis.loadLazyCovers();
            }, { once: true });
        }
    } else {
        const preview = tracks.slice(0, LIST_PREVIEW_CAP);
        const rest = tracks.length - preview.length;
        container.innerHTML = preview.map(itemHTMLFn).join('') +
            (rest > 0 ? `<button class="list-expand-btn" data-remaining="${rest}">Lihat Semua (${tracks.length})</button>` : '');
        const btn = container.querySelector('.list-expand-btn');
        if (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                renderTrackList(container, tracks, itemHTMLFn, emptyHTML, true);
                if (typeof globalThis.loadLazyCovers === 'function') globalThis.loadLazyCovers();
            }, { once: true });
        }
    }
}


export function renderDiscoverTab() {

    if (dom.discArtists && store.discover_featured_artists) {
        renderHashtagCloud(dom.discArtists, store.discover_featured_artists, (artist) => {
            const name = typeof cleanTrackTitle === "function" ? escapeHtml(cleanTrackTitle(artist.nama)) : escapeHtml(artist.nama);
            const hashtag = "#" + name.replace(/\s+/g, '');
            const color = getHashtagColor(hashtag);
            const clicks = artist.click_count || 0;
            const bonusSize = Math.min(clicks * 2, 14); // Max +14px
            const fontSize = 14 + bonusSize; // 14px - 28px
            return `<div class="hashtag-pill" data-artist="${escapeHtml(artist.nama)}" style="color: ${color}; --base-size: ${fontSize}px;">${hashtag}</div>`;
        });

        dom.discArtists.onclick = (e) => {
            const pill = e.target.closest('.hashtag-pill');
            if (pill && pill.dataset.artist) {
                if (store.userRole !== 'admin') {
                    if (typeof showLogToast === 'function') showLogToast("Hanya admin yang bisa memutar musik");
                    return;
                }
                if (typeof showLogToast === 'function') showLogToast(`Memutar playlist dari ${pill.dataset.artist}...`);
                wsSend('enqueue_artist_songs', { artist: pill.dataset.artist });
                if (typeof switchTab === 'function') switchTab('home');
            }
        };
    }
    if (dom.discGenres && store.discover_featured_genres) {
        renderHashtagCloud(dom.discGenres, store.discover_featured_genres, (genre) => {
            const name = typeof cleanTrackTitle === "function" ? escapeHtml(cleanTrackTitle(genre.nama_genre)) : escapeHtml(genre.nama_genre);
            const hashtag = "#" + name.replace(/\s+/g, '');
            const color = getHashtagColor(hashtag);
            const clicks = genre.click_count || 0;
            const bonusSize = Math.min(clicks * 2, 14); // Max +14px
            const fontSize = 14 + bonusSize; // 14px - 28px
            return `<div class="hashtag-pill" data-genre="${escapeHtml(genre.nama_genre)}" style="color: ${color}; --base-size: ${fontSize}px;">${hashtag}</div>`;
        });

        dom.discGenres.onclick = (e) => {
            const pill = e.target.closest('.hashtag-pill');
            if (pill && pill.dataset.genre) {
                if (store.userRole !== 'admin') {
                    if (typeof showLogToast === 'function') showLogToast("Hanya admin yang bisa memutar musik");
                    return;
                }
                if (typeof showLogToast === 'function') showLogToast(`Memutar playlist dari genre ${pill.dataset.genre}...`);
                wsSend('enqueue_genre_songs', { genre: pill.dataset.genre });
                if (typeof switchTab === 'function') switchTab('home');
            }
        };
    }
    if (dom.discFavorites && store.discover_favorites) {
        const emptyHTML = '<div class="discover-empty"><i class="ti ti-heart" style="font-size:32px; opacity:0.6; margin-bottom:12px; display:block;"></i>Belum ada lagu favorit</div>';
        renderTrackList(dom.discFavorites, store.discover_favorites, (track) => {
            const title = typeof cleanTrackTitle === "function" ? escapeHtml(cleanTrackTitle(track.title)) : escapeHtml(track.title);
            let artistName = track.artist || "";
            if (artistName.length > 25) { artistName = artistName.substring(0, 22) + "..."; }
            const trackStr = JSON.stringify(track).replace(/'/g, "&apos;");
            return `
            <div class="sr-item" tabindex="0" role="button" aria-label="Putar ${escapeHtml(track.title)} — ${escapeHtml(track.artist)}" data-vid="${escapeHtml(track.video_id || '')}" data-track-str='${trackStr}'>
                <div class="sr-thumb">
                    <img class="lazy-cover" data-vid="${escapeHtml(track.video_id || '')}" data-title="${escapeHtml(track.title || '')}" data-artist="${escapeHtml(track.artist || '')}" data-thumb="${escapeHtml(track.thumbnail || '')}" src="" alt="">
                    <div class="thumb-eq-overlay"><div class="eq-anim-icon"><span></span><span></span><span></span></div></div>
                    ${track.local_path ? '<span class="disc-tag">cache</span>' : ''}
                </div>
                <div class="sr-info">
                    <div class="sr-title" title="${escapeHtml(track.title)}">${title}</div>
                    <div class="sr-meta">${escapeHtml(artistName)}</div>
                </div>
                <div class="sr-duration">${formatTime(track.duration)}</div>
                <button class="sr-more-btn" aria-label="More"><i class="ti ti-dots-vertical"></i></button>
            </div>`;
        }, emptyHTML);
    }
    if (dom.discCached && store.discover_cached) {
        const emptyHTML = '<div class="discover-empty"><i class="ti ti-box-off" style="font-size:32px; opacity:0.6; margin-bottom:12px; display:block;"></i>Tidak ada file tersimpan</div>';
        renderTrackList(dom.discCached, store.discover_cached, (track) => {
            const title = typeof cleanTrackTitle === "function" ? escapeHtml(cleanTrackTitle(track.title)) : escapeHtml(track.title);
            let artistName = track.artist || "";
            if (artistName.length > 25) { artistName = artistName.substring(0, 22) + "..."; }
            const trackStr = JSON.stringify(track).replace(/'/g, "&apos;");
            return `
            <div class="sr-item" tabindex="0" role="button" aria-label="Putar ${escapeHtml(track.title)} — ${escapeHtml(track.artist)}" data-vid="${escapeHtml(track.video_id || '')}" data-track-str='${trackStr}'>
                <div class="sr-thumb">
                    <img class="lazy-cover" data-vid="${escapeHtml(track.video_id || '')}" data-title="${escapeHtml(track.title || '')}" data-artist="${escapeHtml(track.artist || '')}" data-thumb="${escapeHtml(track.thumbnail || '')}" src="" alt="">
                    <div class="thumb-eq-overlay"><div class="eq-anim-icon"><span></span><span></span><span></span></div></div>
                </div>
                <div class="sr-info">
                    <div class="sr-title" title="${escapeHtml(track.title)}">${title}</div>
                    <div class="sr-meta">${escapeHtml(artistName)}</div>
                </div>
                <div class="sr-duration">${formatTime(track.duration)}</div>
                <button class="sr-more-btn" aria-label="More"><i class="ti ti-dots-vertical"></i></button>
            </div>`;
        }, emptyHTML);
    }
    if (typeof globalThis.loadLazyCovers === "function") {
        globalThis.loadLazyCovers();
    }

    updateDiscoverPlayingState();
}


export function updateDiscoverPlayingState() {
    const currentId = store.current_track && store.current_track.video_id;
    const isPlaying = store.status === "PLAYING";

    const homeRecentContainer = document.getElementById('home-recent-list');
    if (homeRecentContainer) {
        /** @type {NodeListOf<HTMLElement>} */
        (homeRecentContainer.querySelectorAll(".home-recent-item")).forEach(item => {
            const isCurrent = currentId && item.dataset.vid === currentId;
            item.classList.toggle("current", !!isCurrent);
            item.classList.toggle("playing", !!(isCurrent && isPlaying));
        });
    }

    if (dom.discRecent) {
        dom.discRecent.querySelectorAll(".sr-item").forEach(item => {
            const isCurrent = currentId && item.dataset.vid === currentId;
            item.classList.toggle("current", !!isCurrent);
            item.classList.toggle("playing", !!(isCurrent && isPlaying));
        });
    }

    if (dom.discFavorites) {
        dom.discFavorites.querySelectorAll(".sr-item").forEach(item => {
            const isCurrent = currentId && item.dataset.vid === currentId;
            item.classList.toggle("current", !!isCurrent);
            item.classList.toggle("playing", !!(isCurrent && isPlaying));
        });
    }

    if (dom.discCached) {
        dom.discCached.querySelectorAll(".sr-item").forEach(item => {
            const isCurrent = currentId && item.dataset.vid === currentId;
            item.classList.toggle("current", !!isCurrent);
            item.classList.toggle("playing", !!(isCurrent && isPlaying));
        });
    }
}

export function renderRecentRow() {
    const container = document.getElementById('home-recent-list');
    if (!container) return;

    const items = store.discover_recent || [];
    if (items.length === 0) {
        container.innerHTML = '<div style="padding:24px 20px; color:var(--text-3); font-size:14px; text-align:center;">Belum ada riwayat putar</div>';
        return;
    }

    const currentId = store.current_track && store.current_track.video_id;
    container.innerHTML = items.slice(0, 5).map(track => {
        const title = typeof cleanTrackTitle === 'function' ? escapeHtml(cleanTrackTitle(track.title)) : escapeHtml(track.title);
        const isCurrent = track.video_id && track.video_id === currentId;
        return `
        <div class="home-recent-item${isCurrent ? ' current' : ''}" data-vid="${escapeHtml(track.video_id || '')}">
            <div class="home-recent-thumb">
                <img class="lazy-cover" data-vid="${escapeHtml(track.video_id || '')}" data-title="${escapeHtml(track.title || '')}" data-artist="${escapeHtml(track.artist || '')}" data-thumb="${escapeHtml(track.thumbnail || '')}" src="" alt="">
            </div>
            <div class="home-recent-info">
                <div class="home-recent-title">${title}</div>
                <div class="home-recent-artist">${escapeHtml(track.artist || '')}</div>
            </div>
            <button class="home-recent-more" data-track='${JSON.stringify(track).replace(/'/g, "&apos;")}' aria-label="More">
                <i class="ti ti-dots-vertical"></i>
            </button>
        </div>`;
    }).join('');

    if (typeof globalThis.loadLazyCovers === "function") {
        globalThis.loadLazyCovers();
    }

    /** @type {NodeListOf<HTMLElement>} */
    (container.querySelectorAll('.home-recent-item')).forEach(el => {
        el.addEventListener('click', (e) => {
            const target = /** @type {Element} */ (e.target);
            if (target.closest('.home-recent-more')) return;
            if (store.userRole !== 'admin') return;
            const vid = el.dataset.vid;
            if (!vid) return;
            const track = (store.discover_recent || []).find(t => t.video_id === vid);
            if (track) wsSend('play_track', track);
        });
    });

    /** @type {NodeListOf<HTMLElement>} */
    (container.querySelectorAll('.home-recent-more')).forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            try {
                const track = JSON.parse(btn.dataset.track);
                if (typeof showActionModal === 'function') showActionModal(track);
            } catch { /* best-effort, aman diabaikan */ }
        });
    });
}

export function initDiscoverTabBusSubscriptions() {
    on("discover:tab-changed", renderDiscoverTab);
    on("discover:recent-changed", renderRecentRow);
    on("discover:playing-state", updateDiscoverPlayingState);
}
