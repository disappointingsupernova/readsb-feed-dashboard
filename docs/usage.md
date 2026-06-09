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

# Render once and exit (useful for screenshots or piping)
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
  --update              Update to the latest version
  --dump-config         Dump configuration as JSON and exit
  --once                Render once and exit
```

## Keyboard Controls

| Key | Action |
|---|---|
| `Ctrl+C` | Exit cleanly |

## Example Output

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                      readsb Multi-Feed Dashboard                             │
│                        2025-01-15 14:32:07                                   │
└──────────────────────────────────────────────────────────────────────────────┘
┌─ Summary ────────────────────────────────────────────────────────────────────┐
│  Feed     Aircraft  Unique  Service  JSON                                    │
│  SDR1     47        3       active   LIVE                                    │
│  SDR2     52        8       active   LIVE                                    │
│  MERGED   55        0       active   LIVE                                    │
│                                                                              │
│  TOTAL UNIQUE  55                                                            │
└──────────────────────────────────────────────────────────────────────────────┘
┌─ SDR1 [64466840] ────┐  ┌─ SDR2 [95440338] ────┐  ┌─ MERGED ───────────────┐
│  Aircraft:    47      │  │  Aircraft:    52      │  │  Aircraft:    55       │
│  Service:     active  │  │  Service:     active  │  │  Service:     active   │
│  JSON:        LIVE    │  │  JSON:        LIVE    │  │  JSON:        LIVE     │
│  Unique:      3       │  │  Unique:      8       │  │  Unique:      0        │
│  Shared w/SDR2: 44    │  │  Shared w/SDR1: 44    │  │  Beast port:  30005    │
│  Beast port:  30105   │  │  Beast port:  30205   │  │  SBS port:    30003    │
│  Serial:      64466840│  │  Serial:      95440338│  │                        │
└───────────────────────┘  └───────────────────────┘  └────────────────────────┘
┌─ Latest Aircraft — SDR1 ─────────────────────────────────────────────────────┐
│  Hex      Flight   Alt (ft)  Spd (kt)  RSSI   Squawk  Dist (nm)  Seen (s)   │
│  4ca87d   RYR3456  37000     482       -3.2   2431    42.1       0          │
│  400a12   BAW92    34000     448       -5.1   4321    38.7       1          │
│  ...                                                                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Running on Boot (Optional)

To start the dashboard automatically in a tmux session:

```bash
# Add to /etc/rc.local or create a systemd service:
tmux new-session -d -s dashboard 'readsb-feed-dashboard'
```

## SSH Usage

Works perfectly over SSH:

```bash
ssh user@adsb-pi -t readsb-feed-dashboard
```

The `-t` flag allocates a pseudo-terminal, required for the TUI to render correctly.
