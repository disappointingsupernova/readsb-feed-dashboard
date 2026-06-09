"""Notification hooks — call webhooks or scripts when alerts fire."""

import json
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .collector import Alert


@dataclass
class NotificationConfig:
    """Configuration for notification hooks."""

    webhook_url: Optional[str] = None
    script_path: Optional[str] = None
    cooldown_seconds: float = 300.0  # Don't re-fire same alert within this window


# Track last-fired times to avoid spamming
_last_fired: dict[str, float] = {}


def send_notifications(alerts: list[Alert], config: Optional[NotificationConfig]) -> None:
    """Send notifications for new alerts, respecting cooldown."""
    if not config or not alerts:
        return

    import time

    now = time.time()
    for alert in alerts:
        key = f"{alert.feed_label}:{alert.message}"
        last = _last_fired.get(key, 0)
        if now - last < config.cooldown_seconds:
            continue

        _last_fired[key] = now

        if config.webhook_url:
            _send_webhook(config.webhook_url, alert)
        if config.script_path:
            _run_script(config.script_path, alert)


def _send_webhook(url: str, alert: Alert) -> None:
    """POST alert as JSON to a webhook URL."""
    payload = json.dumps({
        "feed": alert.feed_label,
        "severity": alert.severity,
        "message": alert.message,
    }).encode()

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "readsb-feed-dashboard"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except (urllib.error.URLError, OSError):
        pass  # Non-critical


def _run_script(script_path: str, alert: Alert) -> None:
    """Execute a notification script with alert details as environment variables."""
    path = Path(script_path)
    if not path.exists() or not path.is_file():
        return

    import os
    env = os.environ.copy()
    env["ALERT_FEED"] = alert.feed_label
    env["ALERT_SEVERITY"] = alert.severity
    env["ALERT_MESSAGE"] = alert.message

    try:
        subprocess.run(
            [str(path.resolve())],
            env=env,
            timeout=30,
            capture_output=True,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
