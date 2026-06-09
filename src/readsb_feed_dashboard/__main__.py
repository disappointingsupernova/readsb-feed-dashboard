"""Main entry point for readsb-feed-dashboard."""

import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

from . import __version__
from .collector import collect_feed_data, collect_system_info, compute_overlaps, get_history, init_history
from .config import DashboardConfig
from .feeders import ExternalFeeders, collect_external_feeders
from .renderer import render_dashboard


INSTALL_DIR = Path("/opt/readsb-feed-dashboard")
SYMLINK_PATH = Path("/usr/local/bin/readsb-feed-dashboard")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="readsb-feed-dashboard",
        description="Terminal dashboard for monitoring multi-readsb ADS-B setups.",
        epilog="For more information, see: https://github.com/Louis/readsb-feed-dashboard",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to configuration file (default: auto-detect).",
    )
    parser.add_argument(
        "--refresh", "-r",
        type=float,
        default=None,
        help="Refresh interval in seconds (default: 2.0).",
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        default=False,
        help="Force ASCII-safe mode (no Unicode box-drawing characters).",
    )
    parser.add_argument(
        "--unicode",
        action="store_true",
        default=False,
        help="Force Unicode mode.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Maximum aircraft rows per feed table (default: 10).",
    )
    parser.add_argument(
        "--sort",
        type=str,
        choices=["seen", "distance", "altitude", "rssi"],
        default=None,
        help="Sort aircraft table by: seen, distance, altitude, rssi (default: seen).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        default=False,
        help="Compact mode — hide aircraft tables, show only summary and feed panels.",
    )
    parser.add_argument(
        "--theme",
        type=str,
        choices=["dark", "light", "solarised"],
        default=None,
        help="Colour theme (default: dark).",
    )
    parser.add_argument(
        "--log",
        type=str,
        default=None,
        help="Log aircraft counts to a CSV file each refresh cycle.",
    )
    parser.add_argument(
        "--export",
        type=str,
        choices=["json"],
        default=None,
        help="Export current state as JSON and exit.",
    )
    parser.add_argument(
        "--watchdog",
        action="store_true",
        default=False,
        help="Exit with non-zero status if any feed is down (for scripts/cron).",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        default=False,
        help="Update readsb-feed-dashboard to the latest version.",
    )
    parser.add_argument(
        "--dump-config",
        action="store_true",
        default=False,
        help="Dump the auto-detected or loaded configuration as JSON and exit.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        default=False,
        help="Render the dashboard once and exit (useful for screenshots/debugging).",
    )

    return parser.parse_args()


def handle_update() -> None:
    """Handle the --update flag."""
    print("Updating readsb-feed-dashboard...")

    if not INSTALL_DIR.exists():
        print(f"Installation directory not found at {INSTALL_DIR}.", file=sys.stderr)
        print("Please re-run the install script.", file=sys.stderr)
        sys.exit(1)

    # Pull latest code
    try:
        subprocess.run(
            ["git", "-C", str(INSTALL_DIR), "pull", "--ff-only"],
            check=True,
        )
        print("Repository updated successfully.")
    except subprocess.CalledProcessError:
        print("Error: Failed to pull updates. Check your network connection.", file=sys.stderr)
        sys.exit(1)

    # Re-install into the venv
    venv_pip = INSTALL_DIR / ".venv" / "bin" / "pip"
    if venv_pip.exists():
        try:
            subprocess.run(
                [str(venv_pip), "install", "--upgrade", str(INSTALL_DIR)],
                check=True,
            )
            print("Dependencies updated successfully.")
        except subprocess.CalledProcessError:
            print("Error: Failed to update dependencies.", file=sys.stderr)
            sys.exit(1)
    else:
        # Fallback: try system pip with --break-system-packages
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--break-system-packages", "--upgrade", str(INSTALL_DIR)],
                check=True,
            )
            print("Dependencies updated (system pip fallback).")
        except subprocess.CalledProcessError:
            print("Error: Failed to update dependencies.", file=sys.stderr)
            print("Try re-running the install script: sudo bash /opt/readsb-feed-dashboard/install.sh", file=sys.stderr)
            sys.exit(1)

    print("Update complete.")
    sys.exit(0)


def dump_config(config: DashboardConfig) -> None:
    """Dump configuration as JSON."""
    data = {
        "title": config.title,
        "refresh_interval": config.refresh_interval,
        "unicode_mode": config.unicode_mode,
        "max_aircraft_rows": config.max_aircraft_rows,
        "show_ports": config.show_ports,
        "show_service_status": config.show_service_status,
        "theme": config.theme,
        "sort_by": config.sort_by,
        "stale_threshold": config.stale_threshold,
        "sparkline_length": config.sparkline_length,
        "compact_mode": config.compact_mode,
        "log_path": config.log_path,
        "feeds": [],
    }
    for feed in config.feeds:
        feed_data = {
            "label": feed.label,
            "json_path": feed.json_path,
            "json_url": feed.json_url,
            "service_name": feed.service_name,
            "feed_type": feed.feed_type,
            "beast_port": feed.beast_port,
            "sbs_port": feed.sbs_port,
            "serial": feed.serial,
        }
        if feed.alerts:
            feed_data["alerts"] = {
                "min_aircraft": feed.alerts.min_aircraft,
                "alert_on_service_inactive": feed.alerts.alert_on_service_inactive,
                "alert_on_stale_json": feed.alerts.alert_on_stale_json,
            }
        data["feeds"].append(feed_data)

    print(json.dumps(data, indent=2))
    sys.exit(0)


def handle_export(config: DashboardConfig) -> None:
    """Export current state as structured JSON."""
    feeds = [collect_feed_data(f, config) for f in config.feeds]
    overlaps = compute_overlaps(feeds)

    output = {
        "timestamp": datetime.now().isoformat(),
        "total_unique": overlaps["total_unique"],
        "feeds": [],
    }

    for i, feed in enumerate(feeds):
        feed_out = {
            "label": feed.config.label,
            "aircraft_count": feed.aircraft_count,
            "position_tracked": feed.position_tracked,
            "unique": overlaps["unique_to"].get(i, 0),
            "service_active": feed.service_active,
            "service_uptime": feed.service_uptime,
            "json_exists": feed.json_exists,
            "json_stale": feed.json_stale,
            "json_error": feed.json_error,
            "messages_rate": feed.messages_rate,
            "rssi_stats": {
                "min": feed.rssi_stats.min_rssi,
                "avg": feed.rssi_stats.avg_rssi,
                "max": feed.rssi_stats.max_rssi,
            },
            "distance_rings": {
                "within_50nm": feed.distance_rings.within_50nm,
                "within_100nm": feed.distance_rings.within_100nm,
                "within_150nm": feed.distance_rings.within_150nm,
                "within_200nm": feed.distance_rings.within_200nm,
                "beyond_200nm": feed.distance_rings.beyond_200nm,
            },
            "type_breakdown": {
                "adsb_icao": feed.type_breakdown.adsb_icao,
                "mlat": feed.type_breakdown.mlat,
                "tisb": feed.type_breakdown.tisb,
                "mode_s": feed.type_breakdown.mode_s,
                "other": feed.type_breakdown.other,
            },
            "alerts": [{"message": a.message, "severity": a.severity} for a in feed.alerts],
        }
        output["feeds"].append(feed_out)

    print(json.dumps(output, indent=2))
    sys.exit(0)


def handle_watchdog(config: DashboardConfig) -> None:
    """Check feed health and exit with appropriate code."""
    feeds = [collect_feed_data(f, config) for f in config.feeds]

    failures = []
    for feed in feeds:
        if feed.service_active in ("inactive", "failed"):
            failures.append(f"{feed.config.label}: service {feed.service_active}")
        elif not feed.json_exists:
            failures.append(f"{feed.config.label}: JSON not found")
        elif feed.json_stale:
            failures.append(f"{feed.config.label}: JSON stale")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        sys.exit(1)

    print("OK: All feeds healthy.")
    sys.exit(0)


MAX_LOG_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


def log_cycle(feeds: list, log_path: str) -> None:
    """Append current feed data to a CSV log file with size limit."""
    now = datetime.now().isoformat()
    log_file = Path(log_path)

    # Enforce maximum log file size to prevent disk exhaustion
    if log_file.exists():
        try:
            if log_file.stat().st_size >= MAX_LOG_SIZE_BYTES:
                # Rotate: rename current to .old, start fresh
                old_path = log_file.with_suffix(".csv.old")
                try:
                    old_path.unlink(missing_ok=True)
                    log_file.rename(old_path)
                except OSError:
                    return  # Cannot rotate, skip logging
        except OSError:
            return

    file_exists = log_file.exists()

    try:
        with open(log_path, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "timestamp", "feed", "aircraft", "position_tracked",
                    "messages_rate", "service_active", "json_stale",
                ])
            for feed in feeds:
                writer.writerow([
                    now,
                    feed.config.label,
                    feed.aircraft_count,
                    feed.position_tracked,
                    f"{feed.messages_rate:.1f}" if feed.messages_rate is not None else "",
                    feed.service_active,
                    feed.json_stale,
                ])
    except OSError:
        pass  # Non-critical — do not crash for logging failures


def main() -> None:
    """Main entry point."""
    args = parse_args()

    if args.update:
        handle_update()

    # Load configuration
    try:
        config = DashboardConfig.load(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Apply CLI overrides
    if args.refresh is not None:
        config.refresh_interval = args.refresh
    if args.ascii:
        config.unicode_mode = False
    if args.unicode:
        config.unicode_mode = True
    if args.max_rows is not None:
        config.max_aircraft_rows = args.max_rows
    if args.sort:
        config.sort_by = args.sort
    if args.compact:
        config.compact_mode = True
    if args.theme:
        config.theme = args.theme
    if args.log:
        config.log_path = args.log

    if args.dump_config:
        dump_config(config)

    if args.export:
        handle_export(config)

    if args.watchdog:
        handle_watchdog(config)

    if not config.feeds:
        print("No feeds detected or configured.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Either:", file=sys.stderr)
        print("  1. Ensure readsb is running and /run/readsb*/aircraft.json exists.", file=sys.stderr)
        print("  2. Create a config file at /etc/readsb-feed-dashboard.conf", file=sys.stderr)
        print("     or ~/.config/readsb-feed-dashboard/config.json", file=sys.stderr)
        print("", file=sys.stderr)
        print("Run with --dump-config to see what was auto-detected.", file=sys.stderr)
        sys.exit(1)

    # Initialise history with configured sparkline length
    init_history(config.sparkline_length)

    # Set up console
    console = Console(force_terminal=True)
    if not config.unicode_mode:
        console = Console(force_terminal=True, no_color=False, highlight=False)

    # Handle signals gracefully
    def signal_handler(sig, frame):
        try:
            console.clear()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Single-shot mode
    if args.once:
        feeds = [collect_feed_data(f, config) for f in config.feeds]
        external = collect_external_feeders()
        sys_info = collect_system_info()
        renderable = render_dashboard(console, config, feeds, external_feeders=external, sys_info=sys_info)
        console.print(renderable)
        sys.exit(0)

    # Interactive mode with keyboard input
    _run_interactive(console, config)


def _run_interactive(console: Console, config: DashboardConfig) -> None:
    """Run the interactive dashboard loop with keyboard support."""
    import select
    import termios
    import tty

    from rich.live import Live

    focused_feed: Optional[int] = None
    compare_mode: bool = False
    sort_options = ["seen", "distance", "altitude", "rssi"]

    # Set up non-blocking terminal input
    stdin_fd = sys.stdin.fileno()
    old_settings = None
    try:
        old_settings = termios.tcgetattr(stdin_fd)
    except (termios.error, OSError):
        pass

    try:
        if old_settings is not None:
            tty.setcbreak(stdin_fd)

        # Cache external feeders (refresh every 30s)
        external_feeders = collect_external_feeders()
        sys_info = collect_system_info()
        external_last_check = time.time()
        external_cache_ttl = 30.0

        with Live(console=console, refresh_per_second=1, screen=True) as live:
            while True:
                feeds = [collect_feed_data(f, config) for f in config.feeds]

                # Refresh external feeders and system info periodically
                if time.time() - external_last_check > external_cache_ttl:
                    external_feeders = collect_external_feeders()
                    sys_info = collect_system_info()
                    external_last_check = time.time()

                renderable = render_dashboard(console, config, feeds, focused_feed=focused_feed, external_feeders=external_feeders, sys_info=sys_info, compare_mode=compare_mode)
                live.update(renderable)

                # Log if configured
                if config.log_path:
                    log_cycle(feeds, config.log_path)

                # Poll for keyboard input during sleep
                deadline = time.time() + config.refresh_interval
                while time.time() < deadline:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        break

                    if old_settings is None:
                        time.sleep(min(remaining, 0.1))
                        continue

                    ready, _, _ = select.select([sys.stdin], [], [], min(remaining, 0.1))
                    if ready:
                        key = sys.stdin.read(1)
                        if key == "q":
                            return
                        elif key == "s":
                            config.compact_mode = not config.compact_mode
                        elif key == "c":
                            compare_mode = not compare_mode
                        elif key == "f":
                            # Cycle sort
                            idx = sort_options.index(config.sort_by) if config.sort_by in sort_options else 0
                            config.sort_by = sort_options[(idx + 1) % len(sort_options)]
                        elif key == "0":
                            focused_feed = None
                        elif key.isdigit():
                            num = int(key) - 1
                            if 0 <= num < len(config.feeds):
                                focused_feed = num
                            else:
                                focused_feed = None
                        # Force immediate re-render on keypress
                        break
    finally:
        if old_settings is not None:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)


if __name__ == "__main__":
    main()
