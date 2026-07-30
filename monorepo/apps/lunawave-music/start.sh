#!/usr/bin/env bash

# ----------------------------------------------------------
#  CONFIGURATION
# ----------------------------------------------------------
export LUNAWAVE_HOST=${LUNAWAVE_HOST:-${YTGUI_HOST:-"0.0.0.0"}}
export LUNAWAVE_PORT=${LUNAWAVE_PORT:-${YTGUI_PORT:-8765}}
export LUNAWAVE_ADMIN_USER=${LUNAWAVE_ADMIN_USER:-${YTGUI_ADMIN_USER:-"admin"}}
if [ -n "$YTGUI_ADMIN_PASS" ]; then
    export LUNAWAVE_ADMIN_PASS=${LUNAWAVE_ADMIN_PASS:-$YTGUI_ADMIN_PASS}
fi

# ----------------------------------------------------------
#  COLORS & FORMATTING
# ----------------------------------------------------------
RESET="\033[0m"
BOLD="\033[1m"
CYAN="\033[1;36m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
MAGENTA="\033[1;35m"

# ----------------------------------------------------------
#  BANNER
# ----------------------------------------------------------
clear
echo -e "${MAGENTA}${BOLD}"
cat << "EOF"
 _      _    _ _   _   ___   __    __   ___  __      __ _____
| |    | |  | | \ | | / _ \  \ \  / /  / _ \ \ \    / /|  ___|
| |    | |  | |  \| |/ /_\ \  \ \/ /  / /_\ \ \ \  / / | |__
| |___ | |__| | |\  |  ___  \  \  /\  /  ___  \ \ \/ /  |  __|
|_____| \____/|_| \_/_/   \_\  \/  \/_/_/   \_\  \__/   |_____|

EOF
echo -e "${CYAN}    ========================================================="
echo -e "                    LunaWave Web Server Startup              "
echo -e "    =========================================================${RESET}"
echo ""

# ----------------------------------------------------------
#  STARTUP SEQUENCE
# ----------------------------------------------------------

echo -e "${CYAN}[*]${RESET} Initializing Environment Variables..."

python -m launcher.preflight --host "$LUNAWAVE_HOST" --port "$LUNAWAVE_PORT"
if [ $? -ne 0 ]; then
    echo -e "\n${RED}[X] Preflight check failed. Server will not start.${RESET}"
    exit 1
fi

echo -e "${CYAN}[*]${RESET} Cleaning Up Previous Sessions..."
if command -v killall &> /dev/null; then
    killall mpv > /dev/null 2>&1
else
    pkill mpv > /dev/null 2>&1
fi

if [ -d "/tmp" ]; then
    rm -f /tmp/mpv-socket-* 2>/dev/null
fi

SOCKET_DIR="${YT_PLAYER_BASE:-$(dirname "$0")}/cache/sockets"
if [ -d "$SOCKET_DIR" ]; then
    rm -f "$SOCKET_DIR"/*.sock 2>/dev/null
fi

# ----------------------------------------------------------
#  ADMIN ACCESS INFO
# ----------------------------------------------------------
PASS_FILE="${YT_PLAYER_BASE:-$(dirname "$0")}/cache/admin_password.txt"
echo ""
echo -e "${MAGENTA}---------------------------------------------------------${RESET}"
echo -e "${BOLD} Admin Access Information${RESET}"
echo -e "${MAGENTA}---------------------------------------------------------${RESET}"

if [ -n "$LUNAWAVE_ADMIN_PASS" ]; then
    echo -e "  [i] Password loaded from environment (LUNAWAVE_ADMIN_PASS)."
elif [ -f "$PASS_FILE" ]; then
    echo -e "  [i] Password stored securely in: $PASS_FILE"
else
    echo -e "  [i] A new password will be auto-generated on first launch."
fi
echo -e "  [i] Username: ${BOLD}${LUNAWAVE_ADMIN_USER:-admin}${RESET}"

# ----------------------------------------------------------
#  SERVER STARTUP
# ----------------------------------------------------------
echo ""
echo -e "${CYAN}    =========================================================${RESET}"
echo -e "       Client Interface : ${BOLD}http://localhost:${LUNAWAVE_PORT}/${RESET}"
echo -e "       Admin Interface  : ${BOLD}http://localhost:${LUNAWAVE_PORT}/admin${RESET}"
echo -e "       System Health    : ${BOLD}http://localhost:${LUNAWAVE_PORT}/health${RESET}"
echo -e "       Metrics          : ${BOLD}http://localhost:${LUNAWAVE_PORT}/metrics${RESET}"
echo -e "${CYAN}    =========================================================${RESET}"
echo ""
echo -e "${GREEN}[*] Starting Server...${RESET}"

python main.py

if [ $? -ne 0 ]; then
    echo -e "\n${RED}[X] Server terminated with an error.${RESET}"
    echo -e "    Please check the application logs for details."
fi
