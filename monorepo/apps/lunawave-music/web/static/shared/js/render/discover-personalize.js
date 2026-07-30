import { emit, on } from "../bus.js";
import { dom } from "../dom.js";
import { switchTab } from "./navigation.js";
import { store } from "/framework/static/js/core/store.js";
import { escapeHtml, formatTime } from "../utils/format.js";
import { showLogToast } from "./toast.js";
import { wsSend } from "../ws.js";

// Discover Tab — personalization (Taste Spectrum, Untuk Kamu, Karena Kamu Suka,
// Belum Pernah Kamu Dengar, filter bar, artist detail sheet).
// Kept separate from discover-tab.js (yang sudah lewat ambang god-file 200 baris).

const GENRE_COLORS = {
    pop: "var(--g-pop)", rock: "var(--g-rock)", "indo pop": "var(--g-indopop)",
    indopop: "var(--g-indopop)", jazz: "var(--g-jazz)", electronic: "var(--g-electronic)",
};
function genreColor(name) {
    return GENRE_COLORS[(name || "").toLowerCase()] || "var(--g-other)";
}

let _discActiveKategori = "all";
let _discActiveDecade = "all";

export function getDecade(year) {
    if (!year) return null;
    const y = parseInt(year, 10);
    if (isNaN(y)) return null;
    return Math.floor(y / 10) * 10;
}

function renderTasteSpectrum() {
    if (!dom.tasteBar || !dom.tasteLegend) return;
    const spectrum = store.discover_taste_spectrum || [];
    if (spectrum.length === 0) {
        dom.tasteBar.innerHTML = "";
        dom.tasteLegend.innerHTML = '<div class="taste-fallback">Dengarkan beberapa lagu dulu untuk melihat selera kamu.</div>';
        return;
    }
    dom.tasteBar.innerHTML = spectrum.map(t =>
        `<div class="taste-seg" style="width:${t.pct}%; background:${genreColor(t.genre)}" title="${escapeHtml(t.genre)} ${t.pct}%"></div>`
    ).join('');
    dom.tasteLegend.innerHTML = spectrum.map(t =>
        `<div class="taste-legend-item"><span class="taste-dot" style="background:${genreColor(t.genre)}"></span>${escapeHtml(t.genre)} <b>${t.pct}%</b></div>`
    ).join('');
}

export function buildDecadeChips(allArtists) {
    if (!dom.decadeChips) return;
    const decadesSet = new Set();
    allArtists.forEach(a => {
        const dec = getDecade(a.tahun_aktif);
        if (dec) decadesSet.add(dec);
    });
    const decades = [...decadesSet].sort();
    const items = [`<button class="custom-dropdown-item${_discActiveDecade === 'all' ? ' active' : ''}" data-value="all">Semua Era</button>`]
        .concat(decades.map(d => `<button class="custom-dropdown-item${_discActiveDecade === String(d) ? ' active' : ''}" data-value="${d}">${d}an</button>`));
    dom.decadeChips.innerHTML = items.join('');
}

function artistCardHTML(a, opts) {
    opts = opts || {};
    const cover = a.cover
        ? `<img src="${escapeHtml(a.cover)}" alt="${escapeHtml(a.nama)}" loading="lazy">`
        : '<div class="art-fallback"><i class="ti ti-microphone-2"></i></div>';
    let badge = '';
    if (opts.badge === 'match' && typeof a.match_pct === 'number') badge = `<span class="badge badge-match">${a.match_pct}%</span>`;
    if (opts.badge === 'new') badge = '<span class="badge badge-new">Baru</span>';

    const dec = getDecade(a.tahun_aktif);
    const decadeBadge = dec ? `<span class="badge-decade">${dec}an</span>` : '';

    const genreTag = (a.genres && a.genres[0]) || a.kategori || '';
    return `<button class="artist-card${opts.undiscovered ? ' undiscovered' : ''}" data-artist="${escapeHtml(a.nama)}" data-kategori="${escapeHtml(a.kategori || '')}" data-decade="${escapeHtml(a.tahun_aktif || '')}">
        <div class="artist-card-art">${cover}${badge}${decadeBadge}</div>
        <div class="artist-card-name" title="${escapeHtml(a.nama)}">${escapeHtml(a.nama)}</div>
        <div class="artist-card-meta">${escapeHtml(genreTag)}</div>
    </button>`;
}

function filterArtists(list) {
    return (list || []).filter(a =>
        (_discActiveKategori === "all" || a.kategori === _discActiveKategori) &&
        (_discActiveDecade === "all" || String(getDecade(a.tahun_aktif)) === _discActiveDecade)
    );
}

function renderCardRow(container, artists, opts, emptyMsg) {
    if (!container) return;
    if (!artists || artists.length === 0) {
        container.innerHTML = `<div class="card-row-empty">${escapeHtml(emptyMsg)}</div>`;
        return;
    }
    container.innerHTML = artists.map(a => artistCardHTML(a, opts)).join('');
    container.onclick = (e) => {
        const card = e.target.closest('.artist-card');
        if (card && card.dataset.artist) {
            card.classList.add('touched');
            openArtistDetailSheet(card.dataset.artist);
        }
    };
    if (typeof globalThis.loadLazyCovers === "function") globalThis.loadLazyCovers();
}

function applyDiscoverFilters() {
    const forYou = filterArtists(store.discover_for_you);
    const genreArtists = filterArtists(store.discover_genre_affinity_artists);
    const unheard = filterArtists(store.discover_unheard);
    renderCardRow(dom.rowForYou, forYou, { badge: 'match' }, "Belum ada rekomendasi untuk filter ini.");
    renderCardRow(dom.rowGenreAffinity, genreArtists, {}, "Tidak ada artis untuk filter ini.");
    renderCardRow(dom.rowUnheard, unheard, { badge: 'new', undiscovered: true }, "Tidak ada artis untuk filter ini.");
}

export function renderDiscoverPersonalization() {
    renderTasteSpectrum();

    if (dom.rowGenreAffinityLabel) {
        const genre = store.discover_genre_affinity_genre;
        if (dom.rowGenreAffinitySub) dom.rowGenreAffinitySub.textContent = genre ? `Karena Kamu Suka ${genre}` : "Karena Kamu Suka";
        dom.rowGenreAffinityLabel.style.display = genre ? '' : 'none';
        if (dom.rowGenreAffinity) dom.rowGenreAffinity.style.display = genre ? '' : 'none';
    }

    const allArtists = [].concat(store.discover_for_you || [], store.discover_genre_affinity_artists || [], store.discover_unheard || []);
    buildDecadeChips(allArtists);
    applyDiscoverFilters();
}

export function initDiscoverFilterEvents() {
    if (dom.kategoriToggle) {
        dom.kategoriToggle.onclick = (e) => {
            const btn = e.target.closest('button');
            if (!btn) return;
            dom.kategoriToggle.querySelectorAll('button').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _discActiveKategori = btn.dataset.kategori;
            applyDiscoverFilters();
        };
    }
    const dropdownBtn = document.getElementById('decade-dropdown-btn');
    const dropdownContainer = document.getElementById('decade-dropdown-container');
    if (dropdownBtn && dropdownContainer) {
        dropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdownContainer.classList.toggle('open');
        });
        document.addEventListener('click', () => {
            dropdownContainer.classList.remove('open');
        });
    }

    if (dom.decadeChips) {
        dom.decadeChips.onclick = (e) => {
            const btn = e.target.closest('.custom-dropdown-item');
            if (!btn) return;
            dom.decadeChips.querySelectorAll('.custom-dropdown-item').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _discActiveDecade = btn.dataset.value;

            if (dropdownBtn) {
                dropdownBtn.innerHTML = `${btn.textContent} <i class="ti ti-chevron-down"></i>`;
            }

            applyDiscoverFilters();
        };
    }
    if (dom.adsCloseBtn) dom.adsCloseBtn.addEventListener('click', closeArtistDetailSheet);
    if (dom.adsPlayAll) dom.adsPlayAll.addEventListener('click', playAllFromArtistDetail);
}

function openArtistDetailSheet(nama) {
    globalThis.pendingArtistDetail = nama;
    if (dom.adsName) dom.adsName.textContent = nama;
    if (dom.adsTags) dom.adsTags.innerHTML = '';
    if (dom.adsCoverImg) dom.adsCoverImg.src = '';
    if (dom.adsTrackList) dom.adsTrackList.innerHTML = '<div class="ads-empty-tracks">Memuat...</div>';
    if (dom.artistDetailSheet) dom.artistDetailSheet.classList.add('open');
    if (dom.mainOverlay) dom.mainOverlay.classList.add('open');
    if (!nama || !nama.trim()) return;
    wsSend('get_artist_detail', { artist: nama });
}

function closeArtistDetailSheet() {
    if (dom.artistDetailSheet) dom.artistDetailSheet.classList.remove('open');
    emit("overlay:main-close");
    globalThis.pendingArtistDetail = null;
}

export function handleArtistDetail(data) {
    if (!dom.artistDetailSheet || !dom.artistDetailSheet.classList.contains('open')) return;
    if (!data) {
        if (dom.adsTrackList) dom.adsTrackList.innerHTML = '<div class="ads-empty-tracks">Artis tidak ditemukan.</div>';
        return;
    }
    globalThis.pendingArtistDetail = data.nama;
    if (dom.adsName) dom.adsName.textContent = data.nama || '';
    if (dom.adsCoverImg) dom.adsCoverImg.src = data.cover || '';
    if (dom.adsTags) {
        const tags = [data.kategori === 'band' ? 'Band' : 'Solo', data.tahun_aktif].concat(data.genres || []).filter(Boolean);
        dom.adsTags.innerHTML = tags.map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('');
    }
    const songs = data.songs || [];
    if (dom.adsTrackList) {
        dom.adsTrackList.innerHTML = songs.length === 0
            ? '<div class="ads-empty-tracks">Belum ada lagu untuk artis ini.</div>'
            : songs.map((s, i) => `<div class="track-row"><span class="track-idx">${i + 1}</span><span class="track-title">${escapeHtml(s.title)}</span><span class="track-dur">${formatTime(s.duration)}</span></div>`).join('');
    }
}

function playAllFromArtistDetail() {
    if (store.userRole !== 'admin') {
        if (typeof showLogToast === 'function') showLogToast("Hanya admin yang bisa memutar musik");
        return;
    }
    const nama = globalThis.pendingArtistDetail;
    if (!nama) return;
    wsSend('enqueue_artist_songs', { artist: nama });
    if (typeof showLogToast === 'function') showLogToast(`Memutar semua lagu ${nama}...`);
    closeArtistDetailSheet();
    if (typeof switchTab === 'function') switchTab('home');
}

export function initDiscoverPersonalizeBusSubscriptions() {
    on("discover:personalization-changed", renderDiscoverPersonalization);
    on("discover:artist-detail", (data) => handleArtistDetail(data));
}
