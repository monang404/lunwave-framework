import { dom } from "./dom.js";
import { applyRoleUI } from "./services/auth.js";
import { store } from "/framework/static/js/core/store.js";

export function initPortal() {
    const role = globalThis.safeStorage ? globalThis.safeStorage.get("lunawave_user_role") : localStorage.getItem("lunawave_user_role");
    if (role && role !== "client") {
        store.userRole = role;
    } else {
        store.userRole = "portal";
    }
    applyRoleUI();
}

// T-B11.1/T-B11.2: cek GET /api/setup-required SEBELUM memutuskan tampilkan
// #setup-screen atau alur login normal (#portal-screen) -- sengaja TIDAK
// ditebak murni client (mis. dari localStorage lunawave_user_role), karena
// localStorage bisa saja masih menyimpan role lama dari instalasi
// sebelumnya padahal admin_account sudah kosong (upgrade dari instalasi
// lama tanpa migrasi otomatis, lihat K3). #portal-screen sudah class
// "portal-active" bawaan HTML (T-B9 tidak mengubah ini) supaya tetap benar
// kalau JS gagal total -- di sini kita lepas dulu classnya sebelum fetch
// selesai, baru diputuskan ulang berdasar jawaban server, bukan ditebak.
export async function initSetupCheck() {
    if (dom.portalScreen) dom.portalScreen.classList.remove("portal-active");

    let setupRequired = false;
    try {
        const res = await fetch("/api/setup-required");
        if (res.ok) {
            const data = await res.json();
            setupRequired = !!data.setup_required;
        } else {
            console.warn("Cek /api/setup-required gagal (status " + res.status + "), fallback ke alur login normal.");
        }
    } catch (e) {
        console.warn("Cek /api/setup-required gagal (network), fallback ke alur login normal:", e);
    }

    if (setupRequired) {
        // Instalasi baru, admin_account belum ada -> Initial Setup.
        if (dom.setupScreen) dom.setupScreen.classList.add("portal-active");
    } else {
        // Instalasi existing (atau fetch gagal -- fail open ke alur lama
        // supaya user existing tidak pernah terkunci gara-gara check ini
        // sendiri yang gagal) -> langsung Login seperti sebelumnya.
        if (dom.setupScreen) dom.setupScreen.classList.remove("portal-active");
        initPortal();
    }
}
