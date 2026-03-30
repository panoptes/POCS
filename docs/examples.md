# POCS Examples for Beginners

This page contains examples to help you learn POCS, from simple CLI commands to interactive exploration using Jupyter Notebooks.

## Getting Started: The Command Line

**Most users should start with the `pocs` command line tool** - it's simpler and safer than writing Python code.

### Quick Start Hardware Check

```bash
# 1. Configure your unit (REQUIRED FIRST STEP)
pocs config setup

# 2. Test your hardware
pocs mount search-home
pocs camera take-pics --num-images 1

# 3. Run automated observing
pocs mount park
```

### Full CLI Documentation

For complete CLI documentation, see the **[CLI Guide](cli-guide.md)**.

The CLI guide includes:
- All commands (config, run, mount, camera, etc.)
- Detailed examples and options
- Common workflows
- Troubleshooting tips
- Advanced usage

## Interactive POCS with Jupyter (Advanced)

Once you're comfortable with the CLI, explore POCS interactively using a Jupyter Notebook. This is the best way to learn the Python API and experiment with your observatory.

### 1. Set Up Environment

First, we need to set up the environment variables that POCS expects. If you're running this in a simulation mode, we'll point it to a temporary directory.

```python
import os
from pathlib import Path

# Set up a directory for POCS data
pandir = Path.home() / "pocs_notebook"
pandir.mkdir(exist_ok=True)
os.environ["PANDIR"] = str(pandir)

print(f"📁 POCS data directory: {pandir}")
```

### 2. Start Configuration Service

POCS requires a configuration service to be running. In a notebook, you can start it like this:

```python
from panoptes.utils.config.server import config_server

# Use the default config file from the repository
conf_file = Path.cwd() / "conf_files" / "pocs.yaml"
server = config_server(str(conf_file))

print(f"✅ Config service is running using: {conf_file}")
```

### 3. Initialize POCS

Now we can create a `POCS` instance. We'll use `simulators='all'` to ensure we can run everything without real hardware.

```python
from panoptes.pocs.core import POCS

# Create POCS with everything simulated
pocs = POCS.from_config(simulators='all')

# Initialize the system
pocs.initialize()

print(f"🔭 Observatory {pocs.name} is ready!")
print(f"Current State: {pocs.state}")
```

### 4. Interact with Hardware

You can now interact with the various components of the observatory directly.

#### Telescope Mount

```python
mount = pocs.observatory.mount

# Unpark the mount so it can move
mount.unpark()

# Slew to a predefined home position
mount.slew_to_home()

print(f"Mount status: {mount.status}")
```

#### Cameras

```python
from panoptes.utils.time import current_time

# Take a test exposure on all cameras
now = current_time(flatten=True)

for cam_name, cam in pocs.observatory.cameras.items():
    filename = pandir / f"{cam_name}-{now}.cr2"
    print(f"Taking 2s exposure on {cam_name}...")
    cam.take_exposure(seconds=2, filename=str(filename), blocking=True)
    print(f"Saved to {filename}")
```

### 5. Scheduling Observations

You can even ask the scheduler to find a target for you based on the current time and location.

```python
# Get the next best observation from the scheduler
observation = pocs.observatory.get_observation()

if observation:
    print(f"📅 Best target found: {observation.field.name}")
    print(f"Priority: {observation.priority}")
    
    # Slew the mount to the target
    pocs.observatory.mount.slew_to_target()
else:
    print("🌙 No valid targets found for the current conditions.")
```

### 6. Clean Up

When you're done, it's good practice to park the mount.

```python
pocs.observatory.mount.park()
print("💤 Mount parked. Simulation complete!")
```

---

**Note**: For more advanced notebook examples, check the `notebooks/` directory in the POCS repository, such as `TestPOCS.ipynb` and `SchedulerPlayground.ipynb`.
