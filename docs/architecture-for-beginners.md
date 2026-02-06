# POCS Architecture for Beginners

## Overview

POCS is built like a layered cake - each layer handles specific responsibilities.

## The Layers

```
┌────────────────────────┬────────────────────┬──────────────────────────┐
│ Component              │ Analogy            │ Role                     │
├────────────────────────┼────────────────────┼──────────────────────────┤
│ State Machine (POCS)   │ The Brain 🧠       │ You interact here        │
│ Controls workflow      │                    │ Makes decisions          │
│ Uses Scheduler         │                    │                          │
├────────────────────────┼────────────────────┼──────────────────────────┤
│ Scheduler              │ The Planner 📅     │ Decides what to observe  │
│ Picks best targets     │                    │                          │
├────────────────────────┼────────────────────┼──────────────────────────┤
│ Observatory            │ The Coordinator 🎯 │ Coordinates hardware     │
│ Manages equipment      │                    │                          │
├────────────────────────┼────────────────────┼──────────────────────────┤
│ Hardware Drivers       │ The Workers 🔧     │ Talks to devices         │
│ Camera│Mount│Dome│Etc  │                    │                          │
├────────────────────────┼────────────────────┼──────────────────────────┤
│ Physical Devices       │ The Hardware 🔭    │ The actual telescope!    │
│                        │                    │                          │
└────────────────────────┴────────────────────┴──────────────────────────┘
```

## Key Components Explained

### 1. POCS (The Brain 🧠)

**What it does:** Orchestrates the entire observation workflow and makes high-level decisions

**Key file:** `src/panoptes/pocs/core.py`

**Responsibilities:**
- Decides when it's safe to observe
- Coordinates the observation sequence through states
- Asks the Scheduler component for targets (during "scheduling" state)
- Handles errors and safety checks
- Runs as a "state machine" (explained below)

**Think of it as:** The conductor of an orchestra

**Important:** POCS has a "scheduling" STATE where it pauses to ask the Scheduler COMPONENT which target to observe next. POCS controls WHEN to schedule, the Scheduler decides WHAT to observe.

### 2. Scheduler (The Planner 📅)

**What it does:** Decides which astronomical target to observe (when asked by POCS)

**Key file:** `src/panoptes/pocs/scheduler/`

**Responsibilities:**
- Maintains a list of potential targets
- Chooses the best target for current conditions when POCS asks
- Considers constraints (altitude, time, moon phase)

**Think of it as:** A smart calendar that picks the best tasks when consulted

**Important:** The Scheduler doesn't run observations - it just picks targets. POCS asks the Scheduler "what should I observe next?" during the "scheduling" state, then POCS executes that observation.

### 3. Observatory (The Coordinator 🎯)

**What it does:** Manages all your hardware as a single unit

**Key file:** `src/panoptes/pocs/observatory.py`

**Responsibilities:**
- Knows what hardware you have (cameras, mount, etc.)
- Initializes hardware on startup
- Provides access to each component
- Tracks the current observation target

**Think of it as:** A manager who knows all the team members

### 4. Hardware Drivers (The Workers 🔧)

**What they do:** Control individual pieces of equipment

**Key directories:**
- `src/panoptes/pocs/camera/` - Camera control
- `src/panoptes/pocs/mount/` - Telescope mount control
- `src/panoptes/pocs/focuser/` - Focus control
- `src/panoptes/pocs/dome/` - Dome control

**Responsibilities:**
- Send commands to physical devices
- Read status from devices
- Handle device-specific quirks

**Think of them as:** Specialized technicians

## The State Machine Concept

POCS uses a **state machine** - a fancy term for "a system that's always in one specific state and moves between states in a controlled way."

### States in POCS

```
sleeping → ready → scheduling → slewing → tracking → observing → parking
   ↑                                         ↑          ↓              ↓
   │                                         └──────────┘              │
   │                                                                   │
   └───────────────────────────────────────────────────────────────────┘
```

**What each state means:**

- **sleeping:** Daytime, waiting for darkness
- **ready:** Night time, ready to start observing
- **scheduling:** POCS asks the Scheduler component to pick the next target
- **slewing:** Moving the telescope to point at the target
- **tracking:** Checking mount is still tracking (could have stopped due to meridian/horizon limits)
- **observing:** Taking pictures while mount tracks
- **parking:** Safely stowing the telescope

**Note:** Don't confuse the "scheduling" STATE (when POCS pauses to get a target) with the Scheduler COMPONENT (the code that actually picks targets).

### Why use a state machine?

Instead of one giant complicated program, we break observing into small, manageable steps. Each state:
- Has a clear job
- Knows which states can come next
- Includes safety checks

**Analogy:** Like building a house - you can't install the roof before laying the foundation!

## Data Flow Example

Let's trace what happens when you start POCS:

```
1. You create POCS
   ↓
2. POCS creates an Observatory
   ↓
3. Observatory creates hardware drivers
   ↓
4. Drivers connect to physical devices
   ↓
5. POCS enters "sleeping" state
   ↓
6. When dark, POCS → "ready" state
   ↓
7. POCS enters "scheduling" state
   ↓
8. POCS asks Scheduler: "What should I observe?"
   ↓
9. Scheduler returns best target
   ↓
10. Mount slews to target
   ↓
11. Cameras take exposures
   ↓
12. Images saved to disk
```

## Using POCS: Command Line Interface

The `pocs` command is your primary interface to the system. Think of it as POCS's "steering wheel."

### Essential Commands

```bash
# 1. First-time setup (interactive wizard)
pocs config setup

# 2. Test your mount
pocs mount park

# 3. Test your camera
pocs camera take-pics --num-images 1

# 4. Run automated observing
pocs run auto
```

### Full CLI Reference

For complete documentation of all CLI commands, workflows, and troubleshooting, see the **[CLI Guide](cli-guide.md)**.

The CLI guide covers:
- Configuration commands
- Observing and alignment
- Hardware control (mount, camera, dome)
- Common workflows
- Troubleshooting
- Advanced usage

### When to Use CLI vs Python

**Use CLI when:**
- First learning POCS
- Running standard observations
- Testing hardware
- Daily operations

**Use Python API when:**
- Custom observing sequences needed
- Integrating with other software
- Developing new features
- Advanced automation

## Configuration System

POCS needs to know about your specific setup (location, hardware, etc.)

### How configuration works:

```
Config Files (YAML)
       ↓
Config Server (runs in background)
       ↓
POCS asks server for settings
       ↓
POCS configures itself
```

**Key config file:** `conf_files/pocs.yaml`

**What's configured:**
- Your location (latitude, longitude, elevation)
- What hardware you have
- Hardware-specific settings (serial ports, etc.)
- Observation parameters
- Safety thresholds

## File Organization

```
POCS/
├── src/panoptes/pocs/       ← Main source code
│   ├── core.py              ← POCS state machine
│   ├── observatory.py       ← Observatory coordinator
│   ├── camera/              ← Camera drivers
│   ├── mount/               ← Mount drivers
│   └── scheduler/           ← Target scheduling
├── conf_files/              ← Configuration files
├── tests/                   ← Automated tests
├── docs/                    ← Documentation
├── examples/                ← Learning examples (you are here!)
└── notebooks/               ← Jupyter notebooks
```

## Common Patterns You'll See

### 1. Simulators

Almost every hardware component has a "simulator" version:
- Lets you test without real hardware
- Useful for development and learning
- Created with `simulators=['all']`

### 2. Properties

Python `@property` decorators make methods look like attributes:
```python
pocs.state           # Looks like an attribute
pocs.is_safe()       # But is actually a method
```

### 3. Configuration Lookup

Code frequently asks the config server for values:
```python
self.get_config('mount.serial.port')
```

### 4. Logging

Extensive logging helps debug issues:
```python
self.logger.info("Starting observation")
```

## Learning Path

For beginners, we recommend this order:

1. **Configure your unit:** Run `pocs config setup` (interactive, beginner-friendly)
2. **Read conceptual-overview.md:** Understand the POCS concepts
3. **Test hardware manually:** Use CLI commands like `pocs mount park`, `pocs camera take-pics`
4. **Try automated run:** Start with `pocs run auto` in simulator mode
5. **Explore code:** Once CLI is familiar, dive into core.py and observatory.py
6. **Customize:** Modify config, create custom observations

### Command Line First

The `pocs` command line tool is your friend! It's safer and simpler than Python code:

```bash
# Start here - configure your unit
pocs config setup

# Test your mount
pocs mount slew-to-target --target Polaris

# Take test images
pocs camera take-pics --num-images 3 --exptime 5.0

# Run automated observing
pocs run auto
```

### Python API Second

Once comfortable with CLI, explore the Python API for advanced use:

```python
from panoptes.pocs.core import POCS
pocs = POCS.from_config(simulators=['all'])
pocs.initialize()
# ... custom logic ...
```

## Getting Help

- **Forum:** https://forum.projectpanoptes.org
- **Docs:** https://pocs.readthedocs.io
- **Code questions:** GitHub issues
- **Live chat:** Join our community chat

## Summary

**Remember:**
- POCS = Brain that makes decisions
- Observatory = Hardware coordinator
- Drivers = Individual device controllers
- State machine = Organized workflow
- Config server = Settings provider

Start with the examples, read the code, and don't hesitate to ask questions!
