# Architecture

## Overview

readsb-feed-dashboard is a Python application using the Rich library for terminal rendering. It follows a collect-render loop architecture with stateful history for sparklines and rate calculations.

## Module Structure

```mermaid
graph TD
    A[__main__.py] --> B[config.py]
    A --> C[collector.py]
    A --> D[renderer.py]
    A --> U[feeders.py]
    B --> E[/etc/readsb-feed-dashboard.conf]
    B --> F[Auto-detection]
    F --> G[systemd]
    F --> H[/run/readsb*/aircraft.json]
    F --> I[/etc/default/readsb*]
    F --> T[tmux/screen detection]
    C --> H
    C --> G
    C --> J[ss / ports]
    C --> K[/proc/PID/status - memory]
    C --> L[/proc/PID/stat - CPU]
    C --> M[/proc/PID/net/dev - network]
    C --> N[Remote HTTP feeds]
    C --> O[FeedHistory - rates + sparklines]
    C --> V[receiver.json - position]
    U --> W[fr24feed-status]
    U --> X[/run/fr24feed/fr24feed.json]
    D --> P[Rich Library]
    P --> Q[Terminal Output]
    A --> R[CSV Logger]
    A --> S[JSON Exporter]
```

## Data Flow

```mermaid
sequenceDiagram
    participant Main as __main__.py
    participant Config as config.py
    participant History as FeedHistory
    participant Collector as collector.py
    participant Feeders as feeders.py
    participant Renderer as renderer.py
    participant Term as Terminal

    Main->>Config: Load or auto-detect config
    Config-->>Main: DashboardConfig
    Main->>History: init_history(sparkline_length)
    Main->>Feeders: collect_external_feeders()
    Feeders-->>Main: ExternalFeeders (cached 30s)

    loop Every refresh_interval seconds
        Main->>Collector: collect_feed_data(feed_config, config)
        Collector->>Collector: Read aircraft.json (local or remote)
        Collector->>Collector: Compute distance (haversine)
        Collector->>Collector: Compute RSSI stats
        Collector->>Collector: Compute distance rings
        Collector->>Collector: Compute type breakdown
        Collector->>Collector: Check systemd service + uptime
        Collector->>Collector: Check ports (cached 30s)
        Collector->>Collector: Check CPU/memory from /proc
        Collector->>Collector: Check network I/O from /proc
        Collector->>History: Compute message rate (delta)
        Collector->>History: Update sparkline data
        Collector->>Collector: Check alert thresholds
        Collector-->>Main: FeedData

        Main->>Collector: compute_overlaps(feeds)
        Collector-->>Main: Overlap statistics (SDR vs SDR)

        opt Every 30 seconds
            Main->>Feeders: collect_external_feeders()
            Feeders-->>Main: Updated ExternalFeeders
        end

        Main->>Renderer: render_dashboard(config, feeds, focused_feed, external_feeders)
        Renderer->>History: get_sparkline_data()
        Renderer->>Renderer: Build header, alerts, FR24, summary, panels, tables
        Renderer-->>Main: Rich renderable

        Main->>Term: Live.update(renderable)
        Main->>Main: Poll keyboard input
        opt Logging enabled
            Main->>Main: log_cycle() -> CSV (with rotation)
        end
    end
```

## Component Responsibilities

### config.py

- Loads JSON configuration files (with 1 MB size limit)
- Auto-detects readsb instances from filesystem and systemd
- Parses `/etc/default/readsb*` for serial numbers and ports
- Detects terminal Unicode capabilities
- Detects tmux/screen for auto-throttling
- Defines colour themes (dark, light, solarised)
- Defines alert configuration

### collector.py

- Reads and parses local `aircraft.json` files safely
- Validates paths against allowed prefixes (`/run/`, `/tmp/`, `/var/`)
- Fetches remote `aircraft.json` over HTTP (with SSRF protection)
- Validates service names against strict regex before subprocess calls
- Handles missing, stale, malformed, or empty JSON
- Computes aircraft distance via haversine from receiver position
- Computes per-feed metrics:
  - Position-tracked aircraft count
  - RSSI min/avg/max statistics
  - Distance ring distribution
  - Aircraft type breakdown (ADS-B, MLAT, TIS-B, Mode-S)
- Queries systemd for service status and uptime
- Detects listening ports (with 30-second cache)
- Reads CPU and memory from `/proc/<pid>/` (with process name verification)
- Reads network I/O from `/proc/<pid>/net/dev`
- Maintains `FeedHistory` for message rate calculation and sparkline data
- Checks alert thresholds

### feeders.py

- Auto-detects `fr24feed-status` on PATH
- Parses FR24 feeder output (process state, link status, radar ID, aircraft counts)
- Reads `/run/fr24feed/fr24feed.json` for additional stats
- Checks fr24feed systemd service status
- Validates command names before execution

### renderer.py

- Builds Rich renderables (Panels, Tables, Columns)
- Renders sparkline graphs from history data
- Colour-codes RSSI values (green/yellow/red)
- Applies configurable themes
- Supports configurable sort order
- Supports focused single-feed view
- Supports compact mode (no aircraft tables)
- Renders alerts panel when thresholds are breached
- Renders FR24 feeder panel when detected
- Places aircraft tables side-by-side on wide terminals

### __main__.py

- CLI argument parsing (15+ flags)
- Main event loop with Rich Live
- Non-blocking keyboard input handling (select + termios)
- Signal handling for clean exit
- Terminal state always restored in finally block
- CSV logging per cycle with 50 MB rotation
- JSON export mode
- Watchdog mode for monitoring integration
- Update mechanism (uses venv pip)

## Keyboard Input Architecture

```mermaid
flowchart TD
    A[Main Loop Tick] --> B[Collect + Render]
    B --> C[Poll stdin with select()]
    C -->|Key pressed| D{Which key?}
    C -->|Timeout| A

    D -->|q| E[Exit]
    D -->|s| F[Toggle compact mode]
    D -->|f| G[Cycle sort order]
    D -->|1-9| H[Focus feed N]
    D -->|0| I[Reset to all-feeds view]

    F --> J[Force re-render]
    G --> J
    H --> J
    I --> J
    J --> A
```

## Caching Strategy

| Data | Cache TTL | Rationale |
|---|---|---|
| Listening ports | 30 seconds | Ports rarely change |
| FR24 feeder status | 30 seconds | External command, expensive |
| Service status | 0 (every cycle) | Can change at any time |
| Aircraft JSON | 0 (every cycle) | Core data, must be fresh |
| Process stats | 0 (every cycle) | Useful for live monitoring |
| Network I/O | 0 (computed as delta) | Needs continuous sampling |

## Security Architecture

```mermaid
flowchart TD
    A[User Input] --> B{Config file}
    B -->|json_path| C{Path validation}
    C -->|resolve + prefix check| D[Read file]
    C -->|Outside /run /tmp /var| E[REJECT]

    B -->|json_url| F{URL validation}
    F -->|http/https + non-blocked host| G[Fetch with SSL context]
    F -->|file:// or metadata IP| H[REJECT]

    B -->|service_name| I{Regex validation}
    I -->|^[a-zA-Z0-9_.@-]+$| J[Pass to systemctl]
    I -->|Invalid chars| K[REJECT]

    B -->|File size| L{Size check}
    L -->|> 1 MB| M[REJECT]
    L -->|<= 1 MB| N[Parse JSON]
```

## Design Decisions

| Decision | Rationale |
|---|---|
| Python + Rich over Bash | Better JSON parsing, error handling, layout, Unicode support |
| No curses dependency | Rich handles terminal abstraction more cleanly |
| JSON config format | Easy to generate, parse, and version control |
| Auto-detection as default | Works out-of-the-box on standard readsb setups |
| Dedicated venv | Avoids PEP 668 externally-managed-environment errors |
| FeedHistory as module singleton | Maintains state across refresh cycles without global mutable state |
| Port cache with TTL | Avoids shelling out to ss every 2 seconds |
| select() for keyboard | Non-blocking input without threads |
| Unique = SDR vs SDR only | Merge feed contains everything, comparing against it is meaningless |
| No database | Stateless reads + lightweight in-memory history |
| No web server | Pure terminal — simple, secure, low overhead |

## Error Handling Strategy

```mermaid
graph LR
    A[Read aircraft.json] -->|File missing| B[Show NOT FOUND]
    A -->|Permission denied| C[Show ERROR]
    A -->|Malformed JSON| D[Show ERROR]
    A -->|Path outside allowed dirs| E[Show ERROR]
    A -->|Stale > threshold| F[Show STALE]
    A -->|Valid| G[Show LIVE + data]

    H[Remote HTTP fetch] -->|Blocked URL| I[Show ERROR]
    H -->|Timeout| J[Show ERROR]
    H -->|Invalid JSON| K[Show ERROR]
    H -->|Success| L[Show LIVE]

    M[Check systemd] -->|active| N[Green]
    M -->|inactive| O[Red + Alert]
    M -->|failed| P[Red + Alert]
    M -->|invalid name| Q[Skip]
    M -->|systemctl missing| R[Show unknown]

    S[Read /proc] -->|PID gone| T[Skip gracefully]
    S -->|Wrong process name| U[Skip - PID recycled]
    S -->|Permission denied| V[Skip gracefully]
```
