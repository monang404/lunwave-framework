import { emit as bus } from "../../bus.js";
import { dom } from "../../dom.js";
import { store } from "/framework/static/js/core/store.js";
import { wsSend } from "/framework/static/js/core/transport.js";

export function handleAuthMessage(msg) {
    switch (msg.type) {
        case "auth_status":
            if (dom.adminSubmitBtn) {
                dom.adminSubmitBtn.disabled = false;
                dom.adminSubmitBtn.textContent = "Login Admin";
            }
            if (msg.data.success) {
                store.userRole = "admin";
                globalThis.safeStorage.set("lunawave_user_role", "admin");
                if (msg.data && msg.data.token) {
                    globalThis.safeStorage.set("lunawave_session_token", msg.data.token);
                }
                globalThis.safeStorage.remove("lunawave_admin_password");
                dom.loginErrorMsg.textContent = "";
                dom.portalLoginForm.classList.add("hidden");
                bus("auth:role-changed");
                bus("toast:log", { message: "Akses Admin Diterima!" });
                if (store.active_tab === "home" || store.active_tab === "discover") {
                    bus("toast:log", { message: "Meminta data lagu..." });
                    wsSend("discover");
                }
                bus("state:full-render");
            } else {
                dom.loginErrorMsg.textContent = msg.data.message || "Login gagal.";
                if (store.userRole === "admin") {
                    bus("auth:logout");
                }
            }
            break;
        case "setup_status":
            if (dom.setupSubmitBtn) {
                dom.setupSubmitBtn.disabled = false;
                dom.setupSubmitBtn.textContent = "Buat Akun Admin";
            }
            if (msg.data.success) {
                if (dom.setupErrorMsg) dom.setupErrorMsg.textContent = "";
                if (dom.setupConfirmErrorMsg) dom.setupConfirmErrorMsg.textContent = "";
                bus("toast:log", { message: "Akun admin berhasil dibuat! Silakan login." });
                if (dom.setupScreen) dom.setupScreen.classList.remove("portal-active");
                if (dom.portalScreen) dom.portalScreen.classList.add("portal-active");
                if (dom.adminUsername) dom.adminUsername.value = "";
            } else if (dom.setupErrorMsg) {
                dom.setupErrorMsg.textContent = msg.data.message || "Gagal membuat akun admin.";
            }
            break;
    }
}

export function renderHeader() {
    if (store.is_online) {
        dom.statusDot.classList.remove("offline");
        dom.statusText.textContent = "online";
    } else {
        dom.statusDot.classList.add("offline");
        dom.statusText.textContent = "offline";
    }

    const out = store.audio_output || "browser";
    if (out === "browser") {
        dom.outputToggleBtn.textContent = "💻 BROWSER";
        dom.outputToggleBtn.classList.add("browser");
    } else {
        dom.outputToggleBtn.textContent = "📱 HP";
        dom.outputToggleBtn.classList.remove("browser");
    }
}
