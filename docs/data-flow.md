# Data Flow

Detailed data flow documentation for readsb-feed-dashboard.

## Collection Cycle

Each refresh cycle performs the following operations per feed:

```mermaid
flowchart TD
    Start([Refresh Tick]) --> ReadJSON[Read aircraft.json]
    ReadJSON --> ValidatePath{Path valid?}
    ValidatePath -->|Resolves under /run /tmp /var| ParseJSON{Parse JSON}
    ValidatePath -->|Outside allowed dirs| SetError[Set json_error]
    ParseJSON -->|Valid| ExtractAircraft[Extract aircraft entries]
    ParseJSON -->|Missing| SetMissing[Set json_exists=false]
    ParseJSON -->|Malformed| SetError

    ExtractAircraft --> ComputeDistance[Compute distance via haversine]
    ComputeDistance --> CheckStale{File age > threshold?}
    CheckStale -->|Yes| MarkStale[Set json_stale=true]
    CheckStale -->|No| MarkLive[Set json_stale=false]

    MarkStale --> ComputeMetrics[Compute RSSI / rings / types]
    MarkLive --> ComputeMetrics
    SetMissing --> CheckService[Query systemd]
    SetError --> CheckService

    ComputeMetrics --> CheckService
    CheckService --> CheckUptime[Get service uptime]
    CheckUptime --> DetectPorts[Detect listening ports - cached 30s]
    DetectPorts --> ProcessStats[Read /proc - CPU/memory/network]
    ProcessStats --> MessageRate[Compute msgs/sec delta]
    MessageRate --> Sparkline[Update sparkline history]
    Sparkline --> Alerts[Check alert thresholds]
    Alerts --> Done([FeedData complete])
```

## Distance Calculation

```mermaid
flowchart TD
    A[Aircraft has lat/lon?] -->|No| B[Distance = null]
    A -->|Yes| C{r_dst in JSON?}
    C -->|Yes| D[Use r_dst directly]
    C -->|No| E{Receiver position known?}
    E -->|Config receiver_lat/lon| F[Haversine calculation]
    E -->|receiver.json in same dir| F
    E -->|receiver.json in sibling dir| F
    E -->|Not found| B
    F --> G[Distance in nautical miles]
```

## Overlap Computation

For "unique" counts, SDR feeds are compared against other SDR feeds only (the merge feed is excluded since it contains everything):

```mermaid
flowchart LR
    A[SDR1 hex set] --> DiffAB{SDR1 - SDR2}
    DiffAB --> UniqueA[Unique to SDR1]

    B[SDR2 hex set] --> DiffBA{SDR2 - SDR1}
    DiffBA --> UniqueB[Unique to SDR2]

    A --> Intersect{SDR1 AND SDR2}
    B --> Intersect
    Intersect --> Shared[Shared between SDRs]

    C[MERGED hex set] --> DiffM{MERGED - all SDRs}
    DiffM --> UniqueM[Unique to MERGED - usually 0]
```

For N SDR feeds:
- `unique_to[i]` = aircraft seen by SDR i but not by any other SDR
- `shared[i][j]` = aircraft seen by both feed i and feed j
- `total_unique` = union of all hex sets across all feeds

## External Feeder Collection

```mermaid
flowchart TD
    A[collect_external_feeders] --> B{fr24feed-status on PATH?}
    B -->|No| C[Return empty]
    B -->|Yes| D[Run fr24feed-status]
    D --> E[Parse output lines]
    E --> F{/run/fr24feed/fr24feed.json exists?}
    F -->|Yes| G[Parse additional stats]
    F -->|No| H[Return parsed status]
    G --> H
```

## JSON Schema (aircraft.json)

readsb writes the following structure:

```json
{
  "now": 1705312327.4,
  "messages": 123456,
  "aircraft": [
    {
      "hex": "4ca87d",
      "type": "adsb_icao",
      "flight": "RYR3456 ",
      "alt_baro": 37000,
      "alt_geom": 37425,
      "gs": 482.3,
      "track": 127.4,
      "squawk": "2431",
      "rssi": -3.2,
      "lat": 51.234,
      "lon": -1.456,
      "r_dst": 42.1,
      "seen": 0.3,
      "seen_pos": 1.2
    }
  ]
}
```

## Fields Used by Dashboard

| JSON Field | Dashboard Column | Notes |
|---|---|---|
| `hex` | Hex | ICAO 24-bit address |
| `flight` | Flight | Callsign (may have trailing spaces, trimmed) |
| `alt_baro` | Alt | Barometric altitude in feet |
| `gs` | Spd | Ground speed in knots |
| `rssi` | RSSI | Signal strength in dBFS (colour-coded) |
| `squawk` | Sqk | Transponder squawk code |
| `r_dst` | Dist | Distance from receiver in nautical miles |
| `lat`/`lon` | (used for distance) | Aircraft position |
| `seen` | Seen | Seconds since last message (1 decimal) |
| `type` | Type | Message type (adsb_icao, mlat, tisb, mode_s) |
| `messages` | (used for rate) | Total message count for msgs/sec calculation |

## Message Rate Computation

```mermaid
sequenceDiagram
    participant Cycle1 as Cycle N
    participant History as FeedHistory
    participant Cycle2 as Cycle N+1

    Cycle1->>History: Store messages=100000, time=T1
    Note over History: First cycle, rate=null

    Cycle2->>History: Store messages=104000, time=T2
    History->>History: delta = 104000 - 100000 = 4000
    History->>History: dt = T2 - T1 = 2.0s
    History->>Cycle2: rate = 4000 / 2.0 = 2000 msgs/sec
```
