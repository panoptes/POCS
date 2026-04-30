# Weather Station

POCS integrates with the **AAG CloudWatcher** weather station via a thin wrapper class
([`WeatherStation`][panoptes.pocs.sensor.weather.WeatherStation]) and a FastAPI service that
exposes the readings over HTTP.

## How It Works

```
AAG CloudWatcher ──serial──► WeatherStation.record()
                                     │
                                     ▼
                              DB "weather" collection
                                     │
                                     ▼
                          POCS.is_weather_safe()  ──► allow / deny observations
```

1. The `WeatherStation` reads data from the sensor over a serial port.
2. `record()` is called on a configurable interval (default 60 s) and writes the
   latest snapshot to the `weather` database collection.
3. `POCS.is_weather_safe()` reads the most recent record from that collection and
   decides whether observing is safe.

---

## JSON Reading Schema

Every weather record written to the database contains the following fields.

### Measurement Fields

| Field | Type | Unit | Description |
|---|---|---|---|
| `timestamp` | `str` | — | ISO 8601 datetime of the reading, e.g. `"2024-01-15T10:30:00.123456"` |
| `ambient_temp` | `float` | °C | Ambient (air) temperature |
| `sky_temp` | `float` | °C | Sky infrared temperature. The difference `sky_temp − ambient_temp` is used to infer cloud cover |
| `wind_speed` | `float` | m/s | Wind speed |
| `rain_frequency` | `float` | — | Raw rain-sensor frequency value; higher values indicate drier conditions |
| `pwm` | `float` | % | Heater element duty cycle |

### Condition Fields

Condition strings are derived by comparing the measurements against configurable thresholds
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

### Example Record

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

[`POCS.is_weather_safe()`][panoptes.pocs.core.POCS.is_weather_safe] reads the latest
`weather` record from the database and applies two checks:

1. **Safety flag** — looks for `is_safe` (then `safe`) and casts it to `bool`.
2. **Staleness** — compares `timestamp` to the current time. If the record is older
   than `stale` seconds (default **180 s**) the record is treated as unsafe regardless
   of the flag value.

!!! warning "Custom weather integrations"
    If you write weather data directly to the `weather` database collection from a
    custom source, your records **must** include at minimum:

    - `is_safe` (*bool*) — the overall safety decision
    - `timestamp` (*str*) — ISO 8601 datetime so staleness can be evaluated

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

## Configuration

Weather station settings live under `environment.weather` in your config file:

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
