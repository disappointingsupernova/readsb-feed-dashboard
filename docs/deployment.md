# Deployment

## Standard Deployment (Single Pi)

```mermaid
graph TD
    subgraph "Raspberry Pi"
        SDR1[RTL-SDR #1] --> RS1[readsb-sdr1]
        SDR2[RTL-SDR #2] --> RS2[readsb-sdr2]
        RS1 -->|Beast TCP| RM[readsb-merge]
        RS2 -->|Beast TCP| RM
        RM -->|Port 30005| Feeders[Feed aggregators]
        RM -->|Port 30003| SBS[SBS clients]

        RS1 -->|aircraft.json| JSON1[/run/readsb-sdr1/]
        RS2 -->|aircraft.json| JSON2[/run/readsb-sdr2/]
        RM -->|aircraft.json| JSON3[/run/readsb/]

        JSON1 --> Dashboard[readsb-feed-dashboard]
        JSON2 --> Dashboard
        JSON3 --> Dashboard
    end

    Dashboard -->|Terminal| User((User))
```

## Multi-Pi Deployment (Future)

```mermaid
graph TD
    subgraph "Pi A (Rooftop)"
        SDRA[RTL-SDR] --> RSA[readsb-sdr1]
        RSA -->|Beast TCP :30005| Network
    end

    subgraph "Pi B (Ground)"
        SDRB[RTL-SDR] --> RSB[readsb-sdr2]
        RSB -->|Beast TCP :30005| Network
    end

    subgraph "Pi C (Merge Server)"
        Network -->|net-connector| RMC[readsb-merge]
        RMC -->|aircraft.json| Dashboard[readsb-feed-dashboard]
    end
```

## Service Dependencies

```mermaid
graph LR
    A[readsb-sdr1.service] -->|Beast out| C[readsb.service / readsb-merge.service]
    B[readsb-sdr2.service] -->|Beast out| C
    C -->|30005| D[External feeders]
    C -->|30003| E[SBS consumers]
    C -->|JSON| F[tar1090 / Dashboard]
```

## Port Allocation Convention

| Service | Beast Out | SBS Out | Beast Reduce |
|---|---|---|---|
| readsb-sdr1 | 30105 | - | - |
| readsb-sdr2 | 30205 | - | - |
| readsb-sdr3 | 30305 | - | - |
| readsb / merge | 30005 | 30003 | 30006 |
