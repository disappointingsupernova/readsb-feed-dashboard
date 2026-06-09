"""Multi-host aggregation — pull status from multiple remote readsb-feed-dashboard instances."""

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RemoteHostStatus:
    """Status from a remote dashboard instance."""

    host: str
    url: str
    reachable: bool = False
    error: Optional[str] = None
    total_unique: int = 0
    feeds: list[dict] = field(default_factory=list)


def fetch_remote_host(url: str) -> RemoteHostStatus:
    """Fetch status from a remote readsb-feed-dashboard /api/status endpoint.

    Args:
        url: Full URL to the remote /api/status endpoint,
             e.g. "http://192.168.1.50:8754/api/status"
    """
    status = RemoteHostStatus(host=url.split("//")[-1].split("/")[0], url=url)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "readsb-feed-dashboard"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        status.error = str(e)
        return status

    if not isinstance(data, dict):
        status.error = "Invalid response format"
        return status

    status.reachable = True
    status.total_unique = data.get("total_unique", 0)
    status.feeds = data.get("feeds", [])
    return status


def fetch_all_remote_hosts(urls: list[str]) -> list[RemoteHostStatus]:
    """Fetch status from all configured remote hosts."""
    return [fetch_remote_host(url) for url in urls]
