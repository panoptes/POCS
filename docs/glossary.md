# POCS Glossary for Beginners

Quick reference for terms you'll encounter in POCS documentation and code.

## Command Line Interface (CLI)

**pocs command**
: The main command line tool for POCS. Run `pocs --help` to see all available commands.

**pocs config setup**
: Interactive wizard to configure your PANOPTES unit. This should be the **first command** you run after installation.

**pocs run auto**
: Starts POCS in fully automated mode for all-night observing. This is the main command for regular operations.

**pocs mount**
: Group of commands for controlling the telescope mount (slew, park, home, etc.).

**pocs camera**
: Group of commands for camera operations (take pictures, setup, etc.).

**Simulator mode**
: Running POCS with simulated hardware instead of real equipment. Enabled via configuration or CLI flags like `--simulator mount`.

## General Terms

**PANOPTES**
: The project name. Stands for "Panoptic Astronomical Networked OPtical observatory for Transiting Exoplanets Survey". Basically: a network of robotic telescopes searching for planets.

**POCS**
: PANOPTES Observatory Control System. The software that controls a PANOPTES telescope unit.

**Observatory**
: In POCS, this means the software object that represents your complete telescope system (mount, cameras, dome, etc.), not the physical building.

**Unit**
: A complete PANOPTES telescope system. Usually identified like "PAN001", "PAN012", etc.

## Hardware Terms

**Mount**
: The motorized base that points the telescope. It has two axes:
- **RA (Right Ascension)**: East-West rotation
- **Dec (Declination)**: North-South tilt

**DSLR**
: Digital Single-Lens Reflex camera. PANOPTES often uses consumer cameras like Canon or Nikon.

**Focuser**
: A motor that adjusts the camera focus by moving the lens or sensor.

**Dome**
: A protective enclosure that opens for observing and closes for weather protection.

**Filter Wheel**
: A rotating wheel with different color filters for specialized observations.

## Software Terms

**State Machine**
: A design pattern where software is always in one specific "state" and transitions between states following rules. Example states: sleeping, ready, observing.

**Simulator**
: Fake hardware that lets you test POCS without physical equipment. Great for learning!

**Config Server**
: A background service that provides configuration settings to POCS.

**PANDIR**
: Environment variable pointing to where POCS stores data. Usually `/var/panoptes` or `~/panoptes`.

## Astronomy Terms

**RA/Dec (Right Ascension / Declination)**
: Celestial coordinates. Like latitude/longitude but for the sky.
- RA: Measured in hours (0h to 24h)
- Dec: Measured in degrees (-90° to +90°)

**Alt/Az (Altitude / Azimuth)**
: Local coordinates relative to your horizon.
- Altitude: Height above horizon (0° to 90°)
- Azimuth: Compass direction (0° to 360°)

**Exoplanet**
: A planet orbiting a star other than our Sun.

**Transit**
: When a planet passes in front of its star, causing a tiny dip in brightness. This is what PANOPTES looks for!

**Exposure**
: A single photograph taken by the camera. Usually 30-60 seconds for PANOPTES.

**Field of View (FOV)**
: How much sky the camera can see. Like the difference between a wide-angle and zoom lens.

## Observing Terms

**Target**
: A star or region of sky that POCS is observing or planning to observe.

**Observation**
: The complete process of observing one target: slewing, tracking, taking exposures, analyzing images.

**Sequence**
: A series of exposures of the same target.

**Pointing Model**
: Corrections to account for imperfections in mount alignment and mechanics.

**Flat Field**
: Calibration images used to correct for dust and vignetting in the optical system.

**Dark Frame**
: Calibration images with the shutter closed, used to remove sensor noise.

## State Names

**sleeping**
: Daytime state. POCS is waiting for darkness.

**ready**
: Night has fallen and POCS is ready to start observing.

**scheduling**
: Choosing which target to observe next.

**slewing**
: Moving the telescope to point at a new target.

**tracking**
: Verifying the mount is still tracking the target. The mount tracks continuously during observation, but this state checks it hasn't stopped (e.g., due to meridian or horizon limits).

**observing**
: Taking photographs while the mount tracks the target.

**analyzing**
: Checking image quality.

**parking**
: Moving the telescope to a safe position at the end of the night.

**parked**
: Telescope is in the safe position.

**housekeeping**
: Performing maintenance tasks like data cleanup.

## Configuration Terms

**YAML**
: The file format used for configuration. It's like JSON but more human-readable.

**pan_id**
: Your unit's identifier (e.g., "PAN001").

**Constraint**
: A rule limiting what can be observed. Examples: minimum altitude, maximum airmass, moon avoidance.

**Scheduler**
: The component that decides what to observe and when, considering constraints.

## File and Directory Terms

**$PANDIR/images**
: Where POCS stores captured images.

**$PANDIR/logs**
: Where POCS writes log files for debugging.

**conf_files/**
: Directory containing configuration YAML files.

**state files**
: YAML files defining what happens in each state of the state machine.

## Code Terms You'll See

**from_config()**
: A class method that creates an object using settings from the config server.

**Property**
: In Python, a method that looks like a variable. Example: `pocs.state` (looks like a variable but is actually calling a method).

**Callback**
: A function that gets called when something happens. Example: "Call this function when an image is ready."

**Thread**
: A separate flow of execution. Allows POCS to do multiple things simultaneously (e.g., track and download images).

**Process**
: Like a thread but more isolated. Used for camera control.

## Safety Terms

**is_safe()**
: A method that checks if conditions are safe for observing (weather, sun position, etc.).

**Safety Check**
: One of several conditions evaluated by `is_safe()`. Examples: not daytime, weather OK, mount connected.

**Ignore List**
: Safety checks that can be skipped (use carefully!).

**can_observe**
: Overall flag indicating if the observatory is capable of observing.

## Logging Terms

**Logger**
: The system that writes messages about what POCS is doing.

**Log Level**
: How important a message is:
- **DEBUG**: Detailed info for developers
- **INFO**: General informational messages
- **WARNING**: Something unusual but not broken
- **ERROR**: Something failed
- **CRITICAL**: Severe problem

## Common Abbreviations

**GHA**: Greenwich Hour Angle
**LST**: Local Sidereal Time
**UT/UTC**: Universal Time / Coordinated Universal Time
**JD**: Julian Date
**MJD**: Modified Julian Date
**FITS**: Flexible Image Transport System (astronomy image format)
**WCS**: World Coordinate System (maps pixels to sky coordinates)
**SDK**: Software Development Kit (vendor-provided software for hardware)

## Pro Tips

When reading code or documentation:
- If you see `self.logger.info(...)`, that's just writing a log message
- If you see `@property`, it's a method that looks like a variable
- If you see `simulators=['all']`, it means "use fake hardware"
- If you see `assert`, it's a safety check that stops if something is wrong

## Still Confused?

That's OK! You don't need to know all these terms to start using POCS. Learn them gradually as you encounter them.

**Quick help:**
- Ask on the forum: https://forum.projectpanoptes.org
- Check the docs: https://pocs.readthedocs.io
- Search the code: `grep -r "term_you_dont_know" src/`

Remember: Every expert was once a beginner who kept asking questions! 🌟
