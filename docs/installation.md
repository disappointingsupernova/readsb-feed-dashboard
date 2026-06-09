# Installation

## Prerequisites

| Requirement | Minimum | Notes |
|---|---|---|
| OS | Linux (systemd-based) | Debian/Ubuntu/Raspberry Pi OS recommended |
| Python | 3.9+ | `python3 --version` |
| python3-venv | Any | `sudo apt install python3-venv` |
| readsb | Any | At least one instance running |

## Automated Install

```bash
git clone https://github.com/Louis/readsb-feed-dashboard.git
cd readsb-feed-dashboard
sudo bash install.sh
```

This will:
1. Verify Python 3.9+ and install `python3-venv` if needed
2. Copy the project to `/opt/readsb-feed-dashboard`
3. Create a dedicated virtual environment at `/opt/readsb-feed-dashboard/.venv`
4. Install the Python package and dependencies (rich) into the venv
5. Create a wrapper script at `/usr/local/bin/readsb-feed-dashboard`
6. Copy the example config to `/etc/readsb-feed-dashboard.conf` (if none exists)
7. Verify project integrity (pyproject.toml and src/ directory present)

## Manual Install

```bash
git clone https://github.com/Louis/readsb-feed-dashboard.git
cd readsb-feed-dashboard
python3 -m venv .venv
.venv/bin/pip install .
sudo ln -sf "$(pwd)/.venv/bin/readsb-feed-dashboard" /usr/local/bin/readsb-feed-dashboard
```

## Uninstall

```bash
sudo bash uninstall.sh
```

Or manually:

```bash
sudo rm -f /usr/local/bin/readsb-feed-dashboard
sudo rm -rf /opt/readsb-feed-dashboard
sudo rm -f /etc/readsb-feed-dashboard.conf  # Optional
```

## Updating

```bash
sudo readsb-feed-dashboard --update
```

This pulls the latest code and re-installs into the existing venv.

Or manually:

```bash
cd /opt/readsb-feed-dashboard
sudo git pull
sudo .venv/bin/pip install --upgrade .
```

## Verifying Installation

```bash
readsb-feed-dashboard --version
readsb-feed-dashboard --dump-config
```

## Directory Layout After Install

```
/opt/readsb-feed-dashboard/           # Source code
/opt/readsb-feed-dashboard/.venv/     # Python virtual environment
/usr/local/bin/readsb-feed-dashboard  # Wrapper script (calls venv Python)
/etc/readsb-feed-dashboard.conf       # Configuration (optional)
```

## Why a Virtual Environment?

Modern Debian/Ubuntu (PEP 668) marks the system Python as externally managed. Installing packages system-wide with pip is blocked. The venv approach:
- Avoids `externally-managed-environment` errors
- Isolates dependencies from system packages
- Does not require `--break-system-packages`
- Can be cleanly removed without affecting the system
