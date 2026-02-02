#!/bin/bash
#
# Jellyfin Manager Launcher
# Opens a terminal and runs the application
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SCRIPT="$SCRIPT_DIR/jellyfin_manager.py"
VENV_DIR="$SCRIPT_DIR/.venv"

# Build the command to run inside terminal
# Activates venv if it exists, otherwise prompts to run setup
RUN_CMD="cd \"$SCRIPT_DIR\"

# Check if venv exists
if [ -d \"$VENV_DIR\" ]; then
    echo 'Activating virtual environment...'
    source \"$VENV_DIR/bin/activate\"
    python \"$APP_SCRIPT\"
else
    echo ''
    echo '══════════════════════════════════════════════'
    echo '  Virtual environment not found!'
    echo '══════════════════════════════════════════════'
    echo ''
    echo 'Please run setup first:'
    echo '  ./setup_env.sh'
    echo ''
    echo 'Then try launching again.'
fi

echo ''
echo '─────────────────────────────────────'
echo 'Jellyfin Manager closed.'
echo 'Press Enter to close this window...'
read"

# Try to find an available terminal emulator
if command -v konsole &> /dev/null; then
    konsole --hold -e bash -c "$RUN_CMD"
elif command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "$RUN_CMD"
elif command -v xfce4-terminal &> /dev/null; then
    xfce4-terminal --hold -e "bash -c \"$RUN_CMD\""
elif command -v kitty &> /dev/null; then
    kitty --hold bash -c "$RUN_CMD"
elif command -v alacritty &> /dev/null; then
    alacritty --hold -e bash -c "$RUN_CMD"
elif command -v xterm &> /dev/null; then
    xterm -hold -e bash -c "$RUN_CMD"
elif command -v terminator &> /dev/null; then
    terminator -e "bash -c \"$RUN_CMD\""
else
    echo "No supported terminal emulator found!"
    echo "Please install one of: konsole, gnome-terminal, xfce4-terminal, kitty, alacritty, xterm"
    exit 1
fi
