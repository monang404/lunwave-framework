import { getOrInitAudio, resetLastLoadedVideoId } from "../audio/playback-sync.js";
import { emit, on } from "../bus.js";
import { dom } from "../dom.js";
import { switchTab } from "../render/navigation.js";
import { store } from "/framework/static/js/core/store.js";
import { renderHeader, wsSend } from "../ws.js";

export function applyRoleUI() {
    if (store.userRole === "portal") {
        dom.portalScreen.classList.add("portal-active");
        dom.appContainer.classList.add("portal-active");
        document.body.classList.remove("client-mode");
        dom.logoutBtn.style.display = "none";
    } else if (store.userRole === "client") {
        dom.portalScreen.classList.remove("portal-active");
        dom.appContainer.classList.remove("portal-active");
        document.body.classList.add("client-mode");
        switchTab("home");
        dom.logoutBtn.style.display = "flex";
    } else if (store.userRole === "admin") {
        dom.portalScreen.classList.remove("portal-active");
        dom.appContainer.classList.remove("portal-active");
        document.body.classList.remove("client-mode");
        dom.logoutBtn.style.display = "flex";
        switchTab("home");
        // FIX BUG-1: setelah #app visible, paksa recalculate tinggi viewport.
        // Android Chrome tidak auto-fire visualViewport resize saat element
        // berubah dari display:none ke display:flex, sehingga nav-bar bisa
        // terpotong sampai user scroll atau resize manual.
        // Hack visualViewport dihilangkan karena justru menyebabkan nav-bar hilang saat URL bar muncul/hilang.
        // CSS 100dvh sudah diperbaiki di app-shell.css untuk menangani ini secara native.
    }
    renderHeader();
}

export function submitSetup(user, pass, confirmPass) {
    if (!user || !pass) {
        dom.setupErrorMsg.textContent = "Isi username dan password!";
        return;
    }
    if (pass !== confirmPass) {
        // Jaring pengaman sisi client -- tombol submit seharusnya sudah
        // disabled duluan oleh updateSetupSubmitState() (events/index.js,
        // T-B12.1) saat password != confirm, tapi cek ini tetap ada untuk
        // jaga-jaga (mis. submit lewat Enter sebelum listener input sempat
        // jalan).
        dom.setupConfirmErrorMsg.textContent = "Password dan Confirm Password tidak sama.";
        return;
    }

    if (dom.setupSubmitBtn) {
        dom.setupSubmitBtn.disabled = true;
        dom.setupSubmitBtn.textContent = "Menyimpan...";
    }
    dom.setupErrorMsg.textContent = "";
    if (dom.setupConfirmErrorMsg) dom.setupConfirmErrorMsg.textContent = "";

    if (globalThis.ws && globalThis.ws.readyState === WebSocket.OPEN) {
        // T-B12.2: field confirm password TIDAK PERNAH dikirim ke server --
        // sesuai kontrak T-B5.1/_validate_setup_input di server/handlers/setup.py,
        // yang tidak pernah menerima/memvalidasi field ini sama sekali.
        // Match-check adalah tanggung jawab client sepenuhnya (di atas + T-B12.1).
        wsSend("setup_admin", { username: user, password: pass });
    } else {
        dom.setupErrorMsg.textContent = "Koneksi server terputus. Silakan tunggu/refresh.";
        if (dom.setupSubmitBtn) {
            dom.setupSubmitBtn.disabled = false;
            dom.setupSubmitBtn.textContent = "Buat Akun Admin";
        }
    }
}

export function login(user, pass) {
    if (!user || !pass) {
        dom.loginErrorMsg.textContent = "Isi username dan password!";
        return;
    }

    if (dom.adminSubmitBtn) {
        dom.adminSubmitBtn.disabled = true;
        dom.adminSubmitBtn.textContent = "Menghubungkan...";
    }
    dom.loginErrorMsg.textContent = "";

    store.adminUsername = user;
    store.adminPassword = pass;

    if (globalThis.ws && globalThis.ws.readyState === WebSocket.OPEN) {
        wsSend("auth", { username: user, password: pass });
    } else {
        dom.loginErrorMsg.textContent = "Koneksi server terputus. Silakan tunggu/refresh.";
        if (dom.adminSubmitBtn) {
            dom.adminSubmitBtn.disabled = false;
            dom.adminSubmitBtn.textContent = "Login Admin";
        }
    }
}

export function logout() {
    // 1. Stop local browser/client audio
    const localAudio = getOrInitAudio();
    if (localAudio) {
        try {
            localAudio.pause();
            localAudio.src = "";
            localAudio.removeAttribute("src");
            localAudio.load();
        } catch (e) {
            console.warn("Failed to stop browser audio:", e);
        }
    }
    resetLastLoadedVideoId();

    // 2. Stop server playback if admin
    if (store.userRole === "admin") {
        try {
            wsSend("stop");
        } catch (e) {
            console.warn("Failed to send stop command:", e);
        }
    }

    // 3. Clear store & local storage
    store.userRole = "portal";
    store.adminUsername = "";
    store.adminPassword = "";

    // Kirim pesan logout ke server untuk invalidate session
    const token = globalThis.safeStorage.get("lunawave_session_token");
    if (token) {
        try {
            wsSend("logout", { token: token });
        } catch (e) {
            console.warn("Failed to send logout command:", e);
        }
    }

    globalThis.safeStorage.remove("lunawave_user_role");
    globalThis.safeStorage.remove("lunawave_admin_username");
    globalThis.safeStorage.remove("lunawave_admin_password");
    globalThis.safeStorage.remove("lunawave_session_token");

    // 4. Close settings sheet UI if open
    emit("overlay:main-close");

    // 5. Redirect or adjust view
    if (globalThis.location.pathname !== "/admin") {
        setTimeout(() => {
            if (globalThis.ws) {
                try {
                    globalThis.ws.close();
                } catch { /* best-effort, aman diabaikan */ }
            }
            globalThis.location.href = "/admin";
        }, 150);
    } else {
        applyRoleUI();
        if (globalThis.ws) {
            try {
                globalThis.ws.close();
            } catch { /* best-effort, aman diabaikan */ }
        }
    }
}

export function initAuthBusSubscriptions() {
    on("auth:role-changed", applyRoleUI);
    on("auth:logout", logout);
}
