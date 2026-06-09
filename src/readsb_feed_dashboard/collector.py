"""Data collection module — reads JSON, queries systemd, detects ports, computes metrics."""

import json
import math
import os
import subprocess
import time
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import re

from .config import AlertConfig, DashboardConfig, FeedConfig

_VALID_SERVICE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.@-]*$")


@dataclass
class AircraftEntry:
    """A single aircraft record."""

    hex: str
    flight: Optional[str] = None
    alt_baro: Optional[int] = None
    gs: Optional[float] = None
    rssi: Optional[float] = None
    squawk: Optional[str] = None
    seen: Optional[float] = None
    distance: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    ac_type: Optional[str] = None  # adsb_icao, mlat, tisb, mode_s, etc.


@dataclass
class RSSIStats:
    """Signal strength statistics for a feed."""

    min_rssi: Optional[float] = None
    max_rssi: Optional[float] = None
    avg_rssi: Optional[float] = None


@dataclass
class DistanceRings:
    """Aircraft counts by distance band."""

    within_50nm: int = 0
    within_100nm: int = 0
    within_150nm: int = 0
    within_200nm: int = 0
    beyond_200nm: int = 0


@dataclass
class TypeBreakdown:
    """Aircraft counts by message type."""

    adsb_icao: int = 0
    mlat: int = 0
    tisb: int = 0
    mode_s: int = 0
    other: int = 0


@dataclass
class ProcessStats:
    """CPU and memory stats for a service process."""

    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    pid: Optional[int] = None


@dataclass
class NetworkStats:
    """Network I/O stats for a service process."""

    bytes_rx: Optional[int] = None
    bytes_tx: Optional[int] = None


@dataclass
class Alert:
    """A triggered alert."""

    feed_label: str
    message: str
    severity: str = "warning"  # "warning" or "critical"


@dataclass
class FeedData:
    """Collected data for a single feed."""

    config: FeedConfig
    aircraft: list[AircraftEntry] = field(default_factory=list)
    aircraft_count: int = 0
    aircraft_count_delta: Optional[int] = None
    position_tracked: int = 0
    hex_set: set[str] = field(default_factory=set)
    json_exists: bool = False
    json_stale: bool = False
    json_mtime: Optional[float] = None
    json_error: Optional[str] = None
    service_active: Optional[str] = None
    service_uptime: Optional[str] = None
    listening_ports: list[str] = field(default_factory=list)
    messages_total: Optional[int] = None
    messages_rate: Optional[float] = None
    rssi_stats: RSSIStats = field(default_factory=RSSIStats)
    distance_rings: DistanceRings = field(default_factory=DistanceRings)
    type_breakdown: TypeBreakdown = field(default_factory=TypeBreakdown)
    process_stats: ProcessStats = field(default_factory=ProcessStats)
    network_stats: NetworkStats = field(default_factory=NetworkStats)
    alerts: list[Alert] = field(default_factory=list)
    farthest_aircraft: Optional[AircraftEntry] = None
    max_range_session: Optional[float] = None
    recently_lost: list[str] = field(default_factory=list)


class FeedHistory:
    """Maintains historical data for sparklines and rate calculations."""

    def __init__(self, max_length: int = 60):
        self._max_length = max_length
        self._aircraft_counts: dict[str, deque] = {}
        self._message_counts: dict[str, tuple[Optional[int], Optional[float]]] = {}
        self._network_prev: dict[str, tuple[Optional[int], Optional[int], float]] = {}
        self._max_range: dict[str, float] = {}
        self._prev_hex_sets: dict[str, set[str]] = {}
        self._prev_aircraft_counts: dict[str, int] = {}

    def update_aircraft_count(self, feed_label: str, count: int) -> None:
        """Record aircraft count for sparkline."""
        if feed_label not in self._aircraft_counts:
            self._aircraft_counts[feed_label] = deque(maxlen=self._max_length)
        self._aircraft_counts[feed_label].append(count)

    def get_sparkline_data(self, feed_label: str) -> list[int]:
        """Get sparkline data for a feed."""
        return list(self._aircraft_counts.get(feed_label, []))

    def compute_message_rate(self, feed_label: str, messages: Optional[int]) -> Optional[float]:
        """Compute messages/sec from delta between cycles."""
        if messages is None:
            return None

        now = time.time()
        prev = self._message_counts.get(feed_label)
        self._message_counts[feed_label] = (messages, now)

        if prev is None or prev[0] is None or prev[1] is None:
            return None

        prev_messages, prev_time = prev
        dt = now - prev_time
        if dt <= 0:
            return None

        delta = messages - prev_messages
        if delta < 0:
            # Service restarted, counter reset
            return None

        return delta / dt

    def update_max_range(self, feed_label: str, distance: float) -> float:
        """Update and return the max range seen this session."""
        current = self._max_range.get(feed_label, 0.0)
        if distance > current:
            self._max_range[feed_label] = distance
            return distance
        return current

    def get_max_range(self, feed_label: str) -> Optional[float]:
        """Get the session max range for a feed."""
        return self._max_range.get(feed_label)

    def compute_count_delta(self, feed_label: str, count: int) -> Optional[int]:
        """Compute aircraft count change since last cycle."""
        prev = self._prev_aircraft_counts.get(feed_label)
        self._prev_aircraft_counts[feed_label] = count
        if prev is None:
            return None
        return count - prev

    def compute_recently_lost(self, feed_label: str, current_hex: set[str]) -> list[str]:
        """Return hex codes that were in the previous cycle but not this one."""
        prev = self._prev_hex_sets.get(feed_label, set())
        self._prev_hex_sets[feed_label] = current_hex.copy()
        return sorted(prev - current_hex)[:10]  # Cap at 10

    def update_network(self, feed_label: str, rx: Optional[int], tx: Optional[int]) -> tuple[Optional[int], Optional[int]]:
        """Compute network bytes/sec delta."""
        if rx is None or tx is None:
            return None, None

        now = time.time()
        prev = self._network_prev.get(feed_label)
        self._network_prev[feed_label] = (rx, tx, now)

        if prev is None:
            return None, None

        prev_rx, prev_tx, prev_time = prev
        dt = now - prev_time
        if dt <= 0 or prev_rx is None or prev_tx is None:
            return None, None

        rx_rate = int((rx - prev_rx) / dt) if rx >= prev_rx else None
        tx_rate = int((tx - prev_tx) / dt) if tx >= prev_tx else None
        return rx_rate, tx_rate


# Module-level history instance
_history = FeedHistory()


def init_history(sparkline_length: int = 60) -> None:
    """Re-initialise the history with a given sparkline length."""
    global _history
    _history = FeedHistory(max_length=sparkline_length)


def get_history() -> FeedHistory:
    """Get the module-level history instance."""
    return _history


def collect_feed_data(feed_config: FeedConfig, config: DashboardConfig) -> FeedData:
    """Collect all data for a single feed."""
    data = FeedData(config=feed_config)

    _read_json(data, config.stale_threshold)
    _compute_rssi_stats(data)
    _compute_distance_rings(data)
    _compute_type_breakdown(data)
    _check_service(data)
    _check_uptime(data)
    _check_ports_cached(data)
    _check_process_stats(data)
    _check_network_stats(data)

    # Message rate
    data.messages_rate = _history.compute_message_rate(
        feed_config.label, data.messages_total
    )

    # Sparkline
    _history.update_aircraft_count(feed_config.label, data.aircraft_count)

    # Aircraft count delta
    data.aircraft_count_delta = _history.compute_count_delta(
        feed_config.label, data.aircraft_count
    )

    # Recently lost aircraft
    data.recently_lost = _history.compute_recently_lost(
        feed_config.label, data.hex_set
    )

    # Farthest aircraft and max range
    _compute_farthest(data)

    # Alerts
    _check_alerts(data)

    return data


def _read_json(data: FeedData, stale_threshold: float) -> None:
    """Read and parse the aircraft.json file for a feed."""
    raw = None

    # Remote feed support
    if data.config.json_url:
        raw = _fetch_remote_json(data)
        if raw is None:
            return
    else:
        raw = _read_local_json(data, stale_threshold)
        if raw is None:
            return

    if not isinstance(raw, dict) or "aircraft" not in raw:
        data.json_error = "Missing 'aircraft' key"
        return

    # Extract total messages count
    data.messages_total = raw.get("messages") if isinstance(raw.get("messages"), (int, float)) else None

    aircraft_list = raw.get("aircraft", [])
    if not isinstance(aircraft_list, list):
        data.json_error = "Invalid 'aircraft' field"
        return

    # Try to get receiver position for distance calculation
    receiver_lat, receiver_lon = _get_receiver_position(data)

    for ac in aircraft_list:
        if not isinstance(ac, dict):
            continue
        hex_code = ac.get("hex", "").strip()
        if not hex_code:
            continue

        ac_lat = ac.get("lat") if isinstance(ac.get("lat"), (int, float)) else None
        ac_lon = ac.get("lon") if isinstance(ac.get("lon"), (int, float)) else None

        # Distance: use r_dst if available, otherwise compute from lat/lon
        distance = None
        if isinstance(ac.get("r_dst"), (int, float)):
            distance = ac.get("r_dst")
        elif ac_lat is not None and ac_lon is not None and receiver_lat is not None and receiver_lon is not None:
            distance = _haversine_nm(receiver_lat, receiver_lon, ac_lat, ac_lon)

        entry = AircraftEntry(
            hex=hex_code,
            flight=ac.get("flight", "").strip() or None,
            alt_baro=ac.get("alt_baro") if isinstance(ac.get("alt_baro"), (int, float)) else None,
            gs=ac.get("gs") if isinstance(ac.get("gs"), (int, float)) else None,
            rssi=ac.get("rssi") if isinstance(ac.get("rssi"), (int, float)) else None,
            squawk=ac.get("squawk") if isinstance(ac.get("squawk"), str) else None,
            seen=ac.get("seen") if isinstance(ac.get("seen"), (int, float)) else None,
            distance=distance,
            lat=ac_lat,
            lon=ac_lon,
            ac_type=ac.get("type") if isinstance(ac.get("type"), str) else None,
        )
        data.aircraft.append(entry)
        data.hex_set.add(hex_code)

        if entry.lat is not None and entry.lon is not None:
            data.position_tracked += 1

    data.aircraft_count = len(data.aircraft)
    data.json_exists = True


def _read_local_json(data: FeedData, stale_threshold: float) -> Optional[dict]:
    """Read a local aircraft.json file."""
    json_path = Path(data.config.json_path)

    # Path traversal protection: resolve symlinks and verify safe prefix
    try:
        resolved = json_path.resolve()
    except (OSError, RuntimeError):
        data.json_exists = False
        data.json_error = "Cannot resolve path"
        return None

    allowed_prefixes = ("/run/", "/tmp/", "/var/")
    if not any(str(resolved).startswith(p) for p in allowed_prefixes):
        data.json_exists = False
        data.json_error = f"Path outside allowed directories: {resolved}"
        return None

    if not resolved.exists():
        data.json_exists = False
        data.json_error = "File not found"
        return None

    data.json_exists = True

    try:
        stat = resolved.stat()
        data.json_mtime = stat.st_mtime
        age = time.time() - stat.st_mtime
        data.json_stale = age > stale_threshold
    except OSError as e:
        data.json_error = f"Cannot stat: {e}"
        return None

    try:
        with open(resolved, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        data.json_error = f"Malformed JSON: {e}"
        return None
    except (PermissionError, OSError) as e:
        data.json_error = f"Read error: {e}"
        return None


def _get_receiver_position(data: FeedData) -> tuple[Optional[float], Optional[float]]:
    """Try to get receiver lat/lon from config, then receiver.json, then sibling dirs."""
    # Check config first
    if data.config.receiver_lat is not None and data.config.receiver_lon is not None:
        return data.config.receiver_lat, data.config.receiver_lon

    # Try receiver.json adjacent to this feed's aircraft.json
    if data.config.json_path:
        result = _read_receiver_json(Path(data.config.json_path).parent / "receiver.json")
        if result:
            return result

    # Fall back to any sibling /run/readsb* directory that has receiver.json
    for candidate in ["/run/readsb", "/run/readsb-merge", "/run/readsb-sdr1", "/run/readsb-sdr2"]:
        result = _read_receiver_json(Path(candidate) / "receiver.json")
        if result:
            return result

    return None, None


def _read_receiver_json(path: Path) -> Optional[tuple[float, float]]:
    """Read lat/lon from a receiver.json file."""
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            rdata = json.load(f)
        lat = rdata.get("lat") if isinstance(rdata.get("lat"), (int, float)) else None
        lon = rdata.get("lon") if isinstance(rdata.get("lon"), (int, float)) else None
        if lat is not None and lon is not None:
            return lat, lon
    except (json.JSONDecodeError, PermissionError, OSError):
        pass
    return None


def _haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in nautical miles between two points."""
    R_NM = 3440.065  # Earth radius in nautical miles
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R_NM * c


def _validate_url(url: str) -> Optional[str]:
    """Validate a remote feed URL. Returns error string or None if valid."""
    from urllib.parse import urlparse
    import ipaddress

    parsed = urlparse(url)

    # Scheme must be http or https only
    if parsed.scheme not in ("http", "https"):
        return f"Unsupported URL scheme: {parsed.scheme} (only http/https allowed)"

    # Reject obviously dangerous hosts
    hostname = parsed.hostname or ""
    if not hostname:
        return "URL has no hostname"

    # Block metadata endpoints and loopback
    blocked_hosts = {"169.254.169.254", "metadata.google.internal"}
    if hostname in blocked_hosts:
        return f"Blocked host: {hostname}"

    # Check if hostname is an IP and block link-local/loopback
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_loopback or addr.is_link_local:
            return f"Blocked address: {hostname} (loopback/link-local)"
    except ValueError:
        # Not an IP literal — that's fine, it's a hostname
        pass

    return None


def _fetch_remote_json(data: FeedData) -> Optional[dict]:
    """Fetch aircraft.json from a remote HTTP endpoint."""
    import ssl

    url = data.config.json_url

    # Validate URL before fetching
    url_error = _validate_url(url)
    if url_error:
        data.json_exists = False
        data.json_error = url_error
        return None

    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "readsb-feed-dashboard"})
        with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
            raw = json.loads(resp.read())
        data.json_exists = True
        data.json_stale = False
        return raw
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        data.json_exists = False
        data.json_error = f"Remote fetch failed: {e}"
        return None


def _compute_rssi_stats(data: FeedData) -> None:
    """Compute min/avg/max RSSI for the feed."""
    rssi_values = [ac.rssi for ac in data.aircraft if ac.rssi is not None]
    if rssi_values:
        data.rssi_stats = RSSIStats(
            min_rssi=min(rssi_values),
            max_rssi=max(rssi_values),
            avg_rssi=sum(rssi_values) / len(rssi_values),
        )


def _compute_distance_rings(data: FeedData) -> None:
    """Compute aircraft counts by distance band."""
    rings = DistanceRings()
    for ac in data.aircraft:
        if ac.distance is None:
            continue
        if ac.distance <= 50:
            rings.within_50nm += 1
        elif ac.distance <= 100:
            rings.within_100nm += 1
        elif ac.distance <= 150:
            rings.within_150nm += 1
        elif ac.distance <= 200:
            rings.within_200nm += 1
        else:
            rings.beyond_200nm += 1
    data.distance_rings = rings


def _compute_type_breakdown(data: FeedData) -> None:
    """Compute aircraft counts by message type."""
    tb = TypeBreakdown()
    for ac in data.aircraft:
        if ac.ac_type is None:
            tb.other += 1
        elif "adsb" in ac.ac_type:
            tb.adsb_icao += 1
        elif "mlat" in ac.ac_type:
            tb.mlat += 1
        elif "tisb" in ac.ac_type:
            tb.tisb += 1
        elif "mode_s" in ac.ac_type or ac.ac_type == "mode_s":
            tb.mode_s += 1
        else:
            tb.other += 1
    data.type_breakdown = tb


def _check_service(data: FeedData) -> None:
    """Check systemd service status."""
    svc = data.config.service_name
    if not svc:
        data.service_active = "unknown"
        return

    if not _VALID_SERVICE_NAME.match(svc):
        data.service_active = "invalid name"
        return

    try:
        result = subprocess.run(
            ["systemctl", "is-active", svc],
            capture_output=True, text=True, timeout=5
        )
        data.service_active = result.stdout.strip() or "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        data.service_active = "unknown"


def _check_uptime(data: FeedData) -> None:
    """Get service uptime from systemd."""
    svc = data.config.service_name
    if not svc or not _VALID_SERVICE_NAME.match(svc):
        return

    try:
        result = subprocess.run(
            ["systemctl", "show", svc, "--property=ActiveEnterTimestamp", "--value"],
            capture_output=True, text=True, timeout=5
        )
        timestamp_str = result.stdout.strip()
        if not timestamp_str:
            return

        # Parse systemd timestamp (e.g. "Mon 2025-01-15 10:30:00 GMT")
        from datetime import datetime
        # systemd outputs various formats; use a simple approach
        result2 = subprocess.run(
            ["systemctl", "show", svc, "--property=ActiveEnterTimestampMonotonic", "--value"],
            capture_output=True, text=True, timeout=5
        )
        mono_usec = result2.stdout.strip()
        if mono_usec and mono_usec != "0":
            # Get system uptime to compute service uptime
            try:
                with open("/proc/uptime", "r") as f:
                    system_uptime_sec = float(f.read().split()[0])
                mono_sec = int(mono_usec) / 1_000_000
                service_uptime_sec = system_uptime_sec - mono_sec
                if service_uptime_sec < 0:
                    service_uptime_sec = 0
                data.service_uptime = _format_duration(service_uptime_sec)
            except (OSError, ValueError):
                data.service_uptime = timestamp_str
        else:
            data.service_uptime = timestamp_str
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def _format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m {seconds % 60}s"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h {minutes % 60}m"
    days = hours // 24
    return f"{days}d {hours % 24}h"


# Port detection cache
_port_cache: dict[str, tuple[float, list[str]]] = {}
_PORT_CACHE_TTL = 30.0  # Refresh ports every 30 seconds


def _check_ports_cached(data: FeedData) -> None:
    """Detect listening ports with caching."""
    svc = data.config.service_name
    if not svc or not _VALID_SERVICE_NAME.match(svc):
        return

    now = time.time()
    cached = _port_cache.get(svc)
    if cached and (now - cached[0]) < _PORT_CACHE_TTL:
        data.listening_ports = cached[1]
        return

    ports = _detect_ports_for_service(svc)
    _port_cache[svc] = (now, ports)
    data.listening_ports = ports


def _detect_ports_for_service(svc: str) -> list[str]:
    """Detect listening ports for a given service."""
    try:
        result = subprocess.run(
            ["systemctl", "show", svc, "--property=MainPID", "--value"],
            capture_output=True, text=True, timeout=5
        )
        pid = result.stdout.strip()
        if not pid or pid == "0":
            return []

        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True, text=True, timeout=5
        )
        ports = []
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if f"pid={pid}" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        ports.append(parts[3])
        return ports
    except (subprocess.TimeoutExpired, FileNotFoundError, IndexError):
        return []


def _check_process_stats(data: FeedData) -> None:
    """Get CPU and memory usage for the service process."""
    svc = data.config.service_name
    if not svc or not _VALID_SERVICE_NAME.match(svc):
        return

    try:
        result = subprocess.run(
            ["systemctl", "show", svc, "--property=MainPID", "--value"],
            capture_output=True, text=True, timeout=5
        )
        pid_str = result.stdout.strip()
        if not pid_str or pid_str == "0":
            return

        pid = int(pid_str)
        data.process_stats.pid = pid

        # Memory from /proc/PID/status
        status_path = Path(f"/proc/{pid}/status")
        if status_path.exists():
            with open(status_path, "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        # VmRSS is in kB
                        kb = int(line.split()[1])
                        data.process_stats.memory_mb = kb / 1024.0
                        break

        # CPU from /proc/PID/stat — rough percentage
        # Verify process name to guard against PID recycling (TOCTOU)
        stat_path = Path(f"/proc/{pid}/stat")
        if stat_path.exists():
            with open(stat_path, "r") as f:
                stat_content = f.read()
            fields = stat_content.split()
            if len(fields) > 14:
                # fields[1] is (comm) — verify it's readsb
                comm = fields[1].strip("()")
                if comm != "readsb":
                    return
                utime = int(fields[13])
                stime = int(fields[14])
                total_ticks = utime + stime
                hz = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
                with open("/proc/uptime", "r") as f:
                    uptime = float(f.read().split()[0])
                if uptime > 0:
                    data.process_stats.cpu_percent = (total_ticks / hz / uptime) * 100.0

    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, OSError):
        pass


def _check_network_stats(data: FeedData) -> None:
    """Get network I/O bytes for the service process."""
    pid = data.process_stats.pid
    if not pid:
        return

    try:
        net_path = Path(f"/proc/{pid}/net/dev")
        if not net_path.exists():
            return

        total_rx = 0
        total_tx = 0
        with open(net_path, "r") as f:
            for line in f:
                line = line.strip()
                if ":" not in line or line.startswith("Inter") or line.startswith("face"):
                    continue
                parts = line.split()
                if len(parts) >= 10:
                    # Skip loopback
                    iface = parts[0].rstrip(":")
                    if iface == "lo":
                        continue
                    total_rx += int(parts[1])
                    total_tx += int(parts[9])

        rx_rate, tx_rate = _history.update_network(data.config.label, total_rx, total_tx)
        data.network_stats = NetworkStats(bytes_rx=rx_rate, bytes_tx=tx_rate)
    except (OSError, ValueError, IndexError):
        pass


def _compute_farthest(data: FeedData) -> None:
    """Find the farthest aircraft and update session max range."""
    farthest = None
    max_dist = 0.0
    for ac in data.aircraft:
        if ac.distance is not None and ac.distance > max_dist:
            max_dist = ac.distance
            farthest = ac

    data.farthest_aircraft = farthest
    if max_dist > 0:
        data.max_range_session = _history.update_max_range(data.config.label, max_dist)
    else:
        data.max_range_session = _history.get_max_range(data.config.label)


@dataclass
class SystemInfo:
    """Host system information."""

    hostname: Optional[str] = None
    uptime: Optional[str] = None
    cpu_temp: Optional[float] = None
    disk_free_run: Optional[str] = None
    kernel: Optional[str] = None


def collect_system_info() -> SystemInfo:
    """Collect host system information."""
    info = SystemInfo()

    # Hostname
    try:
        info.hostname = Path("/etc/hostname").read_text().strip()
    except OSError:
        pass

    # Uptime
    try:
        with open("/proc/uptime", "r") as f:
            secs = float(f.read().split()[0])
        info.uptime = _format_duration(secs)
    except (OSError, ValueError):
        pass

    # CPU temperature (Raspberry Pi)
    try:
        temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
        if temp_path.exists():
            millideg = int(temp_path.read_text().strip())
            info.cpu_temp = millideg / 1000.0
    except (OSError, ValueError):
        pass

    # Disk free on /run
    try:
        result = subprocess.run(
            ["df", "-h", "--output=avail", "/run"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().splitlines()
        if len(lines) >= 2:
            info.disk_free_run = lines[1].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Kernel
    try:
        info.kernel = Path("/proc/version").read_text().split()[2]
    except (OSError, IndexError):
        pass

    return info


def _check_alerts(data: FeedData) -> None:
    """Check threshold alerts for a feed."""
    alerts_config = data.config.alerts
    if not alerts_config:
        # Use defaults
        alerts_config = AlertConfig()

    if alerts_config.min_aircraft is not None:
        if data.aircraft_count < alerts_config.min_aircraft:
            data.alerts.append(Alert(
                feed_label=data.config.label,
                message=f"Aircraft count ({data.aircraft_count}) below threshold ({alerts_config.min_aircraft})",
                severity="warning",
            ))

    if alerts_config.alert_on_service_inactive:
        if data.service_active in ("inactive", "failed"):
            data.alerts.append(Alert(
                feed_label=data.config.label,
                message=f"Service is {data.service_active}",
                severity="critical",
            ))

    if alerts_config.alert_on_stale_json:
        if data.json_stale:
            data.alerts.append(Alert(
                feed_label=data.config.label,
                message="JSON data is stale",
                severity="warning",
            ))


def compute_overlaps(feeds: list[FeedData]) -> dict:
    """Compute aircraft overlap statistics between feeds.

    For 'unique_to', we compare SDR feeds against other SDR feeds only
    (excluding merge feeds from the comparison). This way 'unique' means
    'seen by this SDR but not by any other SDR'.

    Returns a dict with:
      - unique_to[i]: count of aircraft only seen by this SDR (not other SDRs)
      - shared[i][j]: count of aircraft seen by both feed i and j
      - total_unique: total unique hex codes across all feeds
    """
    result = {
        "unique_to": {},
        "shared": {},
        "total_unique": 0,
    }

    all_hex = set()
    for feed in feeds:
        all_hex.update(feed.hex_set)
    result["total_unique"] = len(all_hex)

    # Identify SDR-only feeds for unique calculation
    sdr_indices = [i for i, f in enumerate(feeds) if f.config.feed_type != "merge"]

    for i, feed_i in enumerate(feeds):
        if feed_i.config.feed_type == "merge":
            # For merge feeds, unique = aircraft not in any SDR (should be 0 normally)
            sdr_hex = set()
            for j in sdr_indices:
                sdr_hex.update(feeds[j].hex_set)
            result["unique_to"][i] = len(feed_i.hex_set - sdr_hex)
        else:
            # For SDR feeds, unique = aircraft not seen by any other SDR
            other_sdr_hex = set()
            for j in sdr_indices:
                if j != i:
                    other_sdr_hex.update(feeds[j].hex_set)
            result["unique_to"][i] = len(feed_i.hex_set - other_sdr_hex)

    # Shared is pairwise between all feeds
    for i in range(len(feeds)):
        result["shared"][i] = {}
        for j in range(len(feeds)):
            if i != j:
                result["shared"][i][j] = len(feeds[i].hex_set & feeds[j].hex_set)

    return result


