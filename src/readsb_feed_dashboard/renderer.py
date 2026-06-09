"""Terminal rendering module using Rich for the dashboard display."""

import time
from datetime import datetime

from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .collector import AircraftEntry, FeedData, compute_overlaps
from .config import DashboardConfig


# Colour scheme
COLOUR_ACTIVE = "green"
COLOUR_INACTIVE = "red"
COLOUR_STALE = "yellow"
COLOUR_TITLE = "bold cyan"
COLOUR_HEADER = "bold white"
COLOUR_MUTED = "dim"
COLOUR_HIGHLIGHT = "bold magenta"


def build_header(config: DashboardConfig) -> Panel:
    """Build the top header panel."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title_text = Text(config.title, style=COLOUR_TITLE, justify="center")
    time_text = Text(now, style=COLOUR_MUTED, justify="center")
    content = Group(title_text, time_text)
    return Panel(
        Align.center(content),
        border_style="cyan",
        padding=(0, 1),
    )


def build_feed_panel(feed: FeedData, overlaps: dict, feed_index: int, all_feeds: list[FeedData], ascii_mode: bool = False) -> Panel:
    """Build the summary panel for a single feed."""
    cfg = feed.config

    # Service status
    if feed.service_active == "active":
        status_text = Text("active", style=COLOUR_ACTIVE)
    elif feed.service_active == "failed":
        status_text = Text("failed", style=COLOUR_INACTIVE)
    elif feed.service_active == "inactive":
        status_text = Text("inactive", style=COLOUR_INACTIVE)
    else:
        status_text = Text(feed.service_active or "unknown", style=COLOUR_STALE)

    # JSON status
    if not feed.json_exists:
        json_status = Text("NOT FOUND", style=COLOUR_INACTIVE)
    elif feed.json_stale:
        json_status = Text("STALE", style=COLOUR_STALE)
    elif feed.json_error:
        json_status = Text(f"ERROR: {feed.json_error}", style=COLOUR_INACTIVE)
    else:
        json_status = Text("LIVE", style=COLOUR_ACTIVE)

    # Build info table
    info = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
    info.add_column("Key", style="bold", min_width=14)
    info.add_column("Value")

    info.add_row("Aircraft:", str(feed.aircraft_count))
    info.add_row("Service:", status_text)
    info.add_row("JSON:", json_status)

    # Unique count
    unique_count = overlaps.get("unique_to", {}).get(feed_index, 0)
    info.add_row("Unique:", str(unique_count))

    # Shared with other feeds
    shared_info = overlaps.get("shared", {}).get(feed_index, {})
    for j, count in shared_info.items():
        if count > 0:
            other_label = all_feeds[j].config.label
            info.add_row(f"Shared w/{other_label}:", str(count))

    # Ports
    if cfg.beast_port:
        info.add_row("Beast port:", str(cfg.beast_port))
    if cfg.sbs_port:
        info.add_row("SBS port:", str(cfg.sbs_port))
    if feed.listening_ports:
        for port in feed.listening_ports[:4]:
            info.add_row("Listening:", port)

    # Serial
    if cfg.serial:
        info.add_row("Serial:", cfg.serial)

    # Title
    title = f"{cfg.label}"
    if cfg.serial:
        title += f" [{cfg.serial}]"

    border_style = COLOUR_ACTIVE if feed.service_active == "active" else COLOUR_INACTIVE
    box_type = None  # Rich handles ascii/unicode via Console

    return Panel(
        info,
        title=title,
        title_align="left",
        border_style=border_style,
        padding=(0, 1),
    )


def build_aircraft_table(feed: FeedData, max_rows: int = 10) -> Panel:
    """Build an aircraft table for a feed."""
    table = Table(
        show_header=True,
        header_style=COLOUR_HEADER,
        expand=True,
        padding=(0, 1),
    )

    table.add_column("Hex", style="cyan", min_width=7)
    table.add_column("Flight", min_width=8)
    table.add_column("Alt (ft)", justify="right", min_width=8)
    table.add_column("Spd (kt)", justify="right", min_width=8)
    table.add_column("RSSI", justify="right", min_width=6)
    table.add_column("Squawk", min_width=6)
    table.add_column("Dist (nm)", justify="right", min_width=8)
    table.add_column("Seen (s)", justify="right", min_width=7)

    # Sort by 'seen' (most recently seen first)
    sorted_aircraft = sorted(
        feed.aircraft,
        key=lambda a: a.seen if a.seen is not None else 9999,
    )

    for ac in sorted_aircraft[:max_rows]:
        table.add_row(
            ac.hex,
            ac.flight or "-",
            str(ac.alt_baro) if ac.alt_baro is not None else "-",
            f"{ac.gs:.0f}" if ac.gs is not None else "-",
            f"{ac.rssi:.1f}" if ac.rssi is not None else "-",
            ac.squawk or "-",
            f"{ac.distance:.1f}" if ac.distance is not None else "-",
            f"{ac.seen:.0f}" if ac.seen is not None else "-",
        )

    if not feed.aircraft:
        table.add_row("-", "-", "-", "-", "-", "-", "-", "-")

    return Panel(
        table,
        title=f"Latest Aircraft — {feed.config.label}",
        title_align="left",
        border_style="blue",
    )


def build_summary_panel(feeds: list[FeedData], overlaps: dict) -> Panel:
    """Build a global summary panel."""
    table = Table(show_header=True, header_style=COLOUR_HEADER, box=None, padding=(0, 1))
    table.add_column("Feed", style="bold cyan")
    table.add_column("Aircraft", justify="right")
    table.add_column("Unique", justify="right")
    table.add_column("Service", justify="centre")
    table.add_column("JSON", justify="centre")

    for i, feed in enumerate(feeds):
        # Service
        if feed.service_active == "active":
            svc_text = Text("active", style=COLOUR_ACTIVE)
        else:
            svc_text = Text(feed.service_active or "?", style=COLOUR_INACTIVE)

        # JSON
        if not feed.json_exists:
            j_text = Text("MISSING", style=COLOUR_INACTIVE)
        elif feed.json_stale:
            j_text = Text("STALE", style=COLOUR_STALE)
        elif feed.json_error:
            j_text = Text("ERROR", style=COLOUR_INACTIVE)
        else:
            j_text = Text("LIVE", style=COLOUR_ACTIVE)

        unique = overlaps.get("unique_to", {}).get(i, 0)
        table.add_row(
            feed.config.label,
            str(feed.aircraft_count),
            str(unique),
            svc_text,
            j_text,
        )

    total_unique = overlaps.get("total_unique", 0)
    table.add_row("", "", "", "", "")
    table.add_row(
        Text("TOTAL UNIQUE", style="bold"),
        Text(str(total_unique), style="bold"),
        "", "", "",
    )

    return Panel(table, title="Summary", title_align="left", border_style="magenta")


def render_dashboard(console: Console, config: DashboardConfig, feeds: list[FeedData]) -> Group:
    """Render the full dashboard as a Rich renderable."""
    overlaps = compute_overlaps(feeds)

    renderables = []

    # Header
    renderables.append(build_header(config))

    # Summary
    renderables.append(build_summary_panel(feeds, overlaps))

    # Feed panels side-by-side where possible
    feed_panels = []
    for i, feed in enumerate(feeds):
        feed_panels.append(build_feed_panel(feed, overlaps, i, feeds, ascii_mode=not config.unicode_mode))

    if len(feed_panels) <= 3:
        renderables.append(Columns(feed_panels, equal=True, expand=True))
    else:
        # Group in rows of 3
        for chunk_start in range(0, len(feed_panels), 3):
            chunk = feed_panels[chunk_start:chunk_start + 3]
            renderables.append(Columns(chunk, equal=True, expand=True))

    # Aircraft tables
    for feed in feeds:
        renderables.append(build_aircraft_table(feed, max_rows=config.max_aircraft_rows))

    return Group(*renderables)
