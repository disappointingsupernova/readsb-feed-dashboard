"""Data collection module — reads JSON, queries systemd, detects ports."""

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import FeedConfig


@dataclass
class AircraftEntry:
    """A single aircraft record."""

    hex: str
    alt_baro: Optional[int] = None
    gs: Optional[float] = None
    rssi: Optional[float] = None
    squawk: Optional[str] = None
    flight: Optional[str] = None
    seen: Optional[float] = None
    distance: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


@dataclass
class FeedData:
    """Collected data for a single feed."""

    config: FeedConfig
    aircraft: list[AircraftEntry] = field(default_factory=list)
    aircraft_count: int = 0
    hex_set: set[str] = field(default_factory=set)
    json_exists: bool = False
    json_stale: bool = False
    json_mtime: Optional[float] = None
    json_error: Optional[str] = None
    service_active: Optional[str] = None  # "active", "inactive", "failed", etc.
    listening_ports: list[str] = field(default_factory=list)


def collect_feed_data(feed_config: FeedConfig) -> FeedData:
    """Collect all data for a single feed."""
    data = FeedData(config=feed_config)

    _read_json(data)
    _check_service(data)
    _check_ports(data)

    return data


def _read_json(data: FeedData) -> None:
    """Read and parse the aircraft.json file for a feed."""
    json_path = Path(data.config.json_path)

    if not json_path.exists():
        data.json_exists = False
        data.json_error = "File not found"
        return

    data.json_exists = True

    # Check staleness
    try:
        stat = json_path.stat()
        data.json_mtime = stat.st_mtime
        age = time.time() - stat.st_mtime
        data.json_stale = age > 10.0  # Stale if older than 10 seconds
    except OSError as e:
        data.json_error = f"Cannot stat: {e}"
        return

    # Parse JSON
    try:
        with open(json_path, "r") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        data.json_error = f"Malformed JSON: {e}"
        return
    except (PermissionError, OSError) as e:
        data.json_error = f"Read error: {e}"
        return

    if not isinstance(raw, dict) or "aircraft" not in raw:
        data.json_error = "Missing 'aircraft' key"
        return

    aircraft_list = raw.get("aircraft", [])
    if not isinstance(aircraft_list, list):
        data.json_error = "Invalid 'aircraft' field"
        return

    for ac in aircraft_list:
        if not isinstance(ac, dict):
            continue
        hex_code = ac.get("hex", "").strip()
        if not hex_code:
            continue

        entry = AircraftEntry(
            hex=hex_code,
            alt_baro=ac.get("alt_baro") if isinstance(ac.get("alt_baro"), (int, float)) else None,
            gs=ac.get("gs") if isinstance(ac.get("gs"), (int, float)) else None,
            rssi=ac.get("rssi") if isinstance(ac.get("rssi"), (int, float)) else None,
            squawk=ac.get("squawk") if isinstance(ac.get("squawk"), str) else None,
            flight=ac.get("flight", "").strip() or None,
            seen=ac.get("seen") if isinstance(ac.get("seen"), (int, float)) else None,
            distance=ac.get("r_dst") if isinstance(ac.get("r_dst"), (int, float)) else None,
            lat=ac.get("lat") if isinstance(ac.get("lat"), (int, float)) else None,
            lon=ac.get("lon") if isinstance(ac.get("lon"), (int, float)) else None,
        )
        data.aircraft.append(entry)
        data.hex_set.add(hex_code)

    data.aircraft_count = len(data.aircraft)


def _check_service(data: FeedData) -> None:
    """Check systemd service status."""
    svc = data.config.service_name
    if not svc:
        data.service_active = "unknown"
        return

    try:
        result = subprocess.run(
            ["systemctl", "is-active", svc],
            capture_output=True, text=True, timeout=5
        )
        data.service_active = result.stdout.strip() or "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        data.service_active = "unknown"


def _check_ports(data: FeedData) -> None:
    """Detect listening ports associated with this feed's service."""
    svc = data.config.service_name
    if not svc:
        return

    # Use ss to find listening ports for the process
    try:
        # First get the PID of the main process
        result = subprocess.run(
            ["systemctl", "show", svc, "--property=MainPID", "--value"],
            capture_output=True, text=True, timeout=5
        )
        pid = result.stdout.strip()
        if not pid or pid == "0":
            return

        # Now find ports for that PID
        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if f"pid={pid}" in line:
                    # Extract local address:port
                    parts = line.split()
                    if len(parts) >= 4:
                        local_addr = parts[3]
                        data.listening_ports.append(local_addr)
    except (subprocess.TimeoutExpired, FileNotFoundError, IndexError):
        pass


def compute_overlaps(feeds: list[FeedData]) -> dict:
    """Compute aircraft overlap statistics between feeds.

    Returns a dict with:
      - unique_to[i]: count of aircraft only seen by feed i
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

    for i, feed_i in enumerate(feeds):
        others = set()
        for j, feed_j in enumerate(feeds):
            if i != j:
                others.update(feed_j.hex_set)
        result["unique_to"][i] = len(feed_i.hex_set - others)

    for i in range(len(feeds)):
        result["shared"][i] = {}
        for j in range(len(feeds)):
            if i != j:
                result["shared"][i][j] = len(feeds[i].hex_set & feeds[j].hex_set)

    return result
