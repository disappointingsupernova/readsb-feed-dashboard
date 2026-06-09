"""Configuration management for readsb-feed-dashboard."""

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


CONFIG_PATHS = [
    Path("/etc/readsb-feed-dashboard.conf"),
    Path.home() / ".config" / "readsb-feed-dashboard" / "config.json",
]

DEFAULT_JSON_DIRS = [
    "/run/readsb",
    "/run/readsb-sdr1",
    "/run/readsb-sdr2",
    "/run/readsb-sdr3",
    "/run/readsb-sdr4",
    "/run/readsb-merge",
]

DEFAULT_SERVICE_NAMES = [
    "readsb",
    "readsb-sdr1",
    "readsb-sdr2",
    "readsb-sdr3",
    "readsb-sdr4",
    "readsb-merge",
]


@dataclass
class FeedConfig:
    """Configuration for a single feed."""

    label: str
    json_path: str
    service_name: Optional[str] = None
    feed_type: str = "sdr"  # "sdr" or "merge"
    beast_port: Optional[int] = None
    sbs_port: Optional[int] = None
    serial: Optional[str] = None


@dataclass
class DashboardConfig:
    """Top-level dashboard configuration."""

    feeds: list[FeedConfig] = field(default_factory=list)
    refresh_interval: float = 2.0
    unicode_mode: bool = True
    max_aircraft_rows: int = 10
    show_ports: bool = True
    show_service_status: bool = True
    title: str = "readsb Multi-Feed Dashboard"

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "DashboardConfig":
        """Load configuration from file, or auto-detect if no config exists."""
        if config_path:
            path = Path(config_path)
            if path.exists():
                return cls._from_file(path)
            raise FileNotFoundError(f"Config file not found: {config_path}")

        for path in CONFIG_PATHS:
            if path.exists():
                return cls._from_file(path)

        # Auto-detect
        return cls._auto_detect()

    @classmethod
    def _from_file(cls, path: Path) -> "DashboardConfig":
        """Parse a JSON config file."""
        with open(path, "r") as f:
            data = json.load(f)

        feeds = []
        for fd in data.get("feeds", []):
            feeds.append(FeedConfig(
                label=fd["label"],
                json_path=fd["json_path"],
                service_name=fd.get("service_name"),
                feed_type=fd.get("feed_type", "sdr"),
                beast_port=fd.get("beast_port"),
                sbs_port=fd.get("sbs_port"),
                serial=fd.get("serial"),
            ))

        return cls(
            feeds=feeds,
            refresh_interval=data.get("refresh_interval", 2.0),
            unicode_mode=data.get("unicode_mode", True),
            max_aircraft_rows=data.get("max_aircraft_rows", 10),
            show_ports=data.get("show_ports", True),
            show_service_status=data.get("show_service_status", True),
            title=data.get("title", "readsb Multi-Feed Dashboard"),
        )

    @classmethod
    def _auto_detect(cls) -> "DashboardConfig":
        """Auto-detect readsb feeds from the system."""
        feeds = []

        # Detect JSON directories
        for json_dir in DEFAULT_JSON_DIRS:
            json_path = Path(json_dir) / "aircraft.json"
            if json_path.exists():
                label = _derive_label(json_dir)
                service_name = _derive_service_name(json_dir)
                feed_type = "merge" if "merge" in json_dir or json_dir == "/run/readsb" else "sdr"
                serial = _detect_serial(service_name)
                beast_port, sbs_port = _detect_ports(service_name)

                feeds.append(FeedConfig(
                    label=label,
                    json_path=str(json_path),
                    service_name=service_name,
                    feed_type=feed_type,
                    beast_port=beast_port,
                    sbs_port=sbs_port,
                    serial=serial,
                ))

        # Also scan for any systemd readsb services we may have missed
        discovered_services = _discover_systemd_services()
        for svc in discovered_services:
            run_dir = f"/run/{svc}"
            json_path = Path(run_dir) / "aircraft.json"
            if json_path.exists():
                already_added = any(f.json_path == str(json_path) for f in feeds)
                if not already_added:
                    feed_type = "merge" if "merge" in svc else "sdr"
                    serial = _detect_serial(svc)
                    beast_port, sbs_port = _detect_ports(svc)
                    feeds.append(FeedConfig(
                        label=svc.replace("readsb-", "").replace("readsb", "default").upper(),
                        json_path=str(json_path),
                        service_name=svc,
                        feed_type=feed_type,
                        beast_port=beast_port,
                        sbs_port=sbs_port,
                        serial=serial,
                    ))

        config = cls(feeds=feeds)

        # Determine unicode support
        config.unicode_mode = _check_unicode_support()

        return config


def _derive_label(json_dir: str) -> str:
    """Derive a human-readable label from a JSON directory path."""
    dirname = Path(json_dir).name
    if dirname == "readsb":
        return "MERGED"
    return dirname.replace("readsb-", "").upper()


def _derive_service_name(json_dir: str) -> Optional[str]:
    """Derive the systemd service name from a JSON directory path."""
    dirname = Path(json_dir).name
    # Check if a service with this name exists
    try:
        result = subprocess.run(
            ["systemctl", "cat", dirname],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            return dirname
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return dirname


def _discover_systemd_services() -> list[str]:
    """Discover all readsb-related systemd services."""
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all", "--no-legend"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            services = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if parts:
                    svc_name = parts[0].replace(".service", "")
                    if svc_name.startswith("readsb"):
                        services.append(svc_name)
            return services
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []


def _detect_serial(service_name: Optional[str]) -> Optional[str]:
    """Attempt to detect the RTL-SDR serial from the service config."""
    if not service_name:
        return None

    config_paths = [
        f"/etc/default/{service_name}",
        "/etc/default/readsb",
    ]

    for config_path in config_paths:
        if Path(config_path).exists():
            try:
                with open(config_path, "r") as f:
                    content = f.read()
                for line in content.splitlines():
                    if "device-type" in line or "serial" in line or "device" in line:
                        # Look for --device or --serial patterns
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part in ("--device", "--serial") and i + 1 < len(parts):
                                return parts[i + 1].strip('"').strip("'")
                            if part.startswith("--device=") or part.startswith("--serial="):
                                return part.split("=", 1)[1].strip('"').strip("'")
            except (PermissionError, OSError):
                pass

    return None


def _detect_ports(service_name: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """Attempt to detect Beast and SBS ports from the service config."""
    if not service_name:
        return None, None

    beast_port = None
    sbs_port = None

    config_paths = [
        f"/etc/default/{service_name}",
        "/etc/default/readsb",
    ]

    for config_path in config_paths:
        if Path(config_path).exists():
            try:
                with open(config_path, "r") as f:
                    content = f.read()
                for line in content.splitlines():
                    if "net-bo-port" in line or "net-beast-reduce-port" in line:
                        port = _extract_port(line, "net-bo-port") or _extract_port(line, "net-beast-reduce-port")
                        if port:
                            beast_port = port
                    if "net-sbs-port" in line:
                        port = _extract_port(line, "net-sbs-port")
                        if port:
                            sbs_port = port
            except (PermissionError, OSError):
                pass

    return beast_port, sbs_port


def _extract_port(line: str, flag: str) -> Optional[int]:
    """Extract a port number from a config line containing the given flag."""
    parts = line.split()
    for i, part in enumerate(parts):
        if part == f"--{flag}" and i + 1 < len(parts):
            try:
                return int(parts[i + 1].strip('"').strip("'"))
            except ValueError:
                pass
        if part.startswith(f"--{flag}="):
            try:
                return int(part.split("=", 1)[1].strip('"').strip("'"))
            except ValueError:
                pass
    return None


def _check_unicode_support() -> bool:
    """Check whether the terminal likely supports Unicode box-drawing."""
    lang = os.environ.get("LANG", "")
    lc_all = os.environ.get("LC_ALL", "")
    term = os.environ.get("TERM", "")

    if "utf" in lang.lower() or "utf" in lc_all.lower():
        return True
    if term in ("xterm-256color", "screen-256color", "tmux-256color"):
        return True
    return False
