# POCS Terminal UI Dashboard Plan (pocs-tui)

## Goals

| Goal | Why it matters | Deliverable |
|---|---|---|
| Primary control interface | Users should not need to run separate `pocs` CLI commands for day-to-day operations | All observatory workflows accessible from the TUI |
| Menu-driven UX | Interface should be fully discoverable without memorising keybindings | All actions accessed through navigable menus |
| Live situational awareness | Operators need one-glance status across safety, hardware, and observation progress | Live panels updated by background scanner |
| Safe, auditable control | All actions logged so operators can see what was done and when | Centralised actions module + command log |
| Inline config editing | Config should be editable without leaving the TUI | CONFIG view with tree-browse and inline edit |
| Responsive rendering | UI must stay smooth under ongoing scans | 20 FPS render loop + non-blocking renderer |
| Clear architecture boundaries | Keeps future implementation maintainable | Strict model / scanner / render / input / actions / bridge split |
| Testable foundations | Enables iterative delivery without regressions | Importable stdlib-first skeleton + focused tests |

## Lessons from milk-CTRL mapped to POCS

| milk concept | milk files | POCS equivalent |
|---|---|---|
| Strict model/render/input split | `overview_data.h`, `overview_render*.c`, `overview_input.c` | `model.py`, panel render modules, `input.py` |
| Double-buffer model swap | `OV_MODEL` front/back pair + lock | `Scanner` front/back `POCSModel` references guarded by `threading.Lock` |
| Polling scan thread + force wake | `overview_scan.c`, `ov_scan_force_update()` | `Scanner` background loop using `Event.wait(timeout)` + `force_update()` |
| Sparkline ring buffers | `spark_rate[]`, `hz_hist[]` | `progress_hist` in `CameraModel`, shared sparkline helper in `theme.py` |
| Command log ring | `OV_CMDLOG` | `CmdLog` with `deque(maxlen=64)` and severity level |
| Theme separated from render | `overview_theme.h`, `overview_ansi.h` | `theme.py` keeps chars, palette, and color-pair setup |
| Geometry as computed rects | `OV_LAYOUT`, `OV_RECT`, `ov_layout_compute()` | `Rect`, `Layout`, and `layout_compute()` |
| Isolated control side effects | `overview_ctrl.c` | `actions.py` action functions + cmdlog helper |

## Architecture overview

```
┌─────────────────────────────────────────────────────┐
│                    __main__.py                      │
│   20 FPS loop: input → action → snapshot → render  │
└──────┬───────────────────┬───────────────────┬──────┘
       │                   │                   │
  input.py            actions.py           panels/*.py
  (navigation)     (side effects)          (render)
       │                   │
       │             bridge.py  ◄──── command channel to POCS
       │                   │
  scanner.py          model.py
  (background)       (data model)
       │
  TelemetryClient  (read-only live data)
```

**Command channel (`bridge.py`)**

The bridge abstracts how the TUI sends commands to POCS:

- **In-process (v1 default):** `pocs tui` starts POCS in a background thread and the bridge holds a direct reference. Actions call POCS methods directly (e.g. `pocs.park()`).
- **Out-of-process (future):** Bridge sends over a socket/IPC channel to a separately running POCS process.

The bridge interface is the same regardless of transport, so swapping is non-breaking.

**Read path:** Scanner reads live state from `TelemetryClient` on its polling interval.  
**Write path:** Actions call through `bridge.py` → POCS methods; after each action the scanner is force-woken for an immediate update.

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
    run_active: bool = False
    free_space: float = 0.0
    uptime: str = "--"

@dataclass(slots=True)
class ModalModel:
    """Active confirmation dialog, if any."""
    active: bool = False
    prompt: str = ""
    choices: list[str] = field(default_factory=list)   # e.g. ["Confirm", "Cancel"]
    selected: int = 0
    callback: str = ""   # name of action to call on confirm

@dataclass(slots=True)
class ConfigEditorModel:
    """State for the CONFIG view."""
    keys: list[str] = field(default_factory=list)      # flat dotted-key list
    cursor: int = 0
    editing: bool = False
    edit_buffer: str = ""

@dataclass(slots=True)
class POCSModel:
    safety: SafetyModel = field(default_factory=SafetyModel)
    mount: MountModel = field(default_factory=MountModel)
    cameras: list[CameraModel] = field(default_factory=list)
    scheduler: SchedulerModel = field(default_factory=SchedulerModel)
    focuser: FocuserModel = field(default_factory=FocuserModel)
    dome: DomeModel = field(default_factory=DomeModel)
    system: SystemModel = field(default_factory=SystemModel)
    modal: ModalModel = field(default_factory=ModalModel)
    config_editor: ConfigEditorModel = field(default_factory=ConfigEditorModel)
    scan_time_ms: float = 0.0
    scan_count: int = 0
```

## Scanner design (`scanner.py`)

- Owns a background thread that repeatedly reads `TelemetryClient` and updates the model.
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

## Views and tabs

The TUI uses a tab bar across the top. Tabs are navigated with `←` / `→` or `Tab`.

| View | Tab label | Purpose |
|---|---|---|
| `DASHBOARD` | `[Dashboard]` | High-level status — safety, mount, cameras, active observation |
| `HARDWARE` | `[Hardware]` | Detailed mount / camera / focuser / dome status |
| `SCHEDULER` | `[Scheduler]` | Candidate target list; active observation detail |
| `OPERATIONS` | `[Operations]` | Menu-driven control: lifecycle, procedures, manual commands |
| `CONFIG` | `[Config]` | Browse and inline-edit config keys |
| `HELP` | `[Help]` | Navigation conventions and panel descriptions |

## Navigation conventions

All interaction is menu-driven. No action requires memorising a hotkey.

| Key | Effect |
|---|---|
| `↑` / `↓` | Move selection within a menu or list |
| `←` / `→` | Move between tabs; or navigate nested menus |
| `Tab` | Cycle to the next tab |
| `Enter` | Activate selected menu item / confirm edit |
| `Esc` | Go back one level / cancel edit / dismiss modal |
| `q` | Quit (single global shortcut; prompts confirmation modal) |

Within the CONFIG view, `Enter` on a key opens an inline edit field; `Esc` cancels without saving.  
Within a modal dialog, `↑↓` select `[Confirm]` / `[Cancel]` and `Enter` executes.

## Dashboard layout mockup

```text
+------------------------------------------------------------------------------------------------+
| POCS  [Dashboard] [Hardware] [Scheduler] [Operations] [Config] [Help]   state=observing       |
+---------------------------------------------+-----------------------------------------------+
| SAFETY                                      | OBSERVATION                                   |
| power: OK  dark: YES  weather: GOOD         | field: M42                                     |
| root: 88% free  images: 72% free            | exp: 45/120  exptime: 30s                      |
+---------------------------------------------+-----------------------------------------------+
| MOUNT                                       | CAMERAS                                       |
| parked: no  tracking: yes  slewing: no      | Cam00 exposing temp=-10C filter=L              |
| ra=05:35:17 dec=-05:23:28 ha=+00:11:04      | progress ▁▂▃▅▆▇██                              |
| alt=62.1 az=181.7                           | Cam01 idle temp=-10C filter=R                  |
+---------------------------------------------+-----------------------------------------------+
| CMDLOG                                                                                        |
| 02:11:42 INFO  Start nightly run requested                                                    |
| 02:12:01 INFO  POCS initialized and entering scheduling state                                 |
+------------------------------------------------------------------------------------------------+
```

## Operations view mockup

```text
+------------------------------------------------------------------------------------------------+
| POCS  [Dashboard] [Hardware] [Scheduler] [Operations] [Config] [Help]   state=sleeping        |
+------------------------------------------------------------------------------------------------+
| OPERATIONS                                                                                    |
|                                                                                               |
|  ▶ Start nightly run                                                                          |
|    Stop run                                                                                   |
|    Park telescope                                                                             |
|    ── Procedures ──────────────────────────────────                                          |
|    Polar alignment                                                                            |
|    Focus run                                                                                  |
|    Take dark frames                                                                           |
|    ── Hardware ────────────────────────────────────                                          |
|    Initialize POCS                                                                            |
|    Connect mount                                                                              |
|    Connect cameras                                                                            |
|    Disconnect all                                                                             |
|    ── Session ─────────────────────────────────────                                          |
|    Reload config                                                                              |
|    Shutdown POCS                                                                              |
|    Quit TUI                                                                                   |
|                                                                                               |
+------------------------------------------------------------------------------------------------+
| CMDLOG                                                                                        |
| 02:11:42 INFO  Park requested via Operations menu                                             |
+------------------------------------------------------------------------------------------------+
```

## Config view mockup

```text
+------------------------------------------------------------------------------------------------+
| POCS  [Dashboard] [Hardware] [Scheduler] [Operations] [Config] [Help]   state=sleeping        |
+------------------------------------------------------------------------------------------------+
| CONFIG                                                                                        |
|                                                                                               |
|  name                        My PANOPTES Unit                                                 |
|  location.latitude           19.5363 deg                                                      |
|  location.longitude          -155.5763 deg                                                    |
|  location.elevation          3400.0 m                                                         |
|▶ location.horizon            30 deg                                                           |
|  location.timezone           US/Hawaii                                                        |
|  mount.brand                 iOptron                                                          |
|  mount.driver                panoptes.pocs.mount.ioptron                                      |
|  ...                                                                                          |
|                                                                                               |
|  [Enter] edit   [Esc] cancel                                                                  |
+------------------------------------------------------------------------------------------------+
```

## Action layer (`actions.py`)

All side effects go through this module. Every attempt and outcome writes to `CmdLog`.

**Lifecycle**
- `action_initialize(bridge, cmdlog)` — connect all hardware, enter ready state
- `action_start_run(bridge, cmdlog)` — start automated nightly observation loop
- `action_stop_run(bridge, cmdlog)` — interrupt current run gracefully
- `action_shutdown(bridge, cmdlog)` — park, disconnect, and stop POCS
- `action_quit(bridge, cmdlog)` — stop scanner, restore terminal, exit

**Observatory control**
- `action_park(bridge, cmdlog)` — park the mount
- `action_abort_exposure(bridge, cmdlog)` — abort in-progress camera exposure
- `action_snapshot(bridge, cmdlog)` — trigger a single test image

**Procedures**
- `action_polar_align(bridge, cmdlog)` — start polar alignment procedure
- `action_focus_run(bridge, cmdlog)` — start autofocus sequence
- `action_take_darks(bridge, cmdlog)` — start dark frame acquisition

**Hardware**
- `action_connect_mount(bridge, cmdlog)`
- `action_connect_cameras(bridge, cmdlog)`
- `action_disconnect_all(bridge, cmdlog)`

**Config**
- `action_set_config(bridge, cmdlog, key, value)` — write one config key via `set_config`
- `action_reload_config(bridge, cmdlog)` — reload config from disk

**Rules**
- Destructive actions (stop run, shutdown, disconnect) always present a `ModalModel` confirmation first.
- No action blocks the render thread — all POCS calls go through the bridge asynchronously or in a short-lived thread.

## Command log (`cmdlog.py`)

- `LogEntry(ts, level, msg)` dataclass.
- `CmdLog` with thread-safe `deque(maxlen=64)` storage.
- API:
  - `push(level, msg)`
  - `tail(n)`

## Layout dataclasses

- `Rect(x, y, w, h)`
- `Layout` fields:
  - `screen`, `tab_bar`, `main`, `cmdlog`, `modal_overlay`,
  - `active_view`, `focus`, `width`, `height`.
- `layout_compute(lay)` recomputes all rects on resize and view changes.

## Render layer conventions

- Never block in render path.
- Every panel draws only inside its assigned `Rect`.
- Clip/truncate all text to width.
- Use Unicode sparklines for bounded historical series.
- Read colour/style only from `theme.py` constants and initialised pairs.
- Modal overlay renders on top of all panels when `model.modal.active` is `True`.

## Main loop sketch (`__main__.py`)

- Entry through `curses.wrapper(main)`.
- Construct bridge (in-process: start POCS thread; future: connect socket).
- Start scanner.
- Loop at 20 FPS:
  1. read raw key,
  2. dispatch to `input.handle(key, layout, model)` → returns optional action name,
  3. if action: call through `actions.dispatch(name, bridge, cmdlog, model)`,
  4. fetch scanner `snapshot()`,
  5. `layout_compute(lay)`,
  6. render active tab panel + cmdlog + modal overlay if active,
  7. `stdscr.refresh()`.
- On exit: stop scanner, bridge shutdown, restore terminal state.

## Planned file structure

```text
src/panoptes/pocs/tui/
├── __init__.py
├── __main__.py        # curses entry point and main loop
├── model.py           # dataclass model tree (POCSModel + sub-models)
├── scanner.py         # background TelemetryClient polling thread
├── bridge.py          # command channel to POCS (in-process or socket)
├── layout.py          # Rect, Layout, layout_compute()
├── theme.py           # colour pairs, spark chars, sparkline helper
├── cmdlog.py          # CmdLog ring buffer
├── input.py           # navigation key dispatch (no action hotkeys)
├── actions.py         # all side-effect handlers
└── panels/
    ├── __init__.py
    ├── dashboard.py   # DASHBOARD tab render
    ├── hardware.py    # HARDWARE tab render
    ├── scheduler.py   # SCHEDULER tab render
    ├── operations.py  # OPERATIONS menu render
    ├── config.py      # CONFIG tree/editor render
    └── help.py        # HELP tab render
```

## Dependencies

- Standard library (`curses`, `threading`, `dataclasses`, `collections`, etc.).
- Existing POCS dependencies only (`panoptes-utils` for `TelemetryClient`, `get_config`, `set_config`).
- No new third-party TUI framework.

## Testing strategy

- `model.py`: dataclass defaults and ring-buffer behaviour.
- `cmdlog.py`: ordering, max length, and thread-safe access patterns.
- `scanner.py`: start/stop lifecycle, snapshot stability, force-update signalling.
- `layout.py`: deterministic geometry for representative terminal sizes.
- `actions.py`: handler contract, cmdlog writes, and modal creation for destructive actions.
- `bridge.py`: in-process bridge calls correct POCS methods; mock-POCS tests.
- render modules: non-throwing panel render smoke tests with fake screen objects.
- `input.py`: navigation events produce correct action names from menu state.

## Phased implementation order

1. ✅ Land plan + importable package skeleton.
2. Add `bridge.py` (in-process); wire `pocs tui` CLI entry point; verify POCS starts inside the TUI.
3. Implement `_scan()` with live `TelemetryClient` data; DASHBOARD panels display real values.
4. Implement OPERATIONS view with menu navigation; wire lifecycle actions (init, start run, stop run, park) through bridge.
5. Implement `layout_compute()` and terminal resize handling.
6. Implement CONFIG view: browse config tree, inline-edit a value, write back via `set_config`.
7. Implement HARDWARE and SCHEDULER tabs.
8. Implement SAFETY and HELP tabs.
9. Implement modal confirmation dialogs for destructive actions.
10. Implement remaining procedures (polar align, focus run, dark frames).
11. Richer tests and polish (sparkline tuning, error display, cmdlog formatting, performance).

## Non-goals (initial version)

- Mouse support.
- Graphical / Rich / Textual framework port.
- Remote multi-observatory aggregation.
- Full-text filtering of panels.
- Performance micro-optimisations beyond a stable 20 FPS skeleton.
