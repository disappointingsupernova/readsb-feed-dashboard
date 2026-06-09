# Security Considerations

## Permissions

readsb-feed-dashboard is a **read-only monitoring tool**. It:

- Reads `aircraft.json` files (read-only)
- Queries systemd via `systemctl` (unprivileged operation)
- Queries network sockets via `ss` (unprivileged operation)
- Reads `/etc/default/readsb*` config files (read-only)

It does **not**:

- Modify any readsb configuration
- Restart or stop services
- Write to any system files
- Open network connections
- Send data anywhere

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

It contains no secrets — only paths, labels, and port numbers.
