# Configuration

The dashboard operates in two modes:

1. **Auto-detection** — no config file needed; discovers feeds automatically.
2. **Manual configuration** — explicit control via a JSON config file.

## Config File Locations

The dashboard searches these paths in order:

1. `/etc/readsb-feed-dashboard.conf`
2. `~/.config/readsb-feed-dashboard/config.json`
3. Path specified via `--config /path/to/file.json`

If no config file is found, auto-detection is used.

## Full Config File Example

```json
{
  "title": "readsb Multi-Feed Dashboard",
  "refresh_interval": 2.0,
  "unicode_mode": true,
  "max_aircraft_rows": 10,
  "show_ports": true,
  "show_service_status": true,
  "theme": "dark",
  "sort_by": "seen",
  "stale_threshold": 10.0,
  "sparkline_length": 60,
  "compact_mode": false,
  "log_path": null,
  "feeds": [
    {
      "label": "SDR1",
      "json_path": "/run/readsb-sdr1/aircraft.json",
      "json_url": null,
      "service_name": "readsb-sdr1",
      "feed_type": "sdr",
      "beast_port": 30105,
      "sbs_port": null,
      "serial": "64466840",
      "alerts": {
        "min_aircraft": 5,
        "alert_on_service_inactive": true,
        "alert_on_stale_json": true
      }
    },
    {
      "label": "SDR2",
      "json_path": "/run/readsb-sdr2/aircraft.json",
      "service_name": "readsb-sdr2",
      "feed_type": "sdr",
      "beast_port": 30205,
      "serial": "95440338"
    },
    {
      "label": "MERGED",
      "json_path": "/run/readsb/aircraft.json",
      "service_name": "readsb",
      "feed_type": "merge",
      "beast_port": 30005,
      "sbs_port": 30003
    },
    {
      "label": "REMOTE-PI",
      "json_url": "http://192.168.1.50/tar1090/data/aircraft.json",
      "feed_type": "sdr"
    }
  ]
}
```

## Field Reference

### Top-Level Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `title` | string | `"readsb Multi-Feed Dashboard"` | Dashboard title text |
| `refresh_interval` | float | `2.0` | Seconds between data refreshes |
| `unicode_mode` | bool | auto-detected | Use Unicode box-drawing characters |
| `max_aircraft_rows` | int | `10` | Max aircraft shown per feed table |
| `show_ports` | bool | `true` | Show listening port information |
| `show_service_status` | bool | `true` | Show systemd service status |
| `theme` | string | `"dark"` | Colour theme: `dark`, `light`, or `solarised` |
| `sort_by` | string | `"seen"` | Aircraft sort order: `seen`, `distance`, `altitude`, `rssi` |
| `stale_threshold` | float | `10.0` | Seconds before JSON is considered stale |
| `sparkline_length` | int | `60` | Number of historical data points for sparkline graphs |
| `compact_mode` | bool | `false` | Hide aircraft tables, show only panels |
| `log_path` | string | `null` | Path to CSV log file (null = no logging) |

### Feed Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `label` | string | Yes | Display name for this feed |
| `json_path` | string | No* | Path to local `aircraft.json` |
| `json_url` | string | No* | URL to remote `aircraft.json` |
| `service_name` | string | No | systemd service name |
| `feed_type` | string | No | `"sdr"` or `"merge"` |
| `beast_port` | int | No | Beast output port number |
| `sbs_port` | int | No | SBS (BaseStation) output port |
| `serial` | string | No | RTL-SDR dongle serial number |
| `alerts` | object | No | Alert thresholds (see below) |

*Either `json_path` or `json_url` must be provided.

### Alert Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `min_aircraft` | int | `null` | Alert if aircraft count drops below this |
| `alert_on_service_inactive` | bool | `true` | Alert if systemd service goes inactive/failed |
| `alert_on_stale_json` | bool | `true` | Alert if JSON data becomes stale |

## Remote Feeds

To monitor a readsb instance on another machine (via tar1090 or raw HTTP):

```json
{
  "label": "REMOTE-PI",
  "json_url": "http://192.168.1.50/tar1090/data/aircraft.json",
  "feed_type": "sdr"
}
```

Remote feeds will not have service status, uptime, CPU/memory, or port information — only aircraft data.

## Auto-Detection Behaviour

When no config file is present, the dashboard will:

1. Scan known JSON directories (`/run/readsb*`)
2. Query systemd for `readsb*` services
3. Parse `/etc/default/readsb*` files for serial numbers and port configs
4. Check the `LANG`/`LC_ALL` environment for Unicode support
5. Detect tmux/screen and auto-increase refresh interval

### Detected Paths

```
/run/readsb/aircraft.json
/run/readsb-sdr1/aircraft.json
/run/readsb-sdr2/aircraft.json
/run/readsb-sdr3/aircraft.json
/run/readsb-sdr4/aircraft.json
/run/readsb-merge/aircraft.json
```

## Dumping Detected Config

```bash
readsb-feed-dashboard --dump-config
```

Save it directly as your config:

```bash
readsb-feed-dashboard --dump-config > /etc/readsb-feed-dashboard.conf
```

## Themes

### Dark (default)

Bright colours on dark background. Best for typical terminal emulators.

### Light

Darker tones designed for terminals with white/light backgrounds.

### Solarised

Uses the [Solarised](https://ethanschoonover.com/solarized/) colour palette.
