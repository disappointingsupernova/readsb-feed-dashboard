#!/usr/bin/env bash
# uninstall.sh — Remove readsb-feed-dashboard

set -euo pipefail

INSTALL_DIR="/opt/readsb-feed-dashboard"
SYMLINK="/usr/local/bin/readsb-feed-dashboard"
CONFIG_FILE="/etc/readsb-feed-dashboard.conf"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root (use sudo)."
fi

echo "This will remove readsb-feed-dashboard from your system."
echo
read -rp "Remove installation directory ($INSTALL_DIR)? [y/N] " remove_install
read -rp "Remove config file ($CONFIG_FILE)? [y/N] " remove_config

# Uninstall Python package
info "Removing Python package..."
python3 -m pip uninstall -y readsb-feed-dashboard 2>/dev/null || \
    warn "Python package not found in pip (may have been installed differently)."

# Remove symlink
if [[ -L "$SYMLINK" ]] || [[ -f "$SYMLINK" ]]; then
    rm -f "$SYMLINK"
    info "Removed symlink: $SYMLINK"
fi

# Remove install directory
if [[ "${remove_install,,}" == "y" ]]; then
    if [[ -d "$INSTALL_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
        info "Removed: $INSTALL_DIR"
    else
        warn "Directory not found: $INSTALL_DIR"
    fi
fi

# Remove config
if [[ "${remove_config,,}" == "y" ]]; then
    if [[ -f "$CONFIG_FILE" ]]; then
        rm -f "$CONFIG_FILE"
        info "Removed: $CONFIG_FILE"
    else
        warn "Config not found: $CONFIG_FILE"
    fi
fi

echo
info "Uninstallation complete."
