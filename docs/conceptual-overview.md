# Understanding POCS - A Conceptual Walkthrough

This document explains POCS concepts without requiring installation. Perfect for understanding before you install!

## What Problem Does POCS Solve?

Imagine you want to search for planets around other stars. You need to:

1. Point a telescope at thousands of stars
2. Take pictures all night, every night
3. Look for tiny dips in brightness (planets passing in front of stars)
4. Do this automatically without human intervention

POCS automates all of this!

## The Main Idea

POCS is like an autopilot system for a telescope. Just as airplane autopilot:
- Knows the flight plan (observation schedule)
- Monitors conditions (weather, safety)
- Adjusts course as needed (points telescope)
- Follows procedures (state machine)

**Important**: POCS is the ONLY intelligence - the "autopilot system" itself. All other components are mechanical/electronic systems that POCS controls. When running manually (via scripts or notebooks), a human directly replaces POCS as the autopilot - not as a separate "pilot" or "operator".

## Core Components at a Glance

| Component | Airplane Analogy | What It Does |
|-----------|-----------------|--------------|
| **POCS** | Autopilot system | Makes all decisions, ensures safety |
| **Observatory** | Aircraft frame | Manages all hardware components |
| **Mount** | Control surfaces | Points the telescope |
| **Camera** | Instruments/sensors | Captures images |
| **Scheduler** | Flight computer | Chooses what to observe |
| **State Machine** | Flight sequence | Ensures steps happen in order |

**Key point**: Only POCS has intelligence - it's the autopilot system! Everything else is mechanical hardware that POCS controls. There are no autonomous "pilots" or "crew" - just one smart autopilot (POCS) commanding all the aircraft systems.

## How It Works: A Night in the Life

### 1. Daytime (Sleeping State)
```
POCS checks: "Is it dark yet?"
Answer: No
Action: Keep sleeping, check again in 10 minutes
```

### 2. Sunset (Ready State)
```
POCS checks: "Is it dark? Is weather OK?"
Answer: Yes to both
Action: Move to scheduling
```

### 3. Planning (Scheduling State)
```
Scheduler thinks: "What star should we observe?"
- Checks which stars are visible
- Considers priority and previous observations
- Picks the best target
Action: Tell mount where to point
```

### 4. Moving (Slewing State)
```
Mount receives: "Point to RA 12h 34m, Dec +56° 12'"
Mount motors: Engage!
Mount reports: "Arrived at target"
Action: Mount begins tracking (follows target as Earth rotates)
```

### 5. Tracking Check (Tracking State)
```
POCS: "Is mount still tracking?"
Mount could have stopped due to:
  - Hitting meridian limit
  - Hitting horizon limit
  - Mechanical issues
If still tracking: Proceed to observing
If stopped: Return to scheduling for new target
```

### 6. Picture Time (Observing State)
```
Camera: "Taking 60-second exposure"
Camera: "Image captured!"
POCS: "Save to disk"
Repeat: Take multiple images
Note: Mount continues tracking throughout
```

### 7. Quality Check (Analyzing State)
```
POCS examines: "Are the images good?"
Checks: Focus, image quality, star count
If good: Move to next target
If bad: Try again or skip target
```

### 8. Morning (Parking State)
```
POCS checks: "Getting light?"
Answer: Yes
Action: Point telescope to safe position
Action: Close dome (if present)
State: Return to sleeping
```

## The State Machine Explained Simply

A state machine is like a flowchart where:
- Each box is a "state" (what POCS is doing now)
- Arrows show allowed transitions
- Rules determine when to move to next state

**Why this helps beginners:**
- You always know what POCS is doing (just check `pocs.state`)
- Problems are easier to diagnose (which state is it stuck in?)
- Code is organized by state (easier to understand)

## Configuration: Teaching POCS About Your Setup

POCS needs to know:
- Where you are (latitude/longitude)
- What equipment you have
- How to talk to that equipment

This info lives in YAML files:

```yaml
# Example: Tell POCS about your location
location:
  name: "My Backyard"
  latitude: 34.1234
  longitude: -118.5678
  elevation: 100  # meters

# Example: Tell POCS about your camera
cameras:
  devices:
    - model: Canon EOS
      port: /dev/video0
```

## Simulators: Learning Without Hardware

One of POCS's best features for beginners:

```python
# This creates a completely virtual observatory!
pocs = POCS.from_config(simulators=['all'])
```

What gets simulated:
- Virtual cameras that generate test images
- Virtual mount that "points" anywhere instantly
- Virtual weather station that reports "always clear"
- Virtual dome (if you have that configured)

**Why this is great:**
- Learn POCS before buying equipment
- Test code changes safely
- Develop new features without hardware

## Common Beginner Questions

### "Why is it so complicated?"

Telescopes are complex! POCS handles:
- Astronomy math (coordinate conversions)
- Hardware communication (serial ports, USB)
- Safety (weather, sun position, limits)
- Scheduling (optimization, constraints)
- Image processing (focus, alignment)

But POCS hides most complexity behind simple interfaces.

### "Where do I start?"

1. Read this document (you're doing it!)
2. Run [examples/beginner_simulation.py](../examples/beginner_simulation.py)
3. Explore [notebooks/TestPOCS.ipynb](../notebooks/TestPOCS.ipynb)
4. Read [docs/architecture-for-beginners.md](architecture-for-beginners.md)
5. Look at [src/panoptes/pocs/core.py](../src/panoptes/pocs/core.py)

### "What if I break something?"

In simulator mode: You can't! Break things freely to learn.

With real hardware: POCS has safety checks:
- Won't operate in daytime
- Won't operate in bad weather
- Won't point at sun
- Won't move beyond mechanical limits

### "How do I get help?"

- **Forum**: https://forum.projectpanoptes.org (friendly community!)
- **Documentation**: https://pocs.readthedocs.io
- **Code issues**: https://github.com/panoptes/POCS/issues
- **Live chat**: Join via the forum

## Using POCS: The Command Line Tool

POCS provides a user-friendly command line interface. After installation, you'll use the `pocs` command for everything.

### Quick Start

```bash
# 1. First-time setup (interactive wizard)
pocs config setup

# 2. Test hardware
pocs mount search-home
pocs camera take-pics --num-images 1
pocs mount park
```

### Full CLI Reference

For complete documentation of all CLI commands, see the **[CLI Guide](cli-guide.md)**.

The CLI guide includes:
- All configuration commands (`pocs config ...`)
- Observing commands (`pocs run auto`, etc.)
- Hardware control (`pocs mount ...`, `pocs camera ...`)
- Common workflows and troubleshooting
- Advanced usage tips

### CLI vs Python API

**For most users**: Use the CLI commands above. They're simpler and safer.

**For developers**: Use the Python API (shown in example scripts) when you need:
- Custom observing sequences
- Integration with other software
- Automated testing
- Advanced customization

## Next Steps

After understanding these concepts:

1. **Install POCS** - [Follow installation instructions in README](../README.md#install)
2. **Configure your unit** - Run `pocs config setup`
3. **Test hardware** - Use `pocs mount` and `pocs camera` commands
4. **Run simulations** - Try `pocs run auto` with simulators
5. **Join the community** - Share your learning journey!

## Key Takeaways

- POCS automates robotic telescopes
- It uses a state machine for organized operation
- Everything can be simulated for learning
- Configuration tells POCS about your specific setup
- The community is here to help you learn

Happy learning! 🔭✨
