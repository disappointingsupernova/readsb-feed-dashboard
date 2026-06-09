# Usage

## Basic Usage

```bash
# Run with auto-detection (recommended for first use)
readsb-feed-dashboard

# Run with a specific config file
readsb-feed-dashboard --config /etc/readsb-feed-dashboard.conf

# Force ASCII mode (no Unicode box-drawing)
readsb-feed-dashboard --ascii

# Force Unicode mode
readsb-feed-dashboard --unicode

# Custom refresh rate (seconds)
readsb-feed-dashboard --refresh 5

# Show more aircraft rows
readsb-feed-dashboard --max-rows 20

# Compact mode — summary and panels only, no aircraft tables
readsb-feed-dashboard --compact

# Sort aircraft by distance instead of seen time
readsb-feed-dashboard --sort distance

# Use the solarised colour theme
readsb-feed-dashboard --theme solarised

# Log to CSV each cycle
readsb-feed-dashboard --log /var/log/readsb-dashboard.csv

# Export current state as JSON (single shot)
readsb-feed-dashboard --export json

# Watchdog mode — exit non-zero if any feed is unhealthy
readsb-feed-dashboard --watchdog

# Render once and exit (useful for screenshots)
readsb-feed-dashboard --once

# Dump auto-detected configuration
readsb-feed-dashboard --dump-config

# Update to latest version
sudo readsb-feed-dashboard --update

# Show version
readsb-feed-dashboard --version
```

## Command-Line Reference

```
usage: readsb-feed-dashboard [-h] [--version] [--config CONFIG] [--refresh REFRESH]
                             [--ascii] [--unicode] [--max-rows MAX_ROWS]
                             [--sort {seen,distance,altitude,rssi}]
                             [--compact] [--theme {dark,light,solarised}]
                             [--log LOG] [--export {json}] [--watchdog]
                             [--update] [--dump-config] [--once]

Terminal dashboard for monitoring multi-readsb ADS-B setups.

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --config, -c CONFIG   Path to configuration file (default: auto-detect)
  --refresh, -r REFRESH Refresh interval in seconds (default: 2.0)
  --ascii               Force ASCII-safe mode
  --unicode             Force Unicode mode
  --max-rows MAX_ROWS   Maximum aircraft rows per feed table (default: 10)
  --sort {seen,distance,altitude,rssi}
                        Sort aircraft table by field (default: seen)
  --compact             Compact mode — hide aircraft tables
  --theme {dark,light,solarised}
                        Colour theme (default: dark)
  --log LOG             Log feed data to CSV file each cycle
  --export {json}       Export current state as JSON and exit
  --watchdog            Exit non-zero if any feed is down
  --update              Update to the latest version
  --dump-config         Dump configuration as JSON and exit
  --once                Render once and exit
```

## Keyboard Controls

While the dashboard is running interactively:

| Key | Action |
|---|---|
| `q` | Quit |
| `s` | Toggle compact/summary-only mode |
| `f` | Cycle sort order (seen -> distance -> altitude -> rssi) |
| `1` | Focus on feed 1 (full detail) |
| `2` | Focus on feed 2 (full detail) |
| `3` | Focus on feed 3 (full detail) |
| `0` | Return to all-feeds view |

## Modes

### Default Mode

Shows all feeds side-by-side with summary panel and aircraft tables.

### Compact Mode (`--compact` or press `s`)

Hides the per-feed aircraft tables, showing only the summary and feed info panels. Useful for small terminals or quick status checks.

### Focused Mode (press `1`, `2`, `3`, etc.)

Shows a single feed in full detail. Press `0` to return to the multi-feed view.

### Watchdog Mode (`--watchdog`)

Non-interactive. Checks all feeds once and exits:
- Exit code 0: all feeds healthy
- Exit code 1: one or more feeds down/stale

Useful in cron jobs or monitoring scripts:

```bash
readsb-feed-dashboard --watchdog || echo "ALERT: Feed failure detected" | mail -s "readsb alert" admin@example.com
```

### Export Mode (`--export json`)

Outputs a single JSON snapshot of all feed data. Useful for integration with external monitoring tools:

```bash
readsb-feed-dashboard --export json | jq '.feeds[].aircraft_count'
```

## Logging

Enable CSV logging with `--log` or the `log_path` config field:

```bash
readsb-feed-dashboard --log /var/log/readsb-dashboard.csv
```

The CSV format:

```csv
timestamp,feed,aircraft,position_tracked,messages_rate,service_active,json_stale
2025-01-15T14:32:07,SDR1,47,42,312.5,active,False
2025-01-15T14:32:07,SDR2,52,48,287.3,active,False
2025-01-15T14:32:07,MERGED,55,50,599.8,active,False
```

## Themes

Three built-in colour themes:

- `dark` — cyan/green/red on dark backgrounds (default)
- `light` — darker tones for light terminal backgrounds
- `solarised` — Solarised colour palette

Set via `--theme` or in config:

```json
{
  "theme": "solarised"
}
```

## SSH Usage

Works over SSH — allocate a pseudo-terminal:

```bash
ssh user@adsb-pi -t readsb-feed-dashboard
```

## Running on Boot (Optional)

Start the dashboard in a tmux session:

```bash
tmux new-session -d -s dashboard 'readsb-feed-dashboard'
```

## tmux/screen Detection

When running inside tmux or screen, the dashboard automatically increases the minimum refresh interval to 3 seconds to reduce bandwidth over slow connections.
