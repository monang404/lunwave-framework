import { on } from "../bus.js";
import { dom } from "../dom.js";
import { setRadioHeroAnimState } from "./radio-hero-moon.js";
import { store } from "/framework/static/js/core/store.js";

export function renderRadio() {
    const isRadio = store.playback_mode === 'RADIO';

    if (dom.radioToggleBtn) {
        if (isRadio) {
            dom.radioToggleBtn.classList.add("on");
            dom.radioToggleBtn.classList.remove("off");
            dom.radioToggleBtn.dataset.on = "true";
        } else {
            dom.radioToggleBtn.classList.add("off");
            dom.radioToggleBtn.classList.remove("on");
            dom.radioToggleBtn.dataset.on = "false";
        }
        dom.radioToggleBtn.setAttribute('aria-pressed', isRadio ? 'true' : 'false');
    }

    if (dom.rtSub) {
        if (isRadio) {
            if (store.status === "LOADING") {
                dom.rtSub.textContent = "Mencari stasiun...";
            } else {
                dom.rtSub.textContent = "24/7 Nonstop Music";
            }
        } else {
            dom.rtSub.textContent = "Aktifkan untuk putar otomatis";
        }
    }

    // NEW — hook satu arah ke modul animasi hero, hanya kirim boolean,
    // tidak ada state lain yang dibagi (RFC §5.3)
    if (typeof setRadioHeroAnimState === 'function') {
        setRadioHeroAnimState(isRadio);
    }
}

export function initRadioTabBusSubscriptions() {
    on("radio:changed", renderRadio);
}
