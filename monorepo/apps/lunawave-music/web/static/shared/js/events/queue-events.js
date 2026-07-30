import { unlockBrowserAudio } from "../audio/playback-sync.js";
import { dom } from "../dom.js";
import { store } from "/framework/static/js/core/store.js";
import { wsSend } from "../ws.js";

let _dragSrcIndex = null;
let _dragEl = null;
globalThis.isDraggingQueue = false;

export function initQueueDragDrop() {
    const list = dom.queueList;
    if (!list) return;

    list.addEventListener('pointerdown', _onDragStart, { passive: false });
    document.addEventListener('pointermove', _onDragMove, { passive: false });
    document.addEventListener('pointerup', _onDragEnd);
    document.addEventListener('pointercancel', _onDragCancel);
}

function _onDragStart(e) {
    if (store.userRole !== 'admin') return;
    const handle = e.target.closest('.qi-drag');
    if (!handle) return;

    const item = handle.closest('.queue-item');
    if (!item || !item.hasAttribute('data-index')) return;

    e.preventDefault();
    _dragSrcIndex = parseInt(item.dataset.index);
    _dragEl = item;
    globalThis.isDraggingQueue = true;
    item.classList.add('dragging');
    item.setPointerCapture(e.pointerId);
}

function _onDragMove(e) {
    if (_dragSrcIndex === null || !_dragEl) return;
    e.preventDefault();

    document.querySelectorAll('.queue-item.drag-over').forEach(el => el.classList.remove('drag-over'));

    const target = document.elementFromPoint(e.clientX, e.clientY);
    if (target) {
        const over = target.closest('.queue-item[data-index]');
        if (over && over !== _dragEl) {
            over.classList.add('drag-over');
        }
    }
}

function _onDragEnd(e) {
    if (_dragSrcIndex === null) return;

    const target = document.elementFromPoint(e.clientX, e.clientY);
    if (target) {
        const over = /** @type {HTMLElement | null} */ (target.closest('.queue-item[data-index]'));
        if (over && over !== _dragEl) {
            const toIndex = parseInt(over.dataset.index);
            if (toIndex !== _dragSrcIndex) {
                wsSend('queue_reorder', { from_index: _dragSrcIndex, to_index: toIndex });
            }
        }
    }
    _cleanupDrag();
}

function _onDragCancel() {
    _cleanupDrag();
}

function _cleanupDrag() {
    if (_dragEl) _dragEl.classList.remove('dragging');
    document.querySelectorAll('.queue-item.drag-over').forEach(el => el.classList.remove('drag-over'));
    _dragSrcIndex = null;
    _dragEl = null;
    globalThis.isDraggingQueue = false;
}

export function initQueueEvents() {
    if (dom.queueList) {
        dom.queueList.addEventListener("click", (e) => {
            if (store.userRole !== "admin") return;
            const rmBtn = e.target.closest(".qi-remove");
            if (rmBtn) {
                e.stopPropagation();
                wsSend("queue_remove", { index: parseInt(rmBtn.dataset.index) });
                return;
            }
            if (e.target.closest(".qi-drag")) return;
            const item = e.target.closest(".queue-item[data-index]");
            if (item) {
                if (store.audio_output === "browser" && typeof unlockBrowserAudio === "function") {
                    unlockBrowserAudio(true);
                }
                wsSend("queue_select", { index: parseInt(item.dataset.index) });
            }
        });
    }
}

export const isDraggingQueue = globalThis.isDraggingQueue;
