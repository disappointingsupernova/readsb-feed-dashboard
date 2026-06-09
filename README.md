# readsb-feed-dashboard

A polished terminal dashboard for monitoring multi-readsb ADS-B setups.

Displays live aircraft counts, per-feed statistics, overlap analysis, service health, and detailed aircraft tables — all in a single terminal view.

## Quick Start

```bash
# Install
sudo bash install.sh

# Run
readsb-feed-dashboard

# Run in ASCII mode (for basic terminals)
readsb-feed-dashboard --ascii

# Show help
readsb-feed-dashboard --help
```

## Features

- Supports 1, 2, or more SDR feeds plus merged feeds
- Auto-detects readsb instances, JSON paths, systemd services, ports, and receiver serials
- Shows aircraft counts, unique-per-feed counts, and shared counts
- Displays latest aircraft with hex, callsign, altitude, speed, RSSI, squawk, distance, and seen time
- Reports service status (active/inactive/failed)
- Detects stale or missing JSON files
- ASCII-safe mode for terminals without Unicode support
- Configurable via JSON config file or fully automatic
- Custom feed labels

## Requirements

- Linux with systemd
- Python 3.9+
- `rich` Python package (installed automatically)
- Optional: `jq`, `ss` (iproute2) for extended diagnostics

## Configuration

The dashboard works without any configuration by auto-detecting your setup. For manual control, create `/etc/readsb-feed-dashboard.conf` — see [docs/configuration.md](docs/configuration.md).

## Documentation

- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Usage](docs/usage.md)
- [Architecture](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Extending](docs/extending.md)

## Licence

MIT
