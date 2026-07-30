import { getOrInitAudio, unlockBrowserAudio } from "../audio/playback-sync.js";
import { on } from "../bus.js";
import { dom } from "../dom.js";
import { switchTab } from "../render/navigation.js";
import { store } from "/framework/static/js/core/store.js";
import { wsSend } from "../ws.js";

function openSettings() {
    if (dom.settingsSheet) dom.settingsSheet.classList.add("open");
    if (dom.mainOverlay) dom.mainOverlay.classList.add("open");
    if (typeof renderSettingsSheet === "function") renderSettingsSheet();
    wsSend("get_cache_size", {});
}

export function closeSettings() {
    if (dom.settingsSheet) dom.settingsSheet.classList.remove("open");
    if (typeof closeMainOverlay === "function") closeMainOverlay();
}

export function renderSettingsSheet() {
    if (!dom.settingsSheet || !dom.settingsSheet.classList.contains("open")) return;
    if (dom.sbToggle) dom.sbToggle.dataset.on = store.sponsorblock_active ? "true" : "false";
    if (dom.crossfadeToggle) dom.crossfadeToggle.dataset.on = store.crossfade_enabled ? "true" : "false";
    if (dom.loudnessToggle) dom.loudnessToggle.dataset.on = store.loudness_normalization_enabled ? "true" : "false";
    // Sync speed dropdown ke nilai state saat ini
    if (dom.ssSpeedSelect && store.playback_speed) {
        dom.ssSpeedSelect.value = store.playback_speed.toFixed(2);
        if (dom.ssSpeedSub) dom.ssSpeedSub.textContent = store.playback_speed.toFixed(2) + "x";
    }
    if (dom.ssOutSub && dom.ssOutBtn) {
        if (store.audio_output === "browser") {
            dom.ssOutSub.textContent = "Keluar via browser ini";
            dom.ssOutBtn.textContent = "💻 Browser";
        } else {
            dom.ssOutSub.textContent = "Keluar via perangkat (mpv)";
            dom.ssOutBtn.textContent = "📱 Device";
        }
    }
    if (dom.ssDlRow) {
        if (store.download_progress != null) {
            dom.ssDlRow.style.display = "flex";
            const pct = Math.round(store.download_progress * 100);
            if (dom.ssDlPct) dom.ssDlPct.textContent = pct + "%";
            if (dom.ssDlFill) dom.ssDlFill.style.width = pct + "%";
            if (dom.ssDlTrack && store.current_track) {
                dom.ssDlTrack.textContent = store.current_track.title;
            }
        } else {
            dom.ssDlRow.style.display = "none";
        }
    }
    if (dom.ssHistorySub) {
        dom.ssHistorySub.textContent = (store.history_count || 0) + " lagu diputar";
    }
}

export function closeMainOverlay() {
    if (dom.mainOverlay) dom.mainOverlay.classList.remove("open");
    if (dom.settingsSheet) dom.settingsSheet.classList.remove("open");
    if (dom.actionSheet) dom.actionSheet.classList.remove("open");
    if (dom.helpSheet) dom.helpSheet.classList.remove("open");
    if (dom.artistDetailSheet) dom.artistDetailSheet.classList.remove("open");
}

export function initSettingsEvents() {
    if (dom.btnSettings) {
        dom.btnSettings.addEventListener("click", () => {
            if (dom.settingsSheet && dom.settingsSheet.classList.contains("open")) {
                closeSettings();
            } else {
                openSettings();
            }
        });
    }

    if (dom.mainOverlay) {
        dom.mainOverlay.addEventListener("click", closeMainOverlay);
    }

    if (dom.sbToggle) {
        dom.sbToggle.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            const newVal = dom.sbToggle.dataset.on !== "true";
            dom.sbToggle.dataset.on = newVal ? "true" : "false";
            store.sponsorblock_active = newVal;
            wsSend("set_sponsorblock", { enabled: newVal });
        });
    }

    if (dom.ssOutBtn) {
        dom.ssOutBtn.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            const newOutput = store.audio_output === "browser" ? "device" : "browser";
            if (newOutput === "browser" && typeof unlockBrowserAudio === "function") unlockBrowserAudio();
            wsSend("set_output", { output: newOutput });
            closeSettings();
        });
    }

    if (dom.crossfadeToggle) {
        dom.crossfadeToggle.addEventListener('click', () => {
            if (store.userRole !== 'admin') return;
            const current = store.crossfade_enabled;
            wsSend("set_crossfade", { enabled: !current });
        });
    }

    if (dom.loudnessToggle) {
        dom.loudnessToggle.addEventListener('click', () => {
            if (store.userRole !== 'admin') return;
            const current = store.loudness_normalization_enabled;
            wsSend("set_loudness_normalization", { enabled: !current });
        });
    }

    if (dom.ssStopBtn) {
        dom.ssStopBtn.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            wsSend("stop");
            closeSettings();
        });
    }

    if (dom.ssDlCancelBtn) {
        dom.ssDlCancelBtn.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            wsSend("cancel_download");
        });
    }

    if (dom.ssHistoryBtn) {
        dom.ssHistoryBtn.addEventListener('click', () => {
            closeSettings();
            if (typeof switchTab === "function") switchTab('discover');
            wsSend('discover', {});
            setTimeout(() => {
                if (dom.discRecent) {
                    dom.discRecent.scrollIntoView({ behavior: 'smooth' });
                }
            }, 300);
        });
    }

    if (dom.ssCacheClearBtn) {
        dom.ssCacheClearBtn.addEventListener("click", () => {
            if (store.userRole !== "admin") return;
            if (confirm("Bersihkan cache MP3 sementara? (Track yang diunduh manual tidak akan dihapus)")) {
                if (dom.ssCacheSub) dom.ssCacheSub.textContent = "Membersihkan...";
                wsSend("clear_cache", {});
            }
        });
    }

    // PATCH-UI-PERF-01: tombol reset manual untuk Service Worker + Cache
    // Storage browser (beda dari "Ukuran Cache" di atas, yang itu untuk
    // cache MP3 di server). Ini yang dipakai kalau tampilan/aset kelihatan
    // "nyangkut" di versi lama setelah SW aktif -- tidak perlu buka DevTools
    // atau uninstall browser, cukup tap tombol ini lalu app reload sendiri.
    if (dom.ssSwResetBtn) {
        dom.ssSwResetBtn.addEventListener("click", async () => {
            if (!confirm("Reset tampilan offline? App akan reload setelah ini.")) return;
            dom.ssSwResetBtn.disabled = true;
            dom.ssSwResetBtn.textContent = "...";
            try {
                if ("serviceWorker" in navigator) {
                    const regs = await navigator.serviceWorker.getRegistrations();
                    await Promise.all(regs.map((r) => r.unregister()));
                }
                if ("caches" in window) {
                    const keys = await caches.keys();
                    await Promise.all(keys.map((k) => caches.delete(k)));
                }
            } catch (e) {
                console.warn("[settings] SW/cache reset gagal:", e);
            } finally {
                location.reload();
            }
        });
    }

    if (dom.ssSleepSelect) {
        let _sleepCountdownInterval = null;

        function startSleepCountdown(minutes) {
            if (_sleepCountdownInterval) clearInterval(_sleepCountdownInterval);
            if (minutes <= 0) {
                if (dom.ssSleepSub) dom.ssSleepSub.textContent = "Mati";
                return;
            }
            let remaining = minutes * 60; // detik
            function tick() {
                if (remaining <= 0) {
                    clearInterval(_sleepCountdownInterval);
                    _sleepCountdownInterval = null;
                    if (dom.ssSleepSub) dom.ssSleepSub.textContent = "Mati";
                    if (dom.ssSleepSelect) dom.ssSleepSelect.value = "0";
                    return;
                }
                const m = Math.floor(remaining / 60);
                const s = remaining % 60;
                if (dom.ssSleepSub) dom.ssSleepSub.textContent = `${m}:${String(s).padStart(2,'0')} tersisa`;
                remaining--;
            }
            tick();
            _sleepCountdownInterval = setInterval(tick, 1000);
        }

        dom.ssSleepSelect.addEventListener("change", (e) => {
            if (store.userRole !== "admin") return;
            const minutes = parseInt(e.target.value);
            startSleepCountdown(minutes);
            wsSend("set_sleep_timer", { minutes });
        });
    }

    if (dom.ssSpeedSelect) {
        dom.ssSpeedSelect.addEventListener("change", (e) => {
            if (store.userRole !== "admin") return;
            const speed = parseFloat(e.target.value);
            store.playback_speed = speed;
            if (dom.ssSpeedSub) {
                dom.ssSpeedSub.textContent = speed.toFixed(2) + "x";
            }
            // Langsung apply ke browser audio tanpa tunggu round-trip server
            if (store.audio_output === "browser" && typeof getOrInitAudio === "function") {
                const audio = getOrInitAudio();
                if (audio) audio.playbackRate = speed;
            }
            wsSend("set_speed", { speed });
        });
    }

    if (dom.btnHelp) {
        dom.btnHelp.addEventListener("click", () => {
            if (dom.settingsSheet) dom.settingsSheet.classList.remove("open");
            if (dom.helpSheet) dom.helpSheet.classList.add("open");
            if (dom.mainOverlay) dom.mainOverlay.classList.add("open");
        });
    }

    if (dom.helpCloseBtn) {
        dom.helpCloseBtn.addEventListener("click", () => {
            if (dom.helpSheet) dom.helpSheet.classList.remove("open");
            closeMainOverlay();
        });
    }
}

export function initSettingsBusSubscriptions() {
    on("settings:sheet-changed", renderSettingsSheet);
    on("overlay:main-close", closeMainOverlay);
}
