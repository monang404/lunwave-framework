import { on } from "../bus.js";
import { dom } from "../dom.js";
import { store } from "/framework/static/js/core/store.js";
import { escapeHtml, formatDurationLong, formatTime } from "../utils/format.js";
import { cleanTrackTitle } from "../utils/cover-art.js";

export function renderQueue() {
    if (globalThis.isDraggingQueue) return;
    document.body.dataset.queueEmpty = (store.queue.length === 0) ? "true" : "false";
    const isRadio = store.playback_mode === "RADIO";

    // Render the manual queue in Queue Tab
    renderList(dom.queueList, store.queue, false, store.playback_mode === "QUEUE");

    // Render the radio queue in Radio Tab
    if (dom.radioQueueList) {
        renderList(dom.radioQueueList, store.radio_queue, true, isRadio);
    }

    let totalDur = 0;
    store.queue.forEach(t => {
        if (t && t.duration) totalDur += t.duration;
    });

    const queueCount = store.queue.length;
    const modeStr = isRadio
        ? '<span style="color:var(--fm-green)">RADIO</span>'
        : '<span style="color:var(--fm-text-5)">QUEUE</span>' + (queueCount > 0 ? ` &bull; ${queueCount} lagu (${typeof formatDurationLong === 'function' ? formatDurationLong(totalDur) : formatTime(totalDur)})` : '');
    if (dom.queueFooter) {
        dom.queueFooter.innerHTML = "Mode: " + modeStr;
    }
}


function renderList(container, items, isRadioList, isCurrentActiveMode) {
    if (!container) return;

    const allItems = [];
    if (isCurrentActiveMode && store.current_track) {
        allItems.push({ track: store.current_track, index: -1, isCurrent: true });
    }
    items.forEach((track, i) => allItems.push({ track, index: i, isCurrent: false }));

    if (allItems.length === 0) {
        container.innerHTML = '<div class="queue-empty">' + (isRadioList ? "Tekan 'Acak Ulang' untuk memulai radio" : "Cari lagu atau putar dari Discover") + '</div>';
    } else {
        const existing = Array.from(container.children);
        if (existing.length === 1 && existing[0].classList.contains('queue-empty')) {
            existing[0].remove();
            existing.shift();
        }

        allItems.forEach((item, i) => {
            let el = existing[i];
            if (!el) {
                el = createQueueItemTemplate(isRadioList);
                container.appendChild(el);
            }
            updateQueueItem(el, item.track, item.index, item.isCurrent, isRadioList);
        });

        while (container.children.length > allItems.length) {
            container.removeChild(container.lastChild);
        }

        if (isRadioList && typeof globalThis.loadLazyCovers === "function") {
            globalThis.loadLazyCovers();
        }
    }
}


function createQueueItemTemplate(isRadio) {
    const div = document.createElement("div");
    if (isRadio) {
        div.className = "radio-queue-item";
        div.innerHTML = `
            <div class="radio-queue-thumb">
                <img class="lazy-cover" src="" alt="">
                <div class="thumb-eq-overlay">
                    <div class="eq-anim-icon">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            </div>
            <div class="radio-queue-info">
                <div class="radio-queue-title"></div>
                <div class="radio-queue-artist"></div>
            </div>
        `;
    } else {
        div.className = "queue-item";
        div.innerHTML = `
            <span class="qi-drag">⋮⋮</span>
            <span class="qi-index"></span>
            <div class="qi-info">
                <div class="qi-title"></div>
                <div class="qi-dur"></div>
            </div>
            <button class="qi-remove">✕</button>
        `;
    }
    return div;
}


function updateQueueItem(div, track, index, isCurrent, isRadio) {
    if (isRadio) {
        div.className = "radio-queue-item" + (isCurrent ? " current" : "") + (isCurrent && store.status === "PLAYING" ? " playing" : "");
        div.dataset.vid = track.video_id || '';

        const titleEl = div.querySelector(".radio-queue-title");
        const artistEl = div.querySelector(".radio-queue-artist");

        const title = typeof cleanTrackTitle === "function" ? escapeHtml(cleanTrackTitle(track.title)) : escapeHtml(track.title);
        if (titleEl) titleEl.textContent = title;
        if (artistEl) artistEl.textContent = (track.artist || '') + " · " + formatTime(track.duration);

        const img = div.querySelector(".lazy-cover");
        if (img) {
            // Only update datasets and reset cover if track changed to avoid disappear/flicker bug
            if (img.dataset.vid !== (track.video_id || '')) {
                img.dataset.vid = track.video_id || '';
                img.dataset.title = track.title || '';
                img.dataset.artist = track.artist || '';
                img.dataset.thumb = track.thumbnail || '';
                img.src = '';
                img.classList.remove('loaded');
                img.classList.remove('observed');
            }
        }
    } else {
        div.className = "queue-item" + (isCurrent ? " current" : "");
        if (!isCurrent) {
            div.dataset.index = index;
        } else {
            div.removeAttribute("data-index");
        }

        if (isCurrent) {
            if (store.status === "PLAYING") {
                div.querySelector(".qi-index").innerHTML = `<div class="eq-anim-icon" style="height:12px; width:14px; gap:2px;"><span style="width:3px; background: currentColor;"></span><span style="width:3px; background: currentColor;"></span><span style="width:3px; background: currentColor;"></span></div>`;
            } else {
                div.querySelector(".qi-index").textContent = "▶";
            }
        } else {
            div.querySelector(".qi-index").textContent = index + 1;
        }
        div.querySelector(".qi-title").textContent = track.title;
        div.querySelector(".qi-dur").textContent = track.artist + " · " + formatTime(track.duration);

        const rmBtn = div.querySelector(".qi-remove");
        const dragHandle = div.querySelector(".qi-drag");
        if (isCurrent) {
            rmBtn.style.display = "none";
            if (dragHandle) dragHandle.style.display = "none";
        } else {
            rmBtn.style.display = "block";
            rmBtn.dataset.index = index;
            if (dragHandle) dragHandle.style.display = "";
        }
    }
}

export function initQueueBusSubscriptions() {
    on("queue:changed", renderQueue);
}
