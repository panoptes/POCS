#!/usr/bin/env bash
set -e

# Store the current directory
INSTALL_DIR=$(pwd)

# Wallpaper image
WALLPAPER_URL="https://drive.google.com/uc?export=download&id=1vdJgDWsbl6LM7p-Hkyxgp4WTtpUO5UAd"

# Colors and formatting
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
BOLD='\033[1m'
CHECK='\xE2\x9C\x94'

# Progress function
print_step() {
    echo -e "\n${BLUE}${BOLD}[Step $1/$2]${NC} $3"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

print_success() {
    echo -e "${GREEN}${CHECK} $1${NC}"
}

# Live log tail function
run_with_log_tail() {
    local script=$1
    local log_file="install.log"
    local spinner=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local spin_idx=0

    # Start the script in background
    source "$script" >> "$log_file" 2>&1 &
    local pid=$!

    # Show spinner and last log line while running
    while kill -0 $pid 2>/dev/null; do
        if [ -f "$log_file" ]; then
            local last_line=$(tail -n 1 "$log_file" 2>/dev/null | cut -c1-70)
            printf "\r${YELLOW}${spinner[$spin_idx]}${NC} %s                    " "$last_line"
        fi
        spin_idx=$(( (spin_idx + 1) % 10 ))
        sleep 0.1
    done

    # Wait for the process to complete and get exit status
    wait $pid
    local exit_status=$?

    # Clear the spinner line
    printf "\r%80s\r" " "

    return $exit_status
}

# Banner
echo -e "${BOLD}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║                                                   ║"
echo "║           POCS Installation Script                ║"
echo "║     PANOPTES Observatory Control System           ║"
echo "║                                                   ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

TOTAL_STEPS=8

print_step 1 $TOTAL_STEPS "Setting up user"
source ./setup-user.sh > install.log 2>&1
print_success "User setup complete"

print_step 2 $TOTAL_STEPS "Fixing system time"
source ./fix-time.sh >> install.log 2>&1
print_success "System time configured"

print_step 3 $TOTAL_STEPS "Installing system dependencies"
run_with_log_tail ./install-system-deps.sh
print_success "System dependencies installed"

# Fetch the wallpaper image and set using pcmanfm if available.
if command -v pcmanfm &> /dev/null; then
    wget -qO /tmp/pocs_wallpaper.png "$WALLPAPER_URL"
    if [ -f "/tmp/pocs_wallpaper.png" ]; then
      mv /tmp/pocs_wallpaper.png "${HOME}/.wallpaper.png"
      pcmanfm --set-wallpaper="${HOME}/.wallpaper.png" --wallpaper-mode=stretch
    fi
fi

print_step 4 $TOTAL_STEPS "Installing ZSH for a better shell"
source ./install-zsh.sh >> install.log 2>&1
print_success "ZSH installed"

print_step 5 $TOTAL_STEPS "Installing uv for python management"
source ./install-uv.sh >> install.log 2>&1
print_success "uv installed"

print_step 6 $TOTAL_STEPS "Installing POCS software"
run_with_log_tail ./install-pocs.sh
cd "${INSTALL_DIR}"
print_success "POCS software installed"

print_step 7 $TOTAL_STEPS "Installing services for startup"
source ./install-services.sh >> install.log 2>&1
print_success "Services configured"

print_step 8 $TOTAL_STEPS "Installing ZWO drivers for ASI cameras"
source ./install-zwo-drivers.sh >> install.log 2>&1
print_success "ZWO drivers installed"

echo -e "\n${YELLOW}Running POCS configuration setup...${NC}"
"${HOME}/bin/pocs" config setup

echo -e "\n${GREEN}${BOLD}"
echo "╔═══════════════════════════════════════════════════╗"
echo "║                                                   ║"
echo "║        ✓  Installation Complete!                  ║"
echo "║                                                   ║"
echo "╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "\n${YELLOW}${BOLD}Important:${NC}"
echo -e "  1. ${BOLD}Reboot${NC} your system to apply all changes"
echo -e "  2. After reboot, run: ${BOLD}pocs mount setup${NC}"
echo -e "  3. Then run: ${BOLD}pocs camera setup${NC}"
echo ""
