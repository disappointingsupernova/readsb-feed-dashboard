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

## Config File Format

```json
{
  "title": "readsb Multi-Feed Dashboard",
  "refresh_interval": 2.0,
  "unicode_mode": true,
  "max_aircraft_rows": 10,
  "show_ports": true,
  "show_service_status": true,
  "feeds": [
    {
      "label": "SDR1",
      "json_path": "/run/readsb-sdr1/aircraft.json",
      "service_name": "readsb-sdr1",
      "feed_type": "sdr",
      "beast_port": 30105,
      "sbs_port": null,
      "serial": "64466840"
    },
    {
      "label": "SDR2",
      "json_path": "/run/readsb-sdr2/aircraft.json",
      "service_name": "readsb-sdr2",
      "feed_type": "sdr",
      "beast_port": 30205,
      "sbs_port": null,
      "serial": "95440338"
    },
    {
      "label": "MERGED",
      "json_path": "/run/readsb/aircraft.json",
      "service_name": "readsb",
      "feed_type": "merge",
      "beast_port": 30005,
      "sbs_port": 30003,
      "serial": null
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
| `feeds` | array | `[]` | List of feed configurations |

### Feed Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `label` | string | Yes | Display name for this feed |
| `json_path` | string | Yes | Path to `aircraft.json` |
| `service_name` | string | No | systemd service name |
| `feed_type` | string | No | `"sdr"` or `"merge"` |
| `beast_port` | int | No | Beast output port number |
| `sbs_port` | int | No | SBS (BaseStation) output port |
| `serial` | string | No | RTL-SDR dongle serial number |

## Auto-Detection Behaviour

When no config file is present, the dashboard will:

1. Scan known JSON directories (`/run/readsb*`)
2. Query systemd for `readsb*` services
3. Parse `/etc/default/readsb*` files for serial numbers and port configs
4. Check the `LANG`/`LC_ALL` environment for Unicode support

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

To see what the dashboard auto-detected:

```bash
readsb-feed-dashboard --dump-config
```

This outputs valid JSON you can save as your config file:

```bash
readsb-feed-dashboard --dump-config > /etc/readsb-feed-dashboard.conf
```
