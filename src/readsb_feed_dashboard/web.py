"""Lightweight HTTP server for web dashboard and Prometheus metrics export."""

import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from .collector import FeedData, compute_overlaps


_latest_state: Optional[dict] = None
_lock = threading.Lock()


def update_state(feeds: list[FeedData], overlaps: dict) -> None:
    """Update the shared state for the web server."""
    global _latest_state
    state = {
        "timestamp": datetime.now().isoformat(),
        "total_unique": overlaps.get("total_unique", 0),
        "feeds": [],
    }
    for i, feed in enumerate(feeds):
        state["feeds"].append({
            "label": feed.config.label,
            "aircraft_count": feed.aircraft_count,
            "position_tracked": feed.position_tracked,
            "unique": overlaps.get("unique_to", {}).get(i, 0),
            "service_active": feed.service_active,
            "json_stale": feed.json_stale,
            "messages_rate": feed.messages_rate,
            "max_range_session": feed.max_range_session,
            "rssi_avg": feed.rssi_stats.avg_rssi,
            "type_breakdown": {
                "adsb": feed.type_breakdown.adsb_icao,
                "mlat": feed.type_breakdown.mlat,
                "tisb": feed.type_breakdown.tisb,
                "mode_s": feed.type_breakdown.mode_s,
            },
        })
    with _lock:
        _latest_state = state


def _prometheus_metrics(feeds: list[FeedData]) -> str:
    """Generate Prometheus-format metrics."""
    lines = []
    lines.append("# HELP readsb_aircraft_total Current aircraft count per feed")
    lines.append("# TYPE readsb_aircraft_total gauge")
    for feed in feeds:
        label = feed.config.label.lower().replace(" ", "_")
        lines.append(f'readsb_aircraft_total{{feed="{label}"}} {feed.aircraft_count}')

    lines.append("# HELP readsb_position_tracked Aircraft with position per feed")
    lines.append("# TYPE readsb_position_tracked gauge")
    for feed in feeds:
        label = feed.config.label.lower().replace(" ", "_")
        lines.append(f'readsb_position_tracked{{feed="{label}"}} {feed.position_tracked}')

    lines.append("# HELP readsb_messages_rate Messages per second per feed")
    lines.append("# TYPE readsb_messages_rate gauge")
    for feed in feeds:
        label = feed.config.label.lower().replace(" ", "_")
        rate = feed.messages_rate if feed.messages_rate is not None else 0
        lines.append(f'readsb_messages_rate{{feed="{label}"}} {rate:.1f}')

    lines.append("# HELP readsb_rssi_avg Average RSSI per feed")
    lines.append("# TYPE readsb_rssi_avg gauge")
    for feed in feeds:
        label = feed.config.label.lower().replace(" ", "_")
        rssi = feed.rssi_stats.avg_rssi if feed.rssi_stats.avg_rssi is not None else 0
        lines.append(f'readsb_rssi_avg{{feed="{label}"}} {rssi:.1f}')

    lines.append("# HELP readsb_max_range_nm Session max range in nautical miles")
    lines.append("# TYPE readsb_max_range_nm gauge")
    for feed in feeds:
        label = feed.config.label.lower().replace(" ", "_")
        mr = feed.max_range_session if feed.max_range_session else 0
        lines.append(f'readsb_max_range_nm{{feed="{label}"}} {mr:.1f}')

    lines.append("# HELP readsb_service_up 1 if service is active, 0 otherwise")
    lines.append("# TYPE readsb_service_up gauge")
    for feed in feeds:
        label = feed.config.label.lower().replace(" ", "_")
        up = 1 if feed.service_active == "active" else 0
        lines.append(f'readsb_service_up{{feed="{label}"}} {up}')

    lines.append("")
    return "\n".join(lines)


_latest_feeds: list[FeedData] = []


def _update_feeds(feeds: list[FeedData]) -> None:
    global _latest_feeds
    _latest_feeds = feeds


class _Handler(BaseHTTPRequestHandler):
    """HTTP request handler for the web dashboard."""

    def do_GET(self):
        if self.path == "/metrics":
            body = _prometheus_metrics(_latest_feeds)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())
        elif self.path == "/api/status":
            with _lock:
                data = _latest_state or {}
            body = json.dumps(data, indent=2)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body.encode())
        elif self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(_HTML_PAGE.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress request logging


_HTML_PAGE = """<!DOCTYPE html>
<html><head><title>readsb-feed-dashboard</title>
<meta http-equiv="refresh" content="5">
<style>
body{font-family:monospace;background:#1a1a2e;color:#e0e0e0;margin:2em}
table{border-collapse:collapse;margin:1em 0}
th,td{padding:4px 12px;text-align:left;border-bottom:1px solid #333}
th{color:#00d4ff}
.ok{color:#4caf50} .bad{color:#f44336} .warn{color:#ff9800}
h1{color:#00d4ff}
</style></head><body>
<h1>readsb-feed-dashboard</h1>
<p>Auto-refreshes every 5 seconds. For structured data use <a href="/api/status">/api/status</a> or <a href="/metrics">/metrics</a> (Prometheus).</p>
<div id="data">Loading...</div>
<script>
fetch('/api/status').then(r=>r.json()).then(d=>{
let h='<p>Updated: '+d.timestamp+'</p><p>Total unique: <b>'+d.total_unique+'</b></p>';
h+='<table><tr><th>Feed</th><th>Aircraft</th><th>Tracked</th><th>Unique</th><th>Msgs/s</th><th>Service</th></tr>';
(d.feeds||[]).forEach(f=>{
let svc=f.service_active=='active'?'<span class="ok">active</span>':'<span class="bad">'+f.service_active+'</span>';
let rate=f.messages_rate?f.messages_rate.toFixed(0):'-';
h+='<tr><td>'+f.label+'</td><td>'+f.aircraft_count+'</td><td>'+f.position_tracked+'</td><td>'+f.unique+'</td><td>'+rate+'</td><td>'+svc+'</td></tr>';
});
h+='</table>';
document.getElementById('data').innerHTML=h;
});
</script></body></html>"""


def start_web_server(port: int = 8754) -> threading.Thread:
    """Start the web server in a background thread."""
    server = HTTPServer(("0.0.0.0", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def update_web_state(feeds: list[FeedData], overlaps: dict) -> None:
    """Update both the JSON state and feeds reference for the web server."""
    _update_feeds(feeds)
    update_state(feeds, overlaps)
