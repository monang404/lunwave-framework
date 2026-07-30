import { _fadeIntervals, activeAudioIndex, getOrInitAudio } from "../audio/playback-sync.js";
import { on } from "../bus.js";
import { dom } from "../dom.js";
import { syncPlayerStateAttr } from "./now-playing.js";
import { store } from "/framework/static/js/core/store.js";
import { escapeHtml, formatTime } from "../utils/format.js";
import { cleanTrackTitle } from "../utils/cover-art.js";

export function renderPlayerBar() {
    // PATCH-ANDROID-AUDIO-01: dulu baris ini menimpa data-player-state dengan logic
    // berbeda dari now-playing.js (cuma cek store.status, gak cek track),
    // bikin idle-view bisa nyangkut salah. Sekarang pakai fungsi bersama.
    if (typeof syncPlayerStateAttr === "function") syncPlayerStateAttr();
    const t = store.current_track;

    if (store.status === "LOADING") {
        dom.pbTrackInfo.innerHTML = '<span class="spinner" style="display:inline-block; margin-right:5px; vertical-align:-2px;"></span> Memuat... ' + escapeHtml(t ? t.title : "");
    } else if (t) {
        const title = typeof cleanTrackTitle === "function" ? cleanTrackTitle(t.title) : t.title;
        const thumbUrl = t.thumbnail || '';
        const fallbackIcon = `<i class="ti ti-music" style="color:var(--text-3); font-size:20px;"></i>`;
        const thumbHtml = thumbUrl ? `<img src="${escapeHtml(thumbUrl)}" style="width:44px; height:44px; border-radius:6px; object-fit:cover; flex-shrink:0;">` : `<div style="width:44px; height:44px; border-radius:6px; background:rgba(255,255,255,0.1); flex-shrink:0; display:flex; align-items:center; justify-content:center;">${fallbackIcon}</div>`;
        dom.pbTrackInfo.innerHTML = `
            <div style="display:flex; align-items:center; gap:12px; min-width:0;">
                ${thumbHtml}
                <div style="display:flex; flex-direction:column; justify-content:center; line-height:1.3; overflow:hidden; min-width:0;">
                    <span style="font-weight:600; font-size:14px; color:var(--text-1); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(title)}</span>
                    <span style="font-size:12px; color:var(--text-3); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(t.artist)}</span>
                </div>
            </div>
        `;
    } else {
        dom.pbTrackInfo.innerHTML = "";
    }

    renderPlayBtn();

    if (store.playback_mode === "RADIO") {
        dom.pbModeBadge.textContent = "📻 radio";
        dom.pbModeBadge.className = "pb-mode-badge radio";
        dom.btnRepeat.style.display = "none";
        // PATCH-HIDE-SHUFFLE-RADIO-01: samain kayak repeat — di mode radio,
        // shuffle nggak relevan (radio udah otomatis "acak" lagu baru), jadi
        // ikut disembunyikan biar layout tombol tetap simetris.
        if (dom.btnShuffle) dom.btnShuffle.style.display = "none";
    } else {
        dom.pbModeBadge.textContent = "≡ queue";
        dom.pbModeBadge.className = "pb-mode-badge queue";
        dom.btnRepeat.style.display = "inline-flex";
        if (dom.btnShuffle) dom.btnShuffle.style.display = "inline-flex";
    }

    if (dom.btnRepeat) {
        if (store.loop_mode === "track") {
            dom.btnRepeat.innerHTML = '<i class="ti ti-repeat-once" aria-hidden="true"></i>';
            dom.btnRepeat.classList.add("active");
        } else if (store.loop_mode === "queue") {
            dom.btnRepeat.innerHTML = '<i class="ti ti-repeat" aria-hidden="true"></i>';
            dom.btnRepeat.classList.add("active");
        } else {
            dom.btnRepeat.innerHTML = '<i class="ti ti-repeat" aria-hidden="true"></i>';
            dom.btnRepeat.classList.remove("active");
        }
    }

    if (dom.pbVolLabel) dom.pbVolLabel.textContent = store.volume + "%";
    if (dom.volSlider && !globalThis.isDraggingVol) dom.volSlider.value = store.volume;

    if (t && t.local_path) {
        dom.pbCacheBadge.textContent = "✓ tersimpan";
        dom.pbCacheBadge.className = "pb-badge-sm cached";
        dom.pbCacheBadge.style.display = "inline-block";
    } else if (t) {
        dom.pbCacheBadge.textContent = "☁ stream";
        dom.pbCacheBadge.className = "pb-badge-sm stream";
        dom.pbCacheBadge.style.display = "inline-block";
    } else {
        dom.pbCacheBadge.textContent = "";
        dom.pbCacheBadge.style.display = "none";
    }

    dom.pbSbBadge.textContent = store.sponsorblock_active ? "SB: ON" : "";
    dom.pbSbBadge.style.display = store.sponsorblock_active ? "inline-block" : "none";

    if (store.download_progress != null) {
        dom.pbDlBadge.textContent = "⬇ " + Math.round(store.download_progress * 100) + "%";
        dom.pbDlBadge.style.display = "inline-block";
    } else {
        dom.pbDlBadge.textContent = "";
        dom.pbDlBadge.style.display = "none";
    }
}

export function renderPlayBtn() {
    if (store.status === "PLAYING") {
        dom.btnPlay.innerHTML = '<svg viewBox="0 0 24 24" width="28" height="28" fill="#fff"><path d="M14,19H18V5H14M6,19H10V5H6V19Z"></path></svg>';
        if (typeof startProgressClock === "function") startProgressClock();
    } else {
        dom.btnPlay.innerHTML = '<svg viewBox="0 0 24 24" width="28" height="28" fill="#fff"><path d="M8,5.14V19.14L19,12.14L8,5.14Z"></path></svg>';
        if (typeof stopProgressClock === "function") stopProgressClock();
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// SMOOTH PROGRESS CLOCK (biar semulus Spotify/YouTube Music)
//
// Sebelumnya progress bar cuma digambar ulang PAS ada event baru: "timeupdate"
// dari <audio> browser (~4x/detik, gak selalu rapi jaraknya) atau pesan
// "progress" dari server (~1x/detik). Karena dua sumber ini gak pernah
// nge-tick bebarengan & gak sama presisinya, tampilannya "patah-patah" dan
// kadang kerasa balapan/gontai — sebentar diem, sebentar loncat — beda jauh
// dari Spotify/YouTube Music yang progress bar-nya gerak mulus tiap frame.
//
// Fix: bar gak lagi digambar langsung dari event. Event2 itu (timeupdate,
// progress server, seek) sekarang cuma nge-update SATU "anchor" (posisi
// diketahui + kapan itu diketahui, pakai performance.now()). Lalu ada satu
// loop requestAnimationFrame yang jalan terus (~60fps) yang GAMBAR posisi
// hasil interpolasi dari anchor itu: anchor.value + waktu yang berlalu sejak
// anchor di-set. Hasilnya gerakan progress bar mulus terus-menerus, gak
// peduli event sumbernya jarang/gak rata — sama seperti cara Spotify bikin
// progress bar mulus walau posisi asli cuma di-refresh sesekali dari server.
// ─────────────────────────────────────────────────────────────────────────────
let _posAnchorValue = 0;
let _posAnchorTime = 0;
let _progressRafId = null;
// PERF-01: detik terakhir yang sudah ditulis ke DOM teks (pbTimePos/pbTimeDur).
// Dipakai buat skip document write kalau detiknya belum berubah (lihat
// _renderProgressCore). null artinya "belum pernah ditulis" -> paksa tulis
// sekali di kesempatan berikutnya (aman dipakai setelah ganti lagu/seek
// karena posisi baru hampir selalu beda detik dari yang lama; kalaupun sama
// persis, teks yang ditampilkan memang sama jadi tidak ada bug terlihat).
let _lastRenderedSec = null;

export function setPositionAnchor(value) {
    _posAnchorValue = Math.max(0, value || 0);
    _posAnchorTime = performance.now();
    store.position = _posAnchorValue;
    _lastRenderedSec = null;
}

// FIX-POSITION-DRIFT-06: dipanggil setiap kali status BERUBAH jadi "PLAYING"
// (klik play, atau notifikasi dari client lain kalau admin lain yang resume).
// Cuma reset _posAnchorTime ke "sekarang" — nilai posisinya TETAP yang
// terakhir diketahui. Kalau ini gak dipanggil, interpolasi rAF ikut
// menghitung elapsed dari kapan anchor terakhir di-set (yaitu SAAT PAUSE
// tadi), sehingga durasi jeda nunggu sebelum nekan play ikut ke-hitung
// sebagai "waktu berjalan" -> angka loncat maju jauh (mis. 41+jeda=45),
// baru ketarik balik begitu timeupdate asli dari audio browser masuk.
// Reset ini bikin interpolasi mulai dari 0 elapsed persis saat play beneran
// ditekan/diketahui, jadi gak ada lompatan maju-mundur itu lagi.
export function resetAnchorClock() {
    _posAnchorTime = performance.now();
}

export function getInterpolatedPosition() {
    if (store.status !== "PLAYING") return _posAnchorValue;
    if (store.audio_output === "browser" && globalThis.audioBlocked) return _posAnchorValue;
    const dur = store.current_track ? store.current_track.duration : 0;
    const elapsed = (performance.now() - _posAnchorTime) / 1000;
    const pos = _posAnchorValue + elapsed;
    return dur > 0 ? Math.min(pos, dur) : pos;
}

export function startProgressClock() {
    if (_progressRafId) return;
    function tick() {
        _progressRafId = requestAnimationFrame(tick);
        if (globalThis.isDraggingPb) return;
        _renderProgressCore(getInterpolatedPosition());
    }
    _progressRafId = requestAnimationFrame(tick);
}

export function stopProgressClock() {
    if (_progressRafId) {
        cancelAnimationFrame(_progressRafId);
        _progressRafId = null;
    }
}

export function renderProgress() {
    // Dipanggil dari event (timeupdate, progress, seek, dll) yang sudah
    // mengupdate anchor lewat setPositionAnchor(). Loop rAF di atas yang
    // pegang penggambaran tiap frame; ini cuma jaga-jaga gambar sekali
    // langsung (misal pas status bukan PLAYING, di mana loop tetap jalan
    // tapi nilainya statis) supaya gak nunggu frame berikutnya.
    if (globalThis.isDraggingPb) return;
    _renderProgressCore(getInterpolatedPosition());
}

function _renderProgressCore(posOverride) {
    if (globalThis.isDraggingPb) return;
    const dur = store.current_track ? store.current_track.duration : 0;
    const pos = posOverride != null ? posOverride : (store.position || 0);
    const pct = dur > 0 ? Math.min(100, (pos / dur) * 100) : 0;

    dom.pbProgressFill.style.width = pct + "%";

    // update thumb (PERF-01: pakai referensi yang di-cache di dom.js, bukan
    // querySelector ulang tiap frame — elemennya statis, gak pernah diganti)
    if (dom.pbThumb) dom.pbThumb.style.left = pct + "%";

    // PERF-01: teks waktu presisinya detik, jadi gak perlu ditulis ulang ke
    // DOM 60x/detik untuk nilai yang sama persis. Cuma tulis kalau detiknya
    // (dibulatkan ke bawah) berubah dari yang terakhir ditampilkan.
    const _sec = Math.floor(pos);
    if (_sec !== _lastRenderedSec) {
        _lastRenderedSec = _sec;
        dom.pbTimePos.textContent = formatTime(pos);
        dom.pbTimeDur.textContent = formatTime(dur);
    }

    if (store.audio_output === "browser" && typeof getOrInitAudio === "function") {
        const _audioEl = getOrInitAudio();
        if (_audioEl) {
            if (!globalThis.isDraggingVol && typeof _fadeIntervals !== "undefined" && !_fadeIntervals[activeAudioIndex]) {
                _audioEl.volume = Math.max(0, Math.min(1, store.volume / 100));
            }
        }
    }

    // S8-08 Mini Player Progress (PERF-01: pakai dom.playerBarEl yang di-cache)
    if (dom.playerBarEl) dom.playerBarEl.style.setProperty("--mini-progress", pct + "%");
}

export function initPlayerBusSubscriptions() {
    on("player:btn-changed", renderPlayBtn);
    on("player:bar-changed", renderPlayerBar);
    on("player:clock-reset", resetAnchorClock);
    on("player:clock-start", startProgressClock);
    on("player:clock-stop", stopProgressClock);
    on("player:position", (pos) => setPositionAnchor(pos));
    on("player:progress", renderProgress);
}
