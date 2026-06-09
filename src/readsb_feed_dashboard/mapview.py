"""ASCII map view — polar plot of aircraft positions relative to receiver."""

import math
from typing import Optional

from .collector import AircraftEntry


def render_map(
    aircraft: list[AircraftEntry],
    receiver_lat: Optional[float],
    receiver_lon: Optional[float],
    width: int = 60,
    height: int = 30,
    max_range_nm: float = 200.0,
) -> str:
    """Render an ASCII polar map of aircraft positions.

    Returns a multi-line string representing the map.
    Aircraft are plotted as dots relative to the receiver at centre.
    """
    if receiver_lat is None or receiver_lon is None:
        return "(No receiver position — cannot render map)"

    # Create the canvas
    canvas = [[" " for _ in range(width)] for _ in range(height)]

    cx = width // 2
    cy = height // 2

    # Draw crosshairs
    for x in range(width):
        canvas[cy][x] = "."
    for y in range(height):
        canvas[y][cx] = "."
    canvas[cy][cx] = "+"

    # Draw range rings (quarter, half, full)
    for ring_frac in [0.25, 0.5, 0.75, 1.0]:
        r_chars_x = int(cx * ring_frac)
        r_chars_y = int(cy * ring_frac)
        # Draw simple ring markers at cardinal points
        for angle in range(0, 360, 15):
            rad = math.radians(angle)
            px = int(cx + r_chars_x * math.sin(rad))
            py = int(cy - r_chars_y * math.cos(rad))
            if 0 <= px < width and 0 <= py < height and canvas[py][px] == " ":
                canvas[py][px] = ":"

    # Plot aircraft
    for ac in aircraft:
        if ac.lat is None or ac.lon is None:
            continue

        # Compute bearing and distance from receiver
        dist_nm = _haversine(receiver_lat, receiver_lon, ac.lat, ac.lon)
        bearing = _bearing(receiver_lat, receiver_lon, ac.lat, ac.lon)

        if dist_nm > max_range_nm:
            continue

        # Convert to canvas coordinates
        frac = dist_nm / max_range_nm
        rad = math.radians(bearing)
        px = int(cx + frac * cx * math.sin(rad))
        py = int(cy - frac * cy * math.cos(rad))

        if 0 <= px < width and 0 <= py < height:
            canvas[py][px] = "*"

    # Add labels
    lines = []
    lines.append(f"{'N':^{width}}")
    for row in canvas:
        lines.append("".join(row))
    lines.append(f"{'S':^{width}}")

    # Add W and E markers to middle row
    if len(lines) > cy + 1:
        mid_line = list(lines[cy + 1])
        mid_line[0] = "W"
        mid_line[-1] = "E"
        lines[cy + 1] = "".join(mid_line)

    # Legend
    lines.append(f"  + = receiver  * = aircraft  Range: {max_range_nm:.0f} nm")

    return "\n".join(lines)


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles."""
    R = 3440.065
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2, in degrees (0=N, 90=E)."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360
