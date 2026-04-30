# Weather Station

POCS integrates with the **AAG CloudWatcher** weather station out of the box, but it can
work with **any weather source** — a different sensor, a scraper for a local weather API,
or a home-built station — as long as you write records in the expected JSON format to the
`weather` database collection.

## How It Works

```
Weather source ──────────────────► DB "weather" collection
(AAG CloudWatcher, adapter script,         │
 or any custom integration)                ▼
                               POCS.is_weather_safe()  ──► allow / deny observations
```

The only thing `POCS.is_weather_safe()` cares about is the **most recent document** in
the `weather` collection. It reads two fields and makes a go/no-go decision:

| Field | Required | Description |
|---|---|---|
| `is_safe` | **yes** | `true` = conditions are safe to observe |
| `timestamp` | **yes** | ISO 8601 string; records older than 180 s are treated as unsafe |

---

## Building a Custom Integration

If you are using a non-AAG sensor, scraping a weather page, or writing an adapter script,
this is the section for you.

### Minimum Viable Record

The smallest record POCS will act on:

```json
{
    "is_safe": true,
    "timestamp": "2024-01-15T10:30:00.123456"
}
```

That's it. Write a document with those two fields to the `weather` collection on the
configured interval and POCS will use it to gate observations.

### Example Adapter Script

```python
#!/usr/bin/env python3
"""Minimal weather adapter — scrapes an external source and writes to POCS DB."""

from datetime import UTC, datetime

from panoptes.utils.database import PanDB

db = PanDB()  # uses the same DB backend as POCS


def is_currently_safe() -> bool:
    """Replace this with your own safety logic."""
    # e.g. call a local weather API, read a sensor, scrape a web page …
    return True


def write_weather_record() -> None:
    record = {
        "is_safe": is_currently_safe(),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    db.insert_current("weather", record)
    print(f"Wrote: {record}")


if __name__ == "__main__":
    import time

    while True:
        write_weather_record()
        time.sleep(60)
```

Run this script alongside POCS and it will keep the `weather` collection up to date.
POCS will stop observing if the script stops writing (records go stale after 180 s).

!!! tip "Adding more detail"
    You can include any extra fields you like alongside the two required ones.
    The full schema used by the built-in AAG integration is described
    [below](#full-json-schema). Including those extra fields makes your records
    visible in `pocs weather status` output.

---

## Full JSON Schema

The built-in AAG CloudWatcher integration writes all of the following fields.
Custom integrations may include any subset (only `is_safe` and `timestamp` are required),
or additional fields of their own.

### Measurement Fields

| Field | Type | Unit | Description |
|---|---|---|---|
| `timestamp` | `str` | — | ISO 8601 datetime of the reading, e.g. `"2024-01-15T10:30:00.123456"` |
| `ambient_temp` | `float` | °C | Ambient (air) temperature |
| `sky_temp` | `float` | °C | Sky infrared temperature; the difference `sky_temp − ambient_temp` indicates cloud cover |
| `wind_speed` | `float` | m/s | Wind speed |
| `rain_frequency` | `float` | — | Raw rain-sensor frequency; higher values mean drier conditions |
| `pwm` | `float` | % | Heater element duty cycle |

### Condition Fields

Derived by comparing the measurements against configurable thresholds
(see `environment.weather` in `conf_files/pocs.yaml`).

| Field | Type | Possible Values |
|---|---|---|
| `cloud_condition` | `str` | `"clear"`, `"cloudy"`, `"very cloudy"`, `"unknown"` |
| `wind_condition` | `str` | `"calm"`, `"windy"`, `"very windy"`, `"gusty"`, `"very gusty"`, `"unknown"` |
| `rain_condition` | `str` | `"dry"`, `"wet"`, `"rainy"`, `"unknown"` |

### Safety Fields

| Field | Type | Description |
|---|---|---|
| `cloud_safe` | `bool` | `True` when `cloud_condition == "clear"` |
| `wind_safe` | `bool` | `True` when `wind_condition == "calm"` |
| `rain_safe` | `bool` | `True` when `rain_condition == "dry"` |
| `is_safe` | `bool` | `True` only when **all three** of `cloud_safe`, `wind_safe`, and `rain_safe` are `True` |

### Full Example Record

```json
{
    "timestamp": "2024-01-15T10:30:00.123456",
    "ambient_temp": 15.5,
    "sky_temp": -25.0,
    "wind_speed": 2.3,
    "rain_frequency": 2700.0,
    "pwm": 75.0,
    "cloud_condition": "clear",
    "wind_condition": "calm",
    "rain_condition": "dry",
    "cloud_safe": true,
    "wind_safe": true,
    "rain_safe": true,
    "is_safe": true
}
```

---

## Safety Evaluation

`POCS.is_weather_safe()` reads the latest `weather` record from the database and
applies two checks:

1. **Safety flag** — looks for `is_safe` (then falls back to `safe`) and casts it to `bool`.
2. **Staleness** — compares `timestamp` to the current time. If the record is older
   than `stale` seconds (default **180 s**) the record is treated as unsafe regardless
   of the flag value.

This means **any integration that stops writing records will automatically halt
observations** after the staleness window expires.

---

## HTTP API

The weather FastAPI service (default port **6566**) exposes two endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `/status` | `GET` | Returns the most recent reading as a JSON object (schema above) |
| `/config` | `GET` | Returns the active weather station configuration |

### Querying via the CLI

```bash
# Show a formatted status table
pocs weather status

# Show raw JSON
pocs weather status --show-raw-values

# Show configuration
pocs weather config

# Connect to a remote unit
pocs weather --host 192.168.1.100 --port 6566 status
```

---

## AAG CloudWatcher Configuration

For the built-in AAG integration, settings live under `environment.weather` in your
config file:

```yaml
environment:
  weather:
    serial_port: /dev/weather   # or /dev/ttyUSB0
    auto_detect: false          # set true to probe all ttyUSB* ports
    record_interval: 60         # seconds between DB writes
    store_permanently: false    # keep every reading, not just the latest
```

To set up the stable `/dev/weather` symlink automatically, run:

```bash
pocs weather setup
```

This scans USB serial ports, identifies the AAG CloudWatcher by its handshake response,
and writes a udev rule to `/etc/udev/rules.d/92-panoptes-weather.rules`.
