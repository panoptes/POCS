#!/usr/bin/env python3
"""
Beginner-Friendly POCS Simulation Example
==========================================

This script demonstrates running POCS in full simulation mode using Python.
Perfect for learning the Python API without any hardware!

**IMPORTANT**: Most users should use the command line tool instead:

```bash
# Configure your unit (do this first!)
pocs config setup

# Run automated observing
pocs run auto

# Test mount
pocs mount slew-to-target --target M42

# Take test pictures
pocs camera take-pics
```

This Python script is for users who need programmatic control or are
developing POCS features. If you just want to use POCS, stick with the
CLI commands above!

Author: PANOPTES Team
License: MIT
"""

import os
import sys
from pathlib import Path


def setup_environment():
    """Configure the environment for POCS simulation."""
    # Set up the PANOPTES directory in your home folder
    pandir = Path.home() / 'panoptes_simulation'
    pandir.mkdir(exist_ok=True)
    os.environ['PANDIR'] = str(pandir)
    
    print(f"📁 PANOPTES data directory: {pandir}")
    return pandir


def start_config_service():
    """Start the configuration service needed by POCS."""
    print("\n🔧 Starting configuration service...")
    
    try:
        from panoptes.utils.config.server import config_server
        
        # Use local config file from the repository
        conf_file = Path(__file__).parent.parent / 'conf_files' / 'pocs.yaml'
        
        if not conf_file.exists():
            print(f"❌ Config file not found at: {conf_file}")
            print("   Make sure you're running this script from the POCS repository")
            sys.exit(1)
        
        server = config_server(str(conf_file))
        print("✅ Config service is running")
        print(f"   Using config file: {conf_file}")
        return server
    except Exception as err:
        print(f"❌ Could not start config service: {err}")
        print("   Make sure panoptes-utils is installed")
        sys.exit(1)


def create_simulated_observatory():
    """Create a POCS instance with all hardware simulated."""
    print("\n🔭 Creating simulated observatory...")
    
    try:
        from panoptes.pocs.core import POCS
        
        # Create POCS with everything simulated
        simulated_pocs = POCS.from_config(simulators='all')
        print("✅ Observatory created successfully")
        return simulated_pocs
    except Exception as err:
        print(f"❌ Could not create observatory: {err}")
        sys.exit(1)


def demonstrate_basic_operations(pocs_instance):
    """Show basic POCS operations."""
    print("\n📊 Observatory Information:")
    print(f"   Name: {pocs_instance.name}")
    print(f"   Unit ID: {pocs_instance.unit_id}")
    print(f"   Current State: {pocs_instance.state}")
    
    print("\n🔍 Attempting initialization...")
    init_result = pocs_instance.initialize()
    print(f"   Initialization result: {init_result}")
    
    print("\n🔌 Attached Devices:")
    
    # Display cameras
    observatory = pocs_instance.observatory
    if observatory.has_cameras:
        print(f"   📷 Cameras ({len(observatory.cameras)}):")
        for cam_name, camera in observatory.cameras.items():
            print(f"      • {cam_name}: {camera}")
    else:
        print("   📷 Cameras: None")
    
    # Display mount
    if observatory.mount:
        print(f"   🔭 Mount: {observatory.mount}")
    else:
        print("   🔭 Mount: None")
    
    # Display scheduler
    if observatory.scheduler:
        print(f"   📅 Scheduler: {observatory.scheduler}")
    else:
        print("   📅 Scheduler: None")
    
    # Display dome (if present)
    if observatory.dome:
        print(f"   🏠 Dome: {observatory.dome}")
    else:
        print("   🏠 Dome: None")


def main():
    """Main execution flow for the beginner simulation."""
    print("=" * 60)
    print("  POCS Beginner Simulation")
    print("  Learn POCS without hardware!")
    print("=" * 60)
    
    # Step 1: Environment setup
    data_dir = setup_environment()
    
    # Step 2: Start required services
    # Note: config_service must stay alive for POCS to access configuration
    _config_service = start_config_service()
    
    # Step 3: Create the observatory
    pocs = create_simulated_observatory()
    
    # Step 4: Demonstrate operations
    demonstrate_basic_operations(pocs)
    
    print("\n" + "=" * 60)
    print("  Simulation complete! 🎉")
    print(f"  Data stored in: {data_dir}")
    print("=" * 60)
    
    # Keep the config server running for interactive use
    print("\n💡 Tip: The 'pocs' object is ready for interactive exploration!")
    print("   Try: pocs.state, pocs.observatory, etc.")
    
    return pocs


if __name__ == '__main__':
    observatory_instance = main()
