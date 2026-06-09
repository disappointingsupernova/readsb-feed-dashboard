# Security Considerations

## Threat Model

readsb-feed-dashboard is a **read-only monitoring tool** intended to run on a local ADS-B receiver (typically a Raspberry Pi). The primary threats are:

1. A malicious config file causing unintended file reads or network requests
2. Disk exhaustion from unbounded logging
3. Supply chain attacks during installation
4. Information leakage via PID recycling

## Security Controls Implemented

### Input Validation

| Input | Validation | Rejection |
|---|---|---|
| Config file | Size limit (1 MB max) | Raises error if exceeded |
| `json_path` | Resolved via Path.resolve(), prefix check | Must be under `/run/`, `/tmp/`, or `/var/` |
| `json_url` | Scheme check, host check | Only http/https; blocks loopback, link-local, metadata endpoints |
| `service_name` | Regex: `^[a-zA-Z0-9][a-zA-Z0-9_.@-]*$` | Skipped if invalid |
| `/proc/PID/stat` | Process comm name verified as "readsb" | Skipped if process name doesn't match |

### SSRF Prevention

Remote feed URLs are validated before any network request:

- Only `http://` and `https://` schemes are permitted
- `file://`, `ftp://`, `gopher://` are rejected
- Loopback addresses (`127.x.x.x`, `::1`) are blocked
- Link-local addresses (`169.254.x.x`) are blocked
- Cloud metadata endpoints (`169.254.169.254`, `metadata.google.internal`) are blocked
- TLS verification uses an explicit `ssl.create_default_context()`

### Subprocess Safety

- All subprocess calls use list form (`["cmd", "arg"]`) — never `shell=True`
- Service names are validated against a strict regex before being passed to systemctl
- All subprocess calls have a 5-10 second timeout
- External command names (fr24feed-status) are validated before execution

### Disk Exhaustion Prevention

- CSV log files are automatically rotated when they reach 50 MB
- Old log is preserved as `.csv.old` (single rotation)
- Log write failures are silently ignored (non-critical feature)

### PID Recycling Protection

When reading `/proc/<pid>/stat` for CPU metrics, the process name (comm field) is verified to be "readsb" before reporting. This prevents leaking information about an unrelated process that received the same PID after a service restart.

### Supply Chain

- Dependencies are pinned to major version (`rich>=13.0,<14.0`)
- install.sh uses `--depth 1` clone (less history to tamper with)
- Post-clone integrity check verifies expected project structure
- Installation uses a dedicated venv (isolated from system packages)

## Permissions

The dashboard:

- Reads `aircraft.json` files (read-only)
- Reads `receiver.json` files (read-only)
- Queries systemd via `systemctl` (unprivileged operation)
- Queries network sockets via `ss` (unprivileged operation)
- Reads `/etc/default/readsb*` config files (read-only)
- Reads `/proc/<pid>/status` and `/proc/<pid>/stat` (read-only)
- Runs `fr24feed-status` if available (read-only)

It does **not**:

- Modify any readsb or feeder configuration
- Restart or stop services
- Write to any system files (except optional CSV log)
- Listen on network ports
- Send data anywhere (except fetching remote feed JSON)

## Running as Non-Root

The dashboard can run as a regular user provided:

1. The user has read access to `/run/readsb*/aircraft.json`
2. The user can execute `systemctl is-active`
3. The user can execute `ss -tlnp`

On most systems, items 2 and 3 work for any user. Item 1 depends on the file permissions set by readsb.

### Common Permission Scenarios

| Owner:Group | Permissions | Non-root access? |
|---|---|---|
| `readsb:nogroup` | `644` | Yes |
| `readsb:nogroup` | `640` | No — needs group membership or root |
| `readsb:readsb` | `640` | Add user to `readsb` group |

### Granting Access

```bash
# Option 1: Make files world-readable (simplest)
sudo chmod o+r /run/readsb*/aircraft.json

# Option 2: Add user to the readsb group (if applicable)
sudo usermod -aG readsb $USER
# Then log out and back in

# Option 3: Run as root
sudo readsb-feed-dashboard
```

## Config File Security

The config file at `/etc/readsb-feed-dashboard.conf` should be readable by the user running the dashboard:

```bash
sudo chmod 644 /etc/readsb-feed-dashboard.conf
```

It contains no secrets — only paths, labels, and port numbers. Receiver lat/lon is semi-sensitive (reveals location) but is typically already public via ADS-B exchange sites.
