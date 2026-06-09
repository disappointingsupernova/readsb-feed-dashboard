# Installation

## Prerequisites

| Requirement | Minimum | Notes |
|---|---|---|
| OS | Linux (systemd-based) | Debian/Ubuntu/Raspberry Pi OS recommended |
| Python | 3.9+ | `python3 --version` |
| pip | Any recent | `python3 -m pip --version` |
| readsb | Any | At least one instance running |

## Automated Install

```bash
git clone https://github.com/Louis/readsb-feed-dashboard.git
cd readsb-feed-dashboard
sudo bash install.sh
```

This will:
1. Copy the project to `/opt/readsb-feed-dashboard`
2. Install the Python package and dependencies
3. Create a symlink at `/usr/local/bin/readsb-feed-dashboard`
4. Copy the example config to `/etc/readsb-feed-dashboard.conf` (if none exists)

## Manual Install

```bash
git clone https://github.com/Louis/readsb-feed-dashboard.git
cd readsb-feed-dashboard
python3 -m pip install .
sudo ln -sf $(which readsb-feed-dashboard) /usr/local/bin/readsb-feed-dashboard
```

## Uninstall

```bash
sudo bash uninstall.sh
```

Or manually:

```bash
sudo python3 -m pip uninstall readsb-feed-dashboard
sudo rm -f /usr/local/bin/readsb-feed-dashboard
sudo rm -rf /opt/readsb-feed-dashboard
sudo rm -f /etc/readsb-feed-dashboard.conf  # Optional
```

## Updating

```bash
readsb-feed-dashboard --update
```

Or manually:

```bash
cd /opt/readsb-feed-dashboard
sudo git pull
sudo python3 -m pip install --upgrade .
```

## Verifying Installation

```bash
readsb-feed-dashboard --version
readsb-feed-dashboard --dump-config
```

## Directory Layout After Install

```
/opt/readsb-feed-dashboard/         # Source code
/usr/local/bin/readsb-feed-dashboard  # Symlink/wrapper
/etc/readsb-feed-dashboard.conf     # Configuration (optional)
```
