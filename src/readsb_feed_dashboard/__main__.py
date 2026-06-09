"""Main entry point for readsb-feed-dashboard."""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console

from . import __version__
from .collector import collect_feed_data, compute_overlaps
from .config import DashboardConfig
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

    repo_url = "https://github.com/Louis/readsb-feed-dashboard.git"

    if INSTALL_DIR.exists():
        try:
            subprocess.run(
                ["git", "-C", str(INSTALL_DIR), "pull", "--ff-only"],
                check=True,
            )
            print("Repository updated successfully.")
        except subprocess.CalledProcessError:
            print("Error: Failed to pull updates. Check your network connection.", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Installation directory not found at {INSTALL_DIR}.")
        print("Please re-run the install script.")
        sys.exit(1)

    # Re-install dependencies
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", str(INSTALL_DIR)],
            check=True,
        )
        print("Dependencies updated successfully.")
    except subprocess.CalledProcessError:
        print("Error: Failed to update dependencies.", file=sys.stderr)
        sys.exit(1)

    print("Update complete.")
    sys.exit(0)


def dump_config(config: DashboardConfig) -> None:
    """Dump configuration as JSON."""
    import json

    data = {
        "title": config.title,
        "refresh_interval": config.refresh_interval,
        "unicode_mode": config.unicode_mode,
        "max_aircraft_rows": config.max_aircraft_rows,
        "show_ports": config.show_ports,
        "show_service_status": config.show_service_status,
        "feeds": [],
    }
    for feed in config.feeds:
        data["feeds"].append({
            "label": feed.label,
            "json_path": feed.json_path,
            "service_name": feed.service_name,
            "feed_type": feed.feed_type,
            "beast_port": feed.beast_port,
            "sbs_port": feed.sbs_port,
            "serial": feed.serial,
        })

    print(json.dumps(data, indent=2))
    sys.exit(0)


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

    if args.dump_config:
        dump_config(config)

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

    # Set up console
    console = Console(force_terminal=True)
    if not config.unicode_mode:
        console = Console(force_terminal=True, legacy_windows=True)

    # Handle signals gracefully
    def signal_handler(sig, frame):
        console.clear()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Main loop
    if args.once:
        feeds = [collect_feed_data(f) for f in config.feeds]
        renderable = render_dashboard(console, config, feeds)
        console.print(renderable)
        sys.exit(0)

    from rich.live import Live

    with Live(console=console, refresh_per_second=1, screen=True) as live:
        while True:
            feeds = [collect_feed_data(f) for f in config.feeds]
            renderable = render_dashboard(console, config, feeds)
            live.update(renderable)
            time.sleep(config.refresh_interval)


if __name__ == "__main__":
    main()
