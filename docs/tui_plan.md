# POCS Terminal UI Dashboard Plan (pocs-tui)

## Goals

| Goal | Why it matters | Initial deliverable |
|---|---|---|
| Live observatory situational awareness | Operators need one-glance status for safety, hardware, and observation progress | Dashboard-focused TUI with summary panels |
| Safe keyboard controls | Common actions should be fast but auditable | Centralized actions module + command log |
| Responsive rendering | UI must stay smooth under ongoing scans | 20 FPS render loop + non-blocking renderer |
| Clear architecture boundaries | Keeps future implementation maintainable | Strict model / scanner / render / input / actions split |
| Testable foundations | Enables iterative delivery without regressions | Importable stdlib-first skeleton + focused tests |

## Lessons from milk-CTRL mapped to POCS

| milk concept | milk files | POCS equivalent |
|---|---|---|
| Strict model/render/input split | `overview_data.h`, `overview_render*.c`, `overview_input.c` | `model.py`, panel render modules, `input.py` |
| Double-buffer model swap | `OV_MODEL` front/back pair + lock | `Scanner` front/back `POCSModel` references guarded by `threading.Lock` |
| Polling scan thread + force wake | `overview_scan.c`, `ov_scan_force_update()` | `Scanner` background loop using `Event.wait(timeout)` + `force_update()` |
| Sparkline ring buffers | `spark_rate[]`, `hz_hist[]` | `progress_hist` in `CameraModel`, shared sparkline helper in `theme.py` |
| Command log ring | `OV_CMDLOG` | `CmdLog` with `deque(maxlen=64)` and severity level |
| Panel regex filtering | `ov_filter_build()` | `/` enters filter mode, `Esc` clears filter in input/action flow |
| Theme separated from render | `overview_theme.h`, `overview_ansi.h` | `theme.py` keeps chars, palette, and color-pair setup |
| Geometry as computed rects | `OV_LAYOUT`, `OV_RECT`, `ov_layout_compute()` | `Rect`, `Layout`, and `layout_compute()` |
| Isolated control side effects | `overview_ctrl.c` | `actions.py` action functions + cmdlog helper |

## Data model (`model.py`)

```python
from dataclasses import dataclass, field
from collections import deque

SPARKLINE_LEN = 40

@dataclass(slots=True)
class SafetyModel:
    ac_power: bool = False
    is_dark: bool = False
    good_weather: bool = False
    free_space_root: float = 0.0
    free_space_images: float = 0.0
    age_s: float = 0.0

@dataclass(slots=True)
class MountModel:
    connected: bool = False
    is_parked: bool = True
    is_tracking: bool = False
    is_slewing: bool = False
    ra: str = "--"
    dec: str = "--"
    ha: str = "--"
    alt: str = "--"
    az: str = "--"

@dataclass(slots=True)
class CameraModel:
    name: str = ""
    connected: bool = False
    is_exposing: bool = False
    temperature: str = "--"
    filter_name: str = "--"
    last_image: str = ""
    progress_hist: deque[float] = field(default_factory=lambda: deque(maxlen=SPARKLINE_LEN))

@dataclass(slots=True)
class ObservationModel:
    field_name: str = ""
    exposure_s: float = 0.0
    current_exp_num: int = 0
    merit: float = 0.0

@dataclass(slots=True)
class SchedulerModel:
    available_fields: int = 0
    selected_field: str = ""
    observing: ObservationModel = field(default_factory=ObservationModel)

@dataclass(slots=True)
class FocuserModel:
    connected: bool = False
    position: int = 0
    is_moving: bool = False

@dataclass(slots=True)
class DomeModel:
    connected: bool = False
    is_open: bool = False
    is_moving: bool = False

@dataclass(slots=True)
class SystemModel:
    state: str = "unknown"
    next_state: str = ""
    initialized: bool = False
    connected: bool = False
    free_space: float = 0.0
    uptime: str = "--"

@dataclass(slots=True)
class POCSModel:
    safety: SafetyModel = field(default_factory=SafetyModel)
    mount: MountModel = field(default_factory=MountModel)
    cameras: list[CameraModel] = field(default_factory=list)
    scheduler: SchedulerModel = field(default_factory=SchedulerModel)
    focuser: FocuserModel = field(default_factory=FocuserModel)
    dome: DomeModel = field(default_factory=DomeModel)
    system: SystemModel = field(default_factory=SystemModel)
    scan_time_ms: float = 0.0
    scan_count: int = 0
```

## Scanner design (`scanner.py`)

- Owns a background thread that repeatedly scans POCS state and updates the model.
- Uses a lock-protected front/back model reference swap so renderer always reads complete snapshots.
- Uses:
  - `Event` stop flag for shutdown,
  - `Event` force-wake flag for immediate post-action refresh,
  - periodic wake via `wait(timeout=interval_s)`.
- `_scan()` is exception-isolated: errors are captured and do not crash render loop.
- Public methods:
  - `start()`
  - `stop()`
  - `snapshot()`
  - `force_update()`

## Views and key panel routing

| View | Key | Purpose |
|---|---|---|
| `DASHBOARD` | `F1` | High-level observatory status |
| `HARDWARE` | `F2` | Mount/camera/focuser/dome detail |
| `SCHEDULER` | `F3` | Candidate/active observation detail |
| `SAFETY` | `F4` | Weather, darkness, power, disk safety |
| `HELP` | `?` / `F5` | Keybindings and operator hints |

## Dashboard layout mockup

```text
+------------------------------------------------------------------------------------------------+
| POCS TUI  state=observing  next=tracking  uptime=01:42:09                           F1..F5 ? |
+---------------------------------------------+-----------------------------------------------+
| SAFETY                                      | OBSERVATION                                   |
| power: OK  dark: YES  weather: GOOD         | field: M42                                     |
| root: 88% free  images: 72% free            | exp: 45/120  exptime: 30s                      |
+---------------------------------------------+-----------------------------------------------+
| MOUNT                                       | CAMERAS                                       |
| parked: no  tracking: yes  slewing: no      | Cam00 exposing temp=-10C filter=L              |
| ra=05:35:17 dec=-05:23:28 ha=+00:11:04      | progress ▁▂▃▅▆▇██                               |
| alt=62.1 az=181.7                           | Cam01 idle temp=-10C filter=R                  |
+---------------------------------------------+-----------------------------------------------+
| CMDLOG                                                                                        |
| 02:11:42 INFO  action_park requested by key 'p'                                               |
| 02:12:01 WARN  action aborted: mount not connected                                             |
+------------------------------------------------------------------------------------------------+
| /filter:                                                                                       |
+------------------------------------------------------------------------------------------------+
```

## Layout dataclasses

- `Rect(x, y, w, h)`
- `Layout` fields:
  - `screen`, `header`, `footer`, `status_bar`, `filter_bar`,
  - `left_top`, `right_top`, `left_mid`, `right_mid`, `cmdlog`,
  - `active_view`, `focus`, `width`, `height`.
- `layout_compute(lay)` recomputes all rects on resize and view changes.

## Render layer conventions

- Never block in render path.
- Every panel draws only inside its assigned `Rect`.
- Clip/truncate all text to width.
- Use Unicode sparklines for bounded historical series.
- Read color/style only from `theme.py` constants and initialized pairs.

## Input map (`input.py`)

`KEY_MAP` targets these actions:

- `q` → quit
- `p` → park
- `a` → abort exposure
- `space` → pause/resume scan
- `/` → start filter entry
- `?` → help view
- `F1..F5` → view switching
- arrows → move focus/selection
- `Enter` → activate focused control
- `Esc` → clear filter/cancel mode

`dispatch(action, ...)` remains a thin routing shim to action handlers.

## Action layer (`actions.py`)

Initial action stubs:

- `action_park(pocs, cmdlog)`
- `action_abort_exposure(pocs, cmdlog)`
- `action_snapshot(pocs, cmdlog)`

Rules:

- All side effects go through this module.
- Every attempt and outcome writes to `CmdLog` via `cmdlog_push()`.

## Command log (`cmdlog.py`)

- `LogEntry(ts, level, msg)` dataclass.
- `CmdLog` with thread-safe `deque(maxlen=64)` storage.
- API:
  - `push(level, msg)`
  - `tail(n)`

## Main loop sketch (`__main__.py`)

- Entry through `curses.wrapper(main)`.
- Start scanner.
- Loop at 20 FPS:
  1. read input,
  2. dispatch action,
  3. fetch scanner snapshot,
  4. compute layout,
  5. render active panels,
  6. `stdscr.refresh()`.
- On exit: stop scanner, restore terminal state.

## Planned file structure

```text
src/panoptes/pocs/tui/
├── __init__.py
├── __main__.py
├── model.py
├── scanner.py
├── layout.py
├── theme.py
├── cmdlog.py
├── input.py
├── actions.py
└── panels/
    └── __init__.py
```

## Dependencies

- Standard library (`curses`, `threading`, `dataclasses`, `collections`, etc.).
- Existing POCS dependencies only.
- No new third-party TUI framework in initial implementation.

## Testing strategy

- `model.py`: dataclass defaults and ring-buffer behavior.
- `cmdlog.py`: ordering, max length, and thread-safe access patterns.
- `scanner.py`: start/stop lifecycle, snapshot stability, force-update signaling.
- `layout.py`: deterministic geometry for representative terminal sizes.
- `actions.py`: handler contract and cmdlog writes.
- render modules: non-throwing panel render smoke tests with fake screen objects.

## Phased implementation order

1. Land plan + importable package skeleton.
2. Implement concrete scanner-to-POCS data adapters.
3. Build shared layout computation and resize handling.
4. Implement theme initialization and text helpers.
5. Implement DASHBOARD panels.
6. Implement HARDWARE and SCHEDULER panels.
7. Implement SAFETY and HELP panels.
8. Implement action handlers with safe POCS integration.
9. Add richer tests and operator polish (filter UX, cmdlog formatting, performance tuning).

## Non-goals (initial version)

- Complete real-time observatory control feature parity.
- Full panel rendering fidelity.
- Full-text filtering implementation.
- Remote multi-observatory aggregation.
- Performance micro-optimizations beyond a stable 20 FPS skeleton.
