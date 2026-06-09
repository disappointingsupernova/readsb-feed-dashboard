"""Terminal rendering module using Rich for the dashboard display."""

from datetime import datetime

from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .collector import FeedData, SystemInfo, compute_overlaps, get_history
from .config import DashboardConfig, THEMES
from .feeders import ExternalFeeders, FR24Status, PiawareStatus, RBFeederStatus

# Emergency squawk codes
_EMERGENCY_SQUAWKS = {"7500": "HIJACK", "7600": "RADIO FAIL", "7700": "EMERGENCY"}


def _theme(config: DashboardConfig) -> dict:
    """Get the active theme colours."""
    return THEMES.get(config.theme, THEMES["dark"])


def _rssi_style(rssi: float, theme: dict) -> str:
    """Return colour style for an RSSI value."""
    if rssi >= -10.0:
        return theme["rssi_strong"]
    elif rssi >= -20.0:
        return theme["rssi_moderate"]
    return theme["rssi_weak"]


def _sparkline(values: list[int], width: int = 20) -> str:
    """Generate a sparkline string from a list of values."""
    if not values:
        return ""
    # Use Unicode block characters
    blocks = " _.-~*"
    # Trim to width
    data = values[-width:]
    if not data:
        return ""
    min_val = min(data)
    max_val = max(data)
    spread = max_val - min_val if max_val != min_val else 1

    chars = []
    spark_blocks = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
    for v in data:
        idx = int((v - min_val) / spread * (len(spark_blocks) - 1))
        chars.append(spark_blocks[idx])
    return "".join(chars)


def build_header(config: DashboardConfig) -> Panel:
    """Build the top header panel."""
    theme = _theme(config)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title_text = Text(config.title, style=theme["title"], justify="center")
    time_text = Text(now, style=theme["muted"], justify="center")
    content = Group(title_text, time_text)
    return Panel(
        Align.center(content),
        border_style=theme["panel_border"],
        padding=(0, 1),
    )


def build_alerts_panel(feeds: list[FeedData], config: DashboardConfig) -> Panel | None:
    """Build an alerts panel if any alerts are active."""
    theme = _theme(config)
    all_alerts = []
    for feed in feeds:
        all_alerts.extend(feed.alerts)

    if not all_alerts:
        return None

    table = Table(show_header=True, header_style=theme["header"], box=None, padding=(0, 1))
    table.add_column("Feed", style="bold")
    table.add_column("Severity")
    table.add_column("Message")

    for alert in all_alerts:
        sev_style = theme["alert"] if alert.severity == "critical" else theme["stale"]
        table.add_row(
            alert.feed_label,
            Text(alert.severity.upper(), style=sev_style),
            alert.message,
        )

    return Panel(
        table,
        title="ALERTS",
        title_align="left",
        border_style=theme["alert"],
        padding=(0, 1),
    )


def build_feed_panel(feed: FeedData, overlaps: dict, feed_index: int, all_feeds: list[FeedData], config: DashboardConfig) -> Panel:
    """Build the summary panel for a single feed."""
    theme = _theme(config)
    cfg = feed.config

    # Service status
    if feed.service_active == "active":
        status_text = Text("active", style=theme["active"])
    elif feed.service_active == "failed":
        status_text = Text("failed", style=theme["inactive"])
    elif feed.service_active == "inactive":
        status_text = Text("inactive", style=theme["inactive"])
    else:
        status_text = Text(feed.service_active or "unknown", style=theme["stale"])

    # JSON status
    if not feed.json_exists:
        json_status = Text("NOT FOUND", style=theme["inactive"])
    elif feed.json_stale:
        json_status = Text("STALE", style=theme["stale"])
    elif feed.json_error:
        json_status = Text(f"ERROR: {feed.json_error}", style=theme["inactive"])
    else:
        json_status = Text("LIVE", style=theme["active"])

    # Build info table
    info = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
    info.add_column("Key", style="bold", min_width=14)
    info.add_column("Value")

    info.add_row("Aircraft:", str(feed.aircraft_count))
    info.add_row("With position:", str(feed.position_tracked))

    # Count delta
    if feed.aircraft_count_delta is not None and feed.aircraft_count_delta != 0:
        delta_str = f"+{feed.aircraft_count_delta}" if feed.aircraft_count_delta > 0 else str(feed.aircraft_count_delta)
        delta_style = theme["active"] if feed.aircraft_count_delta > 0 else theme["inactive"]
        info.add_row("Delta:", Text(delta_str, style=delta_style))

    info.add_row("Service:", status_text)

    if feed.service_uptime:
        info.add_row("Uptime:", feed.service_uptime)

    info.add_row("JSON:", json_status)

    # Message rate
    if feed.messages_rate is not None:
        info.add_row("Msgs/sec:", f"{feed.messages_rate:.1f}")

    # Unique count
    unique_count = overlaps.get("unique_to", {}).get(feed_index, 0)
    info.add_row("Unique:", str(unique_count))

    # Shared with other feeds
    shared_info = overlaps.get("shared", {}).get(feed_index, {})
    for j, count in shared_info.items():
        if count > 0:
            other_label = all_feeds[j].config.label
            info.add_row(f"Shared w/{other_label}:", str(count))

    # RSSI stats
    if feed.rssi_stats.avg_rssi is not None:
        rssi_text = Text(
            f"{feed.rssi_stats.min_rssi:.1f} / {feed.rssi_stats.avg_rssi:.1f} / {feed.rssi_stats.max_rssi:.1f}",
            style=_rssi_style(feed.rssi_stats.avg_rssi, theme),
        )
        info.add_row("RSSI min/avg/max:", rssi_text)

    # Type breakdown
    tb = feed.type_breakdown
    type_parts = []
    if tb.adsb_icao:
        type_parts.append(f"ADS-B:{tb.adsb_icao}")
    if tb.mlat:
        type_parts.append(f"MLAT:{tb.mlat}")
    if tb.tisb:
        type_parts.append(f"TIS-B:{tb.tisb}")
    if tb.mode_s:
        type_parts.append(f"Mode-S:{tb.mode_s}")
    if tb.other:
        type_parts.append(f"Other:{tb.other}")
    if type_parts:
        info.add_row("Types:", " ".join(type_parts))

    # Distance rings
    dr = feed.distance_rings
    has_distance = dr.within_50nm + dr.within_100nm + dr.within_150nm + dr.within_200nm + dr.beyond_200nm
    if has_distance:
        rings_str = f"<50:{dr.within_50nm} <100:{dr.within_100nm} <150:{dr.within_150nm} <200:{dr.within_200nm} 200+:{dr.beyond_200nm}"
        info.add_row("Dist rings:", rings_str)

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

    # Process stats
    if feed.process_stats.memory_mb is not None:
        info.add_row("Memory:", f"{feed.process_stats.memory_mb:.1f} MB")
    if feed.process_stats.cpu_percent is not None:
        info.add_row("CPU:", f"{feed.process_stats.cpu_percent:.1f}%")

    # Network stats
    if feed.network_stats.bytes_rx is not None:
        rx_str = _format_bytes_rate(feed.network_stats.bytes_rx)
        tx_str = _format_bytes_rate(feed.network_stats.bytes_tx)
        info.add_row("Net I/O:", f"rx:{rx_str} tx:{tx_str}")

    # Sparkline
    history = get_history()
    spark_data = history.get_sparkline_data(cfg.label)
    if len(spark_data) > 2:
        spark_str = _sparkline(spark_data, width=20)
        info.add_row("Trend:", Text(spark_str, style=theme["sparkline"]))

    # Gain
    if cfg.gain:
        info.add_row("Gain:", cfg.gain)

    # Farthest aircraft
    if feed.farthest_aircraft and feed.farthest_aircraft.distance:
        far = feed.farthest_aircraft
        far_str = f"{far.distance:.1f} nm"
        if far.flight:
            far_str += f" ({far.flight})"
        else:
            far_str += f" ({far.hex})"
        info.add_row("Farthest:", far_str)

    # Max range this session
    if feed.max_range_session:
        info.add_row("Max range:", f"{feed.max_range_session:.1f} nm")

    # Title
    title = f"{cfg.label}"
    if cfg.serial:
        title += f" [{cfg.serial}]"

    border_style = theme["feed_panel_ok"] if feed.service_active == "active" else theme["feed_panel_bad"]

    return Panel(
        info,
        title=title,
        title_align="left",
        border_style=border_style,
        padding=(0, 1),
    )


def build_aircraft_table(feed: FeedData, config: DashboardConfig, expand: bool = True) -> Panel:
    """Build an aircraft table for a feed."""
    theme = _theme(config)

    table = Table(
        show_header=True,
        header_style=theme["header"],
        expand=expand,
        padding=(0, 1),
    )

    table.add_column("Hex", style="cyan", width=7, no_wrap=True)
    table.add_column("Flight", width=8, no_wrap=True)
    table.add_column("Alt", justify="right", width=6, no_wrap=True)
    table.add_column("Spd", justify="right", width=4, no_wrap=True)
    table.add_column("RSSI", justify="right", width=6, no_wrap=True)
    table.add_column("Sqk", width=5, no_wrap=True)
    table.add_column("Dist", justify="right", width=5, no_wrap=True)
    table.add_column("Seen", justify="right", width=5, no_wrap=True)
    table.add_column("Type", width=10, no_wrap=True)

    # Sort aircraft by configured sort key
    sorted_aircraft = _sort_aircraft(feed.aircraft, config.sort_by)

    for ac in sorted_aircraft[:config.max_aircraft_rows]:
        # Colour-coded RSSI
        if ac.rssi is not None:
            rssi_text = Text(f"{ac.rssi:.1f}", style=_rssi_style(ac.rssi, theme))
        else:
            rssi_text = Text("-")

        # Emergency squawk highlighting
        squawk_str = ac.squawk or "-"
        if ac.squawk and ac.squawk in _EMERGENCY_SQUAWKS:
            squawk_text = Text(squawk_str, style="bold red")
        else:
            squawk_text = Text(squawk_str)

        table.add_row(
            ac.hex,
            ac.flight or "-",
            str(ac.alt_baro) if ac.alt_baro is not None else "-",
            f"{ac.gs:.0f}" if ac.gs is not None else "-",
            rssi_text,
            squawk_text,
            f"{ac.distance:.1f}" if ac.distance is not None else "-",
            f"{ac.seen:.1f}" if ac.seen is not None else "-",
            ac.ac_type or "-",
        )

    if not feed.aircraft:
        table.add_row("-", "-", "-", "-", Text("-"), "-", "-", "-", "-")

    return Panel(
        table,
        title=f"Latest Aircraft -- {feed.config.label}",
        title_align="left",
        border_style=theme["table_border"],
    )


def build_summary_panel(feeds: list[FeedData], overlaps: dict, config: DashboardConfig) -> Panel:
    """Build a global summary panel."""
    theme = _theme(config)

    table = Table(show_header=True, header_style=theme["header"], box=None, padding=(0, 1))
    table.add_column("Feed", style="bold cyan")
    table.add_column("Aircraft", justify="right")
    table.add_column("Tracked", justify="right")
    table.add_column("Unique", justify="right")
    table.add_column("Msgs/s", justify="right")
    table.add_column("Service")
    table.add_column("JSON")

    for i, feed in enumerate(feeds):
        # Service
        if feed.service_active == "active":
            svc_text = Text("active", style=theme["active"])
        else:
            svc_text = Text(feed.service_active or "?", style=theme["inactive"])

        # JSON
        if not feed.json_exists:
            j_text = Text("MISSING", style=theme["inactive"])
        elif feed.json_stale:
            j_text = Text("STALE", style=theme["stale"])
        elif feed.json_error:
            j_text = Text("ERROR", style=theme["inactive"])
        else:
            j_text = Text("LIVE", style=theme["active"])

        unique = overlaps.get("unique_to", {}).get(i, 0)
        rate_str = f"{feed.messages_rate:.0f}" if feed.messages_rate is not None else "-"

        table.add_row(
            feed.config.label,
            str(feed.aircraft_count),
            str(feed.position_tracked),
            str(unique),
            rate_str,
            svc_text,
            j_text,
        )

    total_unique = overlaps.get("total_unique", 0)
    table.add_row("", "", "", "", "", "", "")
    table.add_row(
        Text("TOTAL UNIQUE", style="bold"),
        Text(str(total_unique), style="bold"),
        "", "", "", "", "",
    )

    return Panel(table, title="Summary", title_align="left", border_style=theme["summary_border"])


def build_fr24_panel(fr24: FR24Status, config: DashboardConfig) -> Panel:
    """Build a panel for FR24 feeder status."""
    theme = _theme(config)

    info = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
    info.add_column("Key", style="bold", min_width=14)
    info.add_column("Value")

    # Process
    if fr24.process_running:
        info.add_row("Process:", Text("running", style=theme["active"]))
    else:
        info.add_row("Process:", Text("not running", style=theme["inactive"]))

    # Service
    if fr24.service_active:
        svc_style = theme["active"] if fr24.service_active == "active" else theme["inactive"]
        info.add_row("Service:", Text(fr24.service_active, style=svc_style))

    # Link
    if fr24.link_connected:
        link_str = "connected"
        if fr24.link_mode:
            link_str += f" [{fr24.link_mode}]"
        info.add_row("Link:", Text(link_str, style=theme["active"]))
    else:
        info.add_row("Link:", Text("disconnected", style=theme["inactive"]))

    # Radar ID
    if fr24.radar_id:
        info.add_row("Radar:", fr24.radar_id)

    # Sharing key
    if fr24.has_sharing_key:
        info.add_row("Sharing key:", Text("configured", style=theme["active"]))

    # Receiver
    if fr24.receiver_connected:
        recv_str = "connected"
        if fr24.receiver_aircraft is not None:
            recv_str += f" ({fr24.receiver_aircraft} ac)"
        info.add_row("Receiver:", Text(recv_str, style=theme["active"]))
    else:
        info.add_row("Receiver:", Text("disconnected", style=theme["inactive"]))

    # MLAT
    if fr24.mlat_ok:
        mlat_str = "ok"
        if fr24.mlat_aircraft_seen is not None:
            mlat_str += f" ({fr24.mlat_aircraft_seen} ac)"
        info.add_row("MLAT:", Text(mlat_str, style=theme["active"]))
    else:
        info.add_row("MLAT:", Text("not active", style=theme["stale"]))

    # Aircraft stats
    if fr24.aircraft_tracked is not None:
        info.add_row("Tracked:", str(fr24.aircraft_tracked))
    if fr24.aircraft_uploaded is not None:
        info.add_row("Uploaded:", str(fr24.aircraft_uploaded))

    # Stats timestamp
    if fr24.stats_timestamp:
        info.add_row("Last stats:", fr24.stats_timestamp)

    border_style = theme["feed_panel_ok"] if fr24.link_connected else theme["feed_panel_bad"]

    return Panel(
        info,
        title="FR24 Feeder",
        title_align="left",
        border_style=border_style,
        padding=(0, 1),
    )


def render_dashboard(console: Console, config: DashboardConfig, feeds: list[FeedData], focused_feed: int | None = None, external_feeders: ExternalFeeders | None = None, sys_info: SystemInfo | None = None, compare_mode: bool = False) -> Group:
    """Render the full dashboard as a Rich renderable."""
    overlaps = compute_overlaps(feeds)
    renderables = []

    # Header
    renderables.append(build_header(config))

    # Alerts, feeders, and Summary side-by-side
    alerts_panel = build_alerts_panel(feeds, config)
    fr24_panel = None
    piaware_panel = None
    rbfeeder_panel = None

    if external_feeders:
        if external_feeders.fr24 and external_feeders.fr24.available:
            fr24_panel = build_fr24_panel(external_feeders.fr24, config)
        if external_feeders.piaware and external_feeders.piaware.available:
            piaware_panel = build_piaware_panel(external_feeders.piaware, config)
        if external_feeders.rbfeeder and external_feeders.rbfeeder.available:
            rbfeeder_panel = build_rbfeeder_panel(external_feeders.rbfeeder, config)

    top_row = []
    if alerts_panel:
        top_row.append(alerts_panel)
    if fr24_panel:
        top_row.append(fr24_panel)
    if piaware_panel:
        top_row.append(piaware_panel)
    if rbfeeder_panel:
        top_row.append(rbfeeder_panel)
    top_row.append(build_summary_panel(feeds, overlaps, config))

    if len(top_row) > 1:
        renderables.append(Columns(top_row, equal=True, expand=True))
    else:
        renderables.append(top_row[0])

    # Comparison mode
    if compare_mode:
        renderables.append(build_comparison_view(feeds, config))
        if config.show_help_bar:
            renderables.append(build_help_bar(config))
        return Group(*renderables)

    # If focused on a single feed
    if focused_feed is not None and 0 <= focused_feed < len(feeds):
        feed = feeds[focused_feed]
        renderables.append(build_feed_panel(feed, overlaps, focused_feed, feeds, config))
        if not config.compact_mode:
            renderables.append(build_aircraft_table(feed, config))
        if config.show_help_bar:
            renderables.append(build_help_bar(config))
        return Group(*renderables)

    # Feed panels side-by-side
    feed_panels = []
    for i, feed in enumerate(feeds):
        feed_panels.append(build_feed_panel(feed, overlaps, i, feeds, config))

    if len(feed_panels) <= 3:
        renderables.append(Columns(feed_panels, equal=True, expand=True))
    else:
        for chunk_start in range(0, len(feed_panels), 3):
            chunk = feed_panels[chunk_start:chunk_start + 3]
            renderables.append(Columns(chunk, equal=True, expand=True))

    # Aircraft tables (unless compact mode)
    # Place side-by-side if terminal is wide enough (>= 120 cols per table)
    if not config.compact_mode:
        term_width = console.width or 80
        table_min_width = 90  # Minimum usable width per aircraft table
        tables_per_row = max(1, term_width // table_min_width)

        aircraft_tables = [build_aircraft_table(feed, config) for feed in feeds]

        if tables_per_row >= len(aircraft_tables) and len(aircraft_tables) > 1:
            # All fit side-by-side
            renderables.append(Columns(aircraft_tables, equal=True, expand=True))
        elif tables_per_row > 1 and len(aircraft_tables) > 1:
            # Group in rows
            for chunk_start in range(0, len(aircraft_tables), tables_per_row):
                chunk = aircraft_tables[chunk_start:chunk_start + tables_per_row]
                if len(chunk) > 1:
                    renderables.append(Columns(chunk, equal=True, expand=True))
                else:
                    renderables.append(chunk[0])
        else:
            # Narrow terminal — stack vertically
            for t in aircraft_tables:
                renderables.append(t)

    # System info panel
    if sys_info:
        renderables.append(build_system_info_panel(sys_info, config))

    # Help bar
    if config.show_help_bar:
        renderables.append(build_help_bar(config))

    return Group(*renderables)


def _sort_aircraft(aircraft: list, sort_by: str) -> list:
    """Sort aircraft list by the given key."""
    if sort_by == "distance":
        return sorted(aircraft, key=lambda a: a.distance if a.distance is not None else 9999)
    elif sort_by == "altitude":
        return sorted(aircraft, key=lambda a: -(a.alt_baro if a.alt_baro is not None else -9999))
    elif sort_by == "rssi":
        return sorted(aircraft, key=lambda a: -(a.rssi if a.rssi is not None else -999))
    else:  # "seen" (default)
        return sorted(aircraft, key=lambda a: a.seen if a.seen is not None else 9999)


def _format_bytes_rate(bytes_per_sec: int | None) -> str:
    """Format bytes/sec to a human-readable string."""
    if bytes_per_sec is None:
        return "-"
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec} B/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"


def build_help_bar(config: DashboardConfig) -> Text:
    """Build a dim help bar showing keyboard shortcuts."""
    theme = _theme(config)
    return Text(
        "  q:quit  s:compact  f:sort  c:compare  1-9:focus  0:all",
        style=theme["muted"],
    )


def build_system_info_panel(sys_info: SystemInfo, config: DashboardConfig) -> Panel:
    """Build a system information panel."""
    theme = _theme(config)

    info = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
    info.add_column("Key", style="bold", min_width=10)
    info.add_column("Value")

    if sys_info.hostname:
        info.add_row("Host:", sys_info.hostname)
    if sys_info.uptime:
        info.add_row("Uptime:", sys_info.uptime)
    if sys_info.cpu_temp is not None:
        temp_style = theme["active"] if sys_info.cpu_temp < 70 else (
            theme["stale"] if sys_info.cpu_temp < 80 else theme["inactive"]
        )
        info.add_row("CPU temp:", Text(f"{sys_info.cpu_temp:.1f} C", style=temp_style))
    if sys_info.disk_free_run:
        info.add_row("/run free:", sys_info.disk_free_run)
    if sys_info.kernel:
        info.add_row("Kernel:", sys_info.kernel)

    return Panel(info, title="System", title_align="left", border_style=theme["panel_border"], padding=(0, 1))


def build_piaware_panel(piaware: PiawareStatus, config: DashboardConfig) -> Panel:
    """Build a panel for piaware feeder status."""
    theme = _theme(config)

    info = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
    info.add_column("Key", style="bold", min_width=12)
    info.add_column("Value")

    if piaware.process_running:
        info.add_row("Process:", Text("running", style=theme["active"]))
    else:
        info.add_row("Process:", Text("not running", style=theme["inactive"]))

    if piaware.connected_to_flightaware:
        info.add_row("FlightAware:", Text("connected", style=theme["active"]))
    else:
        info.add_row("FlightAware:", Text("disconnected", style=theme["inactive"]))

    if piaware.mlat_ok:
        info.add_row("MLAT:", Text("ok", style=theme["active"]))

    if piaware.aircraft_reported is not None:
        info.add_row("Aircraft:", str(piaware.aircraft_reported))

    border_style = theme["feed_panel_ok"] if piaware.connected_to_flightaware else theme["feed_panel_bad"]
    return Panel(info, title="PiAware", title_align="left", border_style=border_style, padding=(0, 1))


def build_rbfeeder_panel(rbfeeder: RBFeederStatus, config: DashboardConfig) -> Panel:
    """Build a panel for RadarBox feeder status."""
    theme = _theme(config)

    info = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
    info.add_column("Key", style="bold", min_width=12)
    info.add_column("Value")

    if rbfeeder.process_running:
        info.add_row("Process:", Text("running", style=theme["active"]))
    else:
        info.add_row("Process:", Text("not running", style=theme["inactive"]))

    if rbfeeder.connected:
        info.add_row("Link:", Text("connected", style=theme["active"]))

    if rbfeeder.aircraft_tracked is not None:
        info.add_row("Tracked:", str(rbfeeder.aircraft_tracked))

    border_style = theme["feed_panel_ok"] if rbfeeder.process_running else theme["feed_panel_bad"]
    return Panel(info, title="RadarBox", title_align="left", border_style=border_style, padding=(0, 1))


def build_comparison_view(feeds: list[FeedData], config: DashboardConfig) -> Panel:
    """Build a feed comparison view showing hex codes unique to each SDR."""
    theme = _theme(config)

    table = Table(show_header=True, header_style=theme["header"], expand=True, padding=(0, 1))

    sdr_feeds = [f for f in feeds if f.config.feed_type != "merge"]
    if len(sdr_feeds) < 2:
        return Panel(Text("Need 2+ SDR feeds for comparison"), title="Feed Comparison", border_style=theme["panel_border"])

    for feed in sdr_feeds:
        table.add_column(f"Only {feed.config.label}", style="cyan")

    # Compute exclusive hex sets
    exclusive = []
    for i, feed in enumerate(sdr_feeds):
        others = set()
        for j, other in enumerate(sdr_feeds):
            if j != i:
                others.update(other.hex_set)
        exclusive.append(sorted(feed.hex_set - others)[:15])

    max_rows = max(len(e) for e in exclusive) if exclusive else 0
    for row_idx in range(min(max_rows, 15)):
        row = []
        for exc in exclusive:
            row.append(exc[row_idx] if row_idx < len(exc) else "")
        table.add_row(*row)

    return Panel(table, title="Feed Comparison -- Exclusive Aircraft", title_align="left", border_style=theme["panel_border"])
