"""External feeder status collection (FR24, piaware, etc.)."""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


_VALID_CMD_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")


@dataclass
class FR24Status:
    """Parsed fr24feed-status output."""

    available: bool = False
    process_running: bool = False
    link_connected: bool = False
    link_mode: Optional[str] = None  # "UDP", "TCP", etc.
    radar_id: Optional[str] = None
    aircraft_tracked: Optional[int] = None
    aircraft_uploaded: Optional[int] = None
    service_active: Optional[str] = None


@dataclass
class ExternalFeeders:
    """Status of all detected external feeders."""

    fr24: Optional[FR24Status] = None


def collect_external_feeders() -> ExternalFeeders:
    """Detect and collect status from external feeders."""
    feeders = ExternalFeeders()
    feeders.fr24 = _collect_fr24()
    return feeders


def _collect_fr24() -> Optional[FR24Status]:
    """Collect fr24feed status if available."""
    # Check if fr24feed-status command exists
    if not _command_exists("fr24feed-status"):
        return None

    status = FR24Status(available=True)

    # Check systemd service
    status.service_active = _get_service_state("fr24feed")

    # Run fr24feed-status
    try:
        result = subprocess.run(
            ["fr24feed-status"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return status

    # Parse output
    for line in output.splitlines():
        line_lower = line.lower().strip()

        # Process status
        if "process" in line_lower:
            status.process_running = "running" in line_lower

        # Link status
        if "link" in line_lower:
            status.link_connected = "connected" in line_lower
            # Extract mode (UDP/TCP)
            mode_match = re.search(r"\[(UDP|TCP)\]", line, re.IGNORECASE)
            if mode_match:
                status.link_mode = mode_match.group(1).upper()

        # Radar ID
        if "radar" in line_lower:
            parts = line.split(":", 1)
            if len(parts) == 2:
                radar_val = parts[1].strip()
                if radar_val and radar_val != "---":
                    status.radar_id = radar_val

        # Aircraft tracked/uploaded
        if "aircraft" in line_lower and "tracked" in line_lower:
            num_match = re.search(r"(\d+)", line)
            if num_match:
                status.aircraft_tracked = int(num_match.group(1))

        if "aircraft" in line_lower and "uploaded" in line_lower:
            num_match = re.search(r"(\d+)", line)
            if num_match:
                status.aircraft_uploaded = int(num_match.group(1))

    # Also try parsing the monitor file if it exists
    _parse_fr24_monitor(status)

    return status


def _parse_fr24_monitor(status: FR24Status) -> None:
    """Try to parse /var/log/fr24feed/fr24feed.log or monitor JSON for extra stats."""
    monitor_path = Path("/run/fr24feed/fr24feed.json")
    if not monitor_path.exists():
        return

    try:
        import json
        with open(monitor_path, "r") as f:
            data = json.load(f)

        if isinstance(data, dict):
            if "aircraft_tracked" in data:
                status.aircraft_tracked = int(data["aircraft_tracked"])
            if "aircraft_uploaded" in data:
                status.aircraft_uploaded = int(data["aircraft_uploaded"])
    except (json.JSONDecodeError, PermissionError, OSError, ValueError, KeyError):
        pass


def _command_exists(cmd: str) -> bool:
    """Check if a command is available on PATH."""
    if not _VALID_CMD_NAME.match(cmd):
        return False
    try:
        result = subprocess.run(
            ["which", cmd],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _get_service_state(service: str) -> Optional[str]:
    """Get systemd service state."""
    if not _VALID_CMD_NAME.match(service):
        return None
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() or "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"
