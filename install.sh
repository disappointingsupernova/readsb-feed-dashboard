#!/usr/bin/env bash
# install.sh — Install readsb-feed-dashboard
# Requires: Python 3.9+, pip, git

set -euo pipefail

INSTALL_DIR="/opt/readsb-feed-dashboard"
SYMLINK="/usr/local/bin/readsb-feed-dashboard"
CONFIG_DIR="/etc"
CONFIG_FILE="${CONFIG_DIR}/readsb-feed-dashboard.conf"
REPO_URL="https://github.com/disappointingsupernova/readsb-feed-dashboard.git"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# Pre-flight checks
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use sudo)."
    fi
}

check_python() {
    if ! command -v python3 &>/dev/null; then
        error "Python 3.9+ is required. Install with: sudo apt install python3 python3-pip"
    fi

    local version
    version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    local major minor
    major=$(echo "$version" | cut -d. -f1)
    minor=$(echo "$version" | cut -d. -f2)

    if [[ $major -lt 3 ]] || { [[ $major -eq 3 ]] && [[ $minor -lt 9 ]]; }; then
        error "Python 3.9+ required, found $version."
    fi

    info "Python $version detected."
}

check_dependencies() {
    local missing=()

    for cmd in jq systemctl ss; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        warn "Optional dependencies not found: ${missing[*]}"
        warn "Some features may be limited. Install with:"
        warn "  sudo apt install jq iproute2"
    fi
}

install_app() {
    info "Installing readsb-feed-dashboard..."

    # Clone or copy to install directory
    if [[ -d "$INSTALL_DIR" ]]; then
        info "Existing installation found. Updating..."
        cd "$INSTALL_DIR"
        if [[ -d .git ]]; then
            git pull --ff-only || warn "Git pull failed, continuing with existing files."
        fi
    else
        if [[ -d ".git" ]] && [[ -f "pyproject.toml" ]]; then
            # Installing from local clone
            info "Installing from local repository..."
            cp -r "$(pwd)" "$INSTALL_DIR"
        else
            info "Cloning repository..."
            git clone "$REPO_URL" "$INSTALL_DIR" || error "Failed to clone repository."
        fi
    fi

    # Install Python package
    info "Installing Python package..."
    python3 -m pip install --break-system-packages "$INSTALL_DIR" 2>/dev/null || \
    python3 -m pip install "$INSTALL_DIR" || \
    error "Failed to install Python package."

    # Create symlink
    if [[ -L "$SYMLINK" ]] || [[ -f "$SYMLINK" ]]; then
        rm -f "$SYMLINK"
    fi

    # Find the installed script
    local script_path
    script_path=$(python3 -c "import shutil; print(shutil.which('readsb-feed-dashboard') or '')" 2>/dev/null)

    if [[ -n "$script_path" ]]; then
        ln -sf "$script_path" "$SYMLINK"
        info "Symlink created: $SYMLINK -> $script_path"
    else
        # Create a wrapper script
        cat > "$SYMLINK" << 'EOF'
#!/usr/bin/env bash
exec python3 -m readsb_feed_dashboard "$@"
EOF
        chmod +x "$SYMLINK"
        info "Wrapper script created at $SYMLINK"
    fi

    # Install example config if none exists
    if [[ ! -f "$CONFIG_FILE" ]]; then
        if [[ -f "$INSTALL_DIR/config/readsb-feed-dashboard.conf.example" ]]; then
            info "No config file found. Copying example to $CONFIG_FILE"
            cp "$INSTALL_DIR/config/readsb-feed-dashboard.conf.example" "$CONFIG_FILE"
            info "Edit $CONFIG_FILE to match your setup, or delete it to use auto-detection."
        fi
    else
        info "Existing config file preserved at $CONFIG_FILE"
    fi
}

print_summary() {
    echo
    info "Installation complete!"
    echo
    echo "  Usage:"
    echo "    readsb-feed-dashboard              # Run with auto-detection"
    echo "    readsb-feed-dashboard --ascii      # Force ASCII mode"
    echo "    readsb-feed-dashboard --config /etc/readsb-feed-dashboard.conf"
    echo "    readsb-feed-dashboard --help       # Show all options"
    echo "    readsb-feed-dashboard --update     # Update to latest version"
    echo
    echo "  Config file: $CONFIG_FILE"
    echo "  Install dir: $INSTALL_DIR"
    echo
}

# Main
check_root
check_python
check_dependencies
install_app
print_summary
