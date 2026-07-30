import { store } from "/framework/static/js/core/store.js";
import { wsSend } from "../ws.js";

(function() {
    // Hanya aktif di desktop (pointer: fine = mouse)
    if (globalThis.matchMedia('(pointer: fine)').matches) {
        document.addEventListener('keydown', (e) => {
            // Jangan intercept saat user mengetik di input
            const target = /** @type {Element} */ (e.target);
            if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

            // NOTE: 'Space' sengaja tidak ditangani di sini -- sudah ditangani secara
            // global (admin-gated) oleh events/keyboard-shortcut-events.js. Menangani
            // Space di sini juga akan jadi duplicate listener untuk tombol yang sama.
            switch (e.code) {
                case 'ArrowRight':
                    if (store.userRole !== 'admin') return;
                    e.preventDefault();
                    if (typeof wsSend === 'function') wsSend('next');
                    break;
                case 'ArrowLeft':
                    if (store.userRole !== 'admin') return;
                    e.preventDefault();
                    if (typeof wsSend === 'function') wsSend('prev');
                    break;
            }
        });
    }
})();
