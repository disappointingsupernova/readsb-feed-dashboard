"""Aircraft database lookup — resolve ICAO hex to registration, type, and operator."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AircraftInfo:
    """Looked-up aircraft information."""

    registration: Optional[str] = None
    ac_typecode: Optional[str] = None
    operator: Optional[str] = None


# In-memory database (loaded once)
_db: dict[str, AircraftInfo] = {}
_loaded: bool = False

# Search paths for aircraft database files
_DB_PATHS = [
    Path("/usr/share/readsb-feed-dashboard/aircraftdb.csv"),
    Path("/opt/readsb-feed-dashboard/data/aircraftdb.csv"),
    Path("/usr/local/share/tar1090/aircraft.csv"),
    Path("/run/readsb/aircraftdb.csv"),
]


def load_database(custom_path: Optional[str] = None) -> int:
    """Load the aircraft database from CSV. Returns number of entries loaded.

    Expected CSV format: hex,registration,typecode,operator
    (No header row, or first row starting with '#' is skipped)
    """
    global _db, _loaded

    if _loaded:
        return len(_db)

    db_path = None
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            db_path = p
    else:
        for candidate in _DB_PATHS:
            if candidate.exists():
                db_path = candidate
                break

    if not db_path:
        _loaded = True
        return 0

    # Limit file size (50 MB max for the DB)
    try:
        if db_path.stat().st_size > 50_000_000:
            _loaded = True
            return 0
    except OSError:
        _loaded = True
        return 0

    try:
        with open(db_path, "r", newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0].startswith("#"):
                    continue
                if len(row) < 2:
                    continue
                hex_code = row[0].strip().lower()
                if not hex_code:
                    continue
                _db[hex_code] = AircraftInfo(
                    registration=row[1].strip() if len(row) > 1 and row[1].strip() else None,
                    ac_typecode=row[2].strip() if len(row) > 2 and row[2].strip() else None,
                    operator=row[3].strip() if len(row) > 3 and row[3].strip() else None,
                )
    except (OSError, csv.Error):
        pass

    _loaded = True
    return len(_db)


def lookup(hex_code: str) -> Optional[AircraftInfo]:
    """Look up aircraft info by ICAO hex code."""
    if not _loaded:
        load_database()
    return _db.get(hex_code.lower().strip())


def is_loaded() -> bool:
    """Check whether the database has been loaded."""
    return _loaded and len(_db) > 0
