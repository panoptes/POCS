# POCS Command Line Interface (CLI) Guide

Complete reference for using the `pocs` command line tool.

## Quick Start

If you're new to POCS, start with these essential commands:

```bash
# 1. First-time setup (interactive wizard)
pocs config setup

# 2. Test your mount
pocs mount search-home
pocs mount park
pocs mount slew-home
pocs mount slew-to-target --target Polaris
pocs mount park

# 3. Test your camera
pocs camera take-pics --num-images 1

# 4. Run automated observing
pocs run auto
```

For detailed workflows, see [Common Workflows](#common-workflows) below.

---

## Configuration Commands

### `pocs config setup`

**Interactive configuration wizard** - The first command you should run after installation.

```bash
pocs config setup
```

This will ask a series of questions to set up your observatory configuration, including (pre-filled defaults in parentheses, press Enter):

```bash
Setting up configuration for your PANOPTES unit.
This will overwrite any existing configuration. Proceed? [y/n] (n): y
Enter the base directory for POCS (/home/panoptes/POCS): 
Enter the user-friendly name for this unit (Generic PANOPTES Unit): SuperUnit
Enter the PANOPTES ID for this unit. If you do not have one yet just use the default: (PAN000): 
Enter the latitude for this unit, e.g. "19.5 deg": (19.54 deg): 
Enter the longitude for this unit, e.g. "-154.12 deg": (-155.58 deg): 
Enter the elevation for this unit. Use " ft" or " m" for units, e.g. "3400 m" or "12000 ft": (3400.0 m): 
Enter the timezone for this unit (UTC): HST
Enter the GMT offset for this unit in minutes, e.g. 60 for 1 hour ahead, -120 for 2 hours behind: (-600): 
```

**For beginners:** This is the easiest way to get started!

### `pocs config get`

View configuration settings.

```bash
# View all settings
pocs config get

# View specific setting
pocs config get location.latitude
pocs config get name
```

### `pocs config set`

Modify configuration settings.

```bash
pocs config set name "My Observatory"
pocs config set location.latitude 19.54
```

### `pocs config status`

Check if the configuration server is running.

```bash
pocs config status
```

---

## Observing Commands

### `pocs run auto`

**Main command for automated observing** - Runs the full observation sequence.

```bash
# Run with real hardware
pocs run auto

# Run in simulator mode (for testing without hardware)
pocs run auto --simulator all
```

What it does:
1. Initializes observatory
2. Checks safety conditions
3. Schedules targets
4. Slews to targets
5. Takes observations
6. Repeats until sunrise or stopped

**For beginners:** Start with simulator mode to learn how POCS works!

### `pocs run alignment`

Run polar alignment sequence.

```bash
pocs run alignment
```

Helps align your mount to the celestial pole for better tracking.

### `pocs run take-flats`

Take flat field calibration images.

```bash
# Take evening flats (default)
pocs run take-flats

# Take morning flats
pocs run take-flats --which morning

# Custom altitude/azimuth coordinates
pocs run take-flats --alt 45.0 --az 270.0

# Adjust exposure settings
pocs run take-flats --initial-exptime 5.0 --max-exposures 15
```

Options:
- `--which, -w`: Either 'evening' or 'morning' (default: evening)
- `--alt, -a`: Altitude for flats in degrees (overrides config)
- `--az, -z`: Azimuth for flats in degrees (overrides config)
- `--min-counts`: Minimum ADU count (default: 1000)
- `--max-counts`: Maximum ADU count (default: 12000)
- `--target-adu`: Target ADU as percentage of (min + max) (default: 0.5)
- `--initial-exptime, -e`: Initial exposure time in seconds (default: 3.0)
- `--min-exptime`: Minimum exposure time in seconds (default: 0.0)
- `--max-exptime`: Maximum exposure time in seconds (default: 60.0)
- `--max-exposures, -n`: Maximum number of flats to take (default: 10)
- `--no-tracking/--tracking`: Stop tracking for drift flats (default: --no-tracking)

What it does:
1. Slews mount to specified altitude/azimuth (or uses config for evening/morning)
2. Stops tracking (for drift flats)
3. Takes series of flat field images
4. Automatically adjusts exposure time to achieve target ADU counts

**For beginners:** Flat fields are important calibration images taken of a uniformly illuminated surface (like the twilight sky) to correct for dust, vignetting, and variations in pixel sensitivity.

---

## Mount Commands

Control your telescope mount directly.

### `pocs mount slew-to-target`

Point the mount at a specific target.

```bash
# By common name
pocs mount slew-to-target --target M42
pocs mount slew-to-target --target "Orion Nebula"
pocs mount slew-to-target --target Polaris

# By coordinates (RA/Dec in degrees)
pocs mount slew-to-target --ra 83.82 --dec -5.39
```

### `pocs mount search-home`
Search for the home position using the mount's homing sensors.

```bash
pocs mount search-home
```

### `pocs mount park`

Park the mount in its safe position.

```bash
pocs mount park
```

**Always park your mount** when finished observing or before shutting down!

### `pocs mount slew-home`

Move mount to home position.

```bash
pocs mount slew-home
```

The home position is typically the starting point for calibration and alignment.

### `pocs mount set-park`

Set the current position as the park position.

```bash
pocs mount set-park
```

Use this to define where the mount should go when parked.

---

## Camera Commands

Control your cameras directly.

### `pocs camera take-pics`

Take test images.

```bash
# Take one image with default settings
pocs camera take-pics

# Take multiple images with custom exposure time
pocs camera take-pics --num-images 5 --exptime 10.0

# Specify which camera (if you have multiple)
pocs camera take-pics --camera Cam00
```

**For beginners:** Great for testing your camera setup!

### `pocs camera setup`

Initialize and configure cameras.

```bash
pocs camera setup
```

---

## Other Commands

### Weather Commands

Check weather conditions:

```bash
pocs weather status
```

### Sensor Commands

Check environmental sensors:

```bash
pocs sensor status
```

---

## Common Workflows

### First-Time Setup

```bash
# 1. Run interactive setup
pocs config setup

# 2. Verify configuration
pocs config get

# 3. Find mount home position
pocs mount search-home

# 4. Test camera (in simulator mode)
pocs camera take-pics --num-images 1

# 5. Park mount
pocs mount park
```

### Testing Hardware

Before your first real observation:

```bash
# 1. Start with mount parked
pocs mount park

# 2. Test slewing to a bright star
pocs mount slew-to-target --target Polaris

# 3. Take a test image
pocs camera take-pics --num-images 3 --exptime 2.0

# 4. Park mount when done
pocs mount park
```

### Daily Observing Routine

```bash
# 1. Run automated observing
pocs run auto
```

---

## Troubleshooting

### Configuration Server Not Running

**Error:** "Cannot connect to config server"

**Solution:**
```bash
# Start the config server
pocs config status

# If not running, restart it
pocs config setup
```

### Mount Not Responding

**Problem:** Mount commands don't work

**Solutions:**
1. Check mount is powered on and connected
2. Verify configuration: `pocs config get mount`
3. Try simulator mode first: `pocs run auto --simulator all`
4. Check USB/serial connections

### Camera Not Found

**Problem:** Camera commands fail

**Solutions:**
1. Check camera is powered and connected
2. Verify configuration: `pocs config get cameras`
3. Try simulator mode: use `--simulator camera` flag
4. Check USB connections and drivers

### Permission Errors

**Problem:** "Permission denied" errors

**Solutions:**
1. Make sure you're in the correct user groups (dialout, plugdev)
2. Check file permissions in POCS directories
3. May need to run `pocs config setup` again

---

## Advanced Usage

### Simulator Mode

Test POCS without physical hardware:

```bash
# Simulate all components
pocs run auto --simulator all

# Simulate specific components
pocs run auto --simulator mount
pocs run auto --simulator camera
pocs run auto --simulator weather
```

### Getting Help

Get help for any command:

```bash
pocs --help
pocs config --help
pocs mount --help
pocs camera --help
pocs run alignment --help
```

---

## Next Steps

- **New to POCS?** Read [Conceptual Overview](conceptual-overview.md)
- **Want to understand the architecture?** See [Architecture for Beginners](architecture-for-beginners.md)
- **Ready for Python API?** Check [examples/README.md](../examples/README.md)
- **Need term definitions?** Browse the [Glossary](glossary.md)

---

**Questions?** Check the main [README](../README.md) or visit the PANOPTES forum.
