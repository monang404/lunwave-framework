export function handleChatMessage(msg) {
    switch (msg.type) {
        case "chat_history":
            if (globalThis.ChatModule) globalThis.ChatModule.onHistory(msg.data);
            break;
        case "chat_message":
            if (globalThis.ChatModule) globalThis.ChatModule.onNewMessage(msg.data);
            break;
    }
}
