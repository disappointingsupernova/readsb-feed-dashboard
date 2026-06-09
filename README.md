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
- Position-tracked vs Mode-S-only aircraft breakdown
- Live message rate (msgs/sec) per feed
- Service uptime display
- Signal strength statistics (min/avg/max RSSI) with colour coding
- Aircraft type breakdown (ADS-B, MLAT, TIS-B, Mode-S)
- Distance ring distribution (50/100/150/200+ nm)
- Feed health sparkline graphs
- CPU, memory, and network I/O per service
- Threshold-based alerts (aircraft count, service down, stale JSON)
- Remote feed monitoring over HTTP
- Displays latest aircraft with hex, callsign, altitude, speed, RSSI, squawk, distance, type, and seen time
- Reports service status (active/inactive/failed)
- Detects stale or missing JSON files
- ASCII-safe mode for terminals without Unicode support
- Configurable via JSON config file or fully automatic
- Custom feed labels
- Keyboard navigation (focus feeds, toggle views, cycle sort)
- Configurable sort (seen, distance, altitude, RSSI)
- Compact/summary-only mode
- Three colour themes (dark, light, solarised)
- CSV logging for historical data
- JSON export for external tooling
- Watchdog mode for scripts and cron
- tmux/screen auto-detection with throttling

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
- [Data Flow](docs/data-flow.md)
- [Deployment](docs/deployment.md)
- [Security](docs/security.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Extending](docs/extending.md)

## Licence

MIT
