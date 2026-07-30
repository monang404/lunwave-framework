import { sendOverWs } from "/framework/static/js/core/transport.js";

let activeChatUid = null;
let unreadCounts = {};
const dashChatPanel = document.getElementById('dash-chat-panel');
const dashChatClose = document.getElementById('dash-chat-close-btn');
const dashChatMessages = document.getElementById('dash-chat-messages');
const dashChatForm = document.getElementById('dash-chat-form');
const dashChatInput = /** @type {HTMLInputElement} */ (document.getElementById('dash-chat-input'));
const dashChatTargetIp = document.getElementById('dash-chat-target-ip');

export function updateBadge(uid) {
    const badge = document.getElementById(`badge-${uid}`);
    if (!badge) return;
    const count = unreadCounts[uid] || 0;
    if (count > 0) {
        badge.style.display = 'flex';
        badge.textContent = count > 9 ? '9+' : count;
        // Make the button highlighted
        badge.parentElement.style.color = 'var(--accent)';
        badge.parentElement.style.borderColor = 'var(--accent)';
    } else {
        badge.style.display = 'none';
        badge.parentElement.style.color = 'var(--text-2)';
        badge.parentElement.style.borderColor = 'var(--border-2)';
    }
}
export function openChatPanel(uid, ip) {
    dashChatPanel.classList.add('active');

    if (!uid) {
        // client_uid belum terdaftar di server -- biasanya cuma sesaat
        // (client.js kirim client_uid otomatis begitu WS connect, lihat
        // catatan di renderActiveUsers). Tetap buka panel supaya admin
        // tidak "menunggu client chat duluan", tapi jangan pura-pura
        // punya thread yang bisa dikirimi pesan.
        activeChatUid = null;
        dashChatTargetIp.textContent = (ip ? `${ip} — ` : "") + "menunggu koneksi chat client...";
        dashChatMessages.innerHTML = '<div style="text-align:center; color:var(--text-3); font-size:12px; padding:var(--s4);">Client ini belum terdaftar untuk chat. Coba lagi beberapa detik lagi setelah client selesai memuat halaman.</div>';
        return;
    }

    activeChatUid = uid;
    dashChatTargetIp.textContent = uid;
    unreadCounts[uid] = 0;
    updateBadge(uid);

    // Request history
    sendOverWs({
            type: "cmd",
            action: "get_chat_history",
            data: { target_uid: uid }
        });

    setTimeout(() => dashChatInput.focus(), 300);
}
dashChatClose.addEventListener('click', () => {
    dashChatPanel.classList.remove('active');
    activeChatUid = null;
});

dashChatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!activeChatUid) return;
    const msg = dashChatInput.value.trim();
    if (!msg) return;

    sendOverWs({
            type: "cmd",
            action: "send_chat",
            data: {
                sender_name: "Admin",
                message: msg,
                target_uid: activeChatUid
            }
        });
    dashChatInput.value = '';
});
export function formatTime(isoStr) {
    if (!isoStr) return '';
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    } catch {
        return '';
    }
}
export function createMsgEl(msgData) {
    const { sender_name, message, is_admin, created_at } = msgData;
    const isMe = is_admin;
    const wrapper = document.createElement('div');

    const meta = document.createElement('span');
    meta.className = isMe ? 'dash-chat-me-meta' : 'dash-chat-meta';
    meta.textContent = `${isMe ? 'Admin' : sender_name} • ${formatTime(created_at)}`;

    const bubble = document.createElement('div');
    bubble.className = `dash-chat-msg ${isMe ? 'me' : 'them'}`;
    bubble.textContent = message;

    if (isMe) {
        wrapper.appendChild(bubble);
        wrapper.appendChild(meta);
        wrapper.style.alignSelf = 'flex-end';
        wrapper.style.display = 'flex';
        wrapper.style.flexDirection = 'column';
    } else {
        wrapper.appendChild(meta);
        wrapper.appendChild(bubble);
        wrapper.style.alignSelf = 'flex-start';
        wrapper.style.display = 'flex';
        wrapper.style.flexDirection = 'column';
    }
    return wrapper;
}
export function renderChatHistory(messages) {
    dashChatMessages.innerHTML = '';
    messages.forEach(m => {
        dashChatMessages.appendChild(createMsgEl(m));
    });
    dashChatMessages.scrollTop = dashChatMessages.scrollHeight;
}
export function handleIncomingChat(msgData) {
    const { client_uid } = msgData;
    if (client_uid === activeChatUid) {
        dashChatMessages.appendChild(createMsgEl(msgData));
        dashChatMessages.scrollTop = dashChatMessages.scrollHeight;
    } else if (client_uid && !msgData.is_admin) {
        // Unread from another client
        unreadCounts[client_uid] = (unreadCounts[client_uid] || 0) + 1;
        updateBadge(client_uid);
    }
}
