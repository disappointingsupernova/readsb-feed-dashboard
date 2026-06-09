"""Replay mode — read historical CSV log and replay as simulated live data."""

import csv
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Optional


@dataclass
class ReplayFrame:
    """A single replay frame representing one cycle's data."""

    timestamp: str
    feeds: dict[str, dict] = field(default_factory=dict)


def load_replay_data(csv_path: str) -> list[ReplayFrame]:
    """Load all frames from a CSV log file.

    Expected columns: timestamp, feed, aircraft, position_tracked, messages_rate, service_active, json_stale
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Replay file not found: {csv_path}")

    frames_by_ts: dict[str, dict[str, dict]] = defaultdict(dict)

    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get("timestamp", "")
            feed = row.get("feed", "")
            if not ts or not feed:
                continue
            frames_by_ts[ts][feed] = {
                "aircraft_count": int(row.get("aircraft", 0) or 0),
                "position_tracked": int(row.get("position_tracked", 0) or 0),
                "messages_rate": float(row["messages_rate"]) if row.get("messages_rate") else None,
                "service_active": row.get("service_active", "unknown"),
                "json_stale": row.get("json_stale", "").lower() == "true",
            }

    frames = []
    for ts in sorted(frames_by_ts.keys()):
        frames.append(ReplayFrame(timestamp=ts, feeds=frames_by_ts[ts]))

    return frames


def replay_generator(frames: list[ReplayFrame], speed: float = 1.0) -> Generator[ReplayFrame, None, None]:
    """Yield frames with timing that simulates the original refresh rate.

    Args:
        speed: Playback speed multiplier (2.0 = double speed).
    """
    if not frames:
        return

    yield frames[0]

    for i in range(1, len(frames)):
        # Try to compute delay from timestamps
        try:
            from datetime import datetime
            t1 = datetime.fromisoformat(frames[i - 1].timestamp)
            t2 = datetime.fromisoformat(frames[i].timestamp)
            delay = (t2 - t1).total_seconds() / speed
            if delay > 0:
                time.sleep(min(delay, 10.0))  # Cap at 10s
        except (ValueError, TypeError):
            time.sleep(2.0 / speed)

        yield frames[i]
