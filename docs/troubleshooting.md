# Troubleshooting

## Common Issues

### "No feeds detected or configured"

The dashboard could not find any `aircraft.json` files or readsb services.

**Diagnosis:**

```bash
# Check if readsb is running
systemctl status readsb*

# Check for JSON files
ls -la /run/readsb*/aircraft.json

# Check what the dashboard auto-detects
readsb-feed-dashboard --dump-config
```

**Solutions:**

1. Ensure at least one readsb instance is running
2. Check that the JSON output directory exists and is populated
3. Create a manual config file if your paths are non-standard

---

### JSON shows as "STALE"

The `aircraft.json` file has not been updated in the last 10 seconds.

**Diagnosis:**

```bash
# Check file modification time
stat /run/readsb-sdr1/aircraft.json

# Watch for updates
watch -n 1 'stat --format=%Y /run/readsb-sdr1/aircraft.json'

# Check if the service is actually running
journalctl -u readsb-sdr1 --no-pager -n 20
```

**Solutions:**

1. Restart the readsb service: `sudo systemctl restart readsb-sdr1`
2. Check for SDR device issues: `rtl_test`
3. Check for permission issues on the run directory

---

### JSON shows as "ERROR: Malformed JSON"

The JSON file exists but cannot be parsed.

**Diagnosis:**

```bash
# Validate the JSON
jq . /run/readsb-sdr1/aircraft.json

# Check file size (0 bytes = problem)
ls -la /run/readsb-sdr1/aircraft.json

# Check disk space
df -h /run
```

---

### Service shows as "unknown"

The dashboard cannot query systemd.

**Diagnosis:**

```bash
# Check if systemctl is available
which systemctl

# Check if the service name is correct
systemctl list-units 'readsb*'

# Try manually
systemctl is-active readsb-sdr1
```

---

### Unicode characters render as garbage

Your terminal does not support UTF-8/Unicode.

**Solutions:**

```bash
# Force ASCII mode
readsb-feed-dashboard --ascii

# Or set in config
# "unicode_mode": false

# Check your locale
locale

# Set UTF-8 locale
export LANG=en_GB.UTF-8
```

---

### Permission denied reading JSON

The dashboard user cannot read the aircraft.json files.

**Diagnosis:**

```bash
# Check file permissions
ls -la /run/readsb-sdr1/aircraft.json

# Check directory permissions
ls -la /run/ | grep readsb

# Check who owns the files
stat /run/readsb-sdr1/aircraft.json
```

**Solutions:**

```bash
# Run as root (simplest)
sudo readsb-feed-dashboard

# Or add your user to the appropriate group
# Note: on many systems, /run/readsb is owned by readsb:nogroup
# so you may need to adjust permissions:
sudo chmod o+r /run/readsb-sdr1/aircraft.json
```

---

### Dashboard flickers or redraws poorly

**Solutions:**

```bash
# Increase refresh interval
readsb-feed-dashboard --refresh 5

# Try a different terminal emulator
# PuTTY sometimes has issues — try using screen or tmux:
tmux new-session 'readsb-feed-dashboard'
```

---

## Diagnostic Commands

```bash
# Full system check
echo "=== readsb services ==="
systemctl list-units 'readsb*' --no-legend

echo "=== JSON files ==="
find /run -name 'aircraft.json' -ls 2>/dev/null

echo "=== Listening ports ==="
ss -tlnp | grep readsb

echo "=== Config files ==="
ls -la /etc/default/readsb*

echo "=== Dashboard config ==="
cat /etc/readsb-feed-dashboard.conf 2>/dev/null || echo "No config file"

echo "=== Auto-detection ==="
readsb-feed-dashboard --dump-config
```

---

## Getting Help

If the above does not resolve your issue:

1. Run `readsb-feed-dashboard --dump-config` and save the output
2. Run `journalctl -u readsb* --no-pager -n 50` for service logs
3. Check the [GitHub Issues](https://github.com/Louis/readsb-feed-dashboard/issues)
