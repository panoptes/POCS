#!/usr/bin/env bash

# Default PANDIR if not set
PANDIR="${PANDIR:-/home/panoptes/POCS}"

# Check for architecture, default to armv8
ARCH=$(uname -m)
if [ "$ARCH" == "x86_64" ]; then
  LIB_SUBDIR="x64"
else
  LIB_SUBDIR="armv8"
fi

CAMERA_DIR="$PANDIR/resources/cameras/zwo"
FILTERWHEEL_DIR="$PANDIR/resources/filterwheel/zwo"

# Link the ZWO drivers
set -e
if [ ! -d "$CAMERA_DIR" ]; then
  echo "Camera directory $CAMERA_DIR does not exist."
  exit 1
fi

# Find the shared object file (to handle versioned names)
LIB_CAMERA=$(ls "$CAMERA_DIR/$LIB_SUBDIR"/libASICamera2.so* | head -n 1)
if [ -f "$LIB_CAMERA" ]; then
  sudo ln -sf "$LIB_CAMERA" /usr/local/lib/libASICamera2.so
else
  echo "Warning: libASICamera2.so not found in $CAMERA_DIR/$LIB_SUBDIR"
fi
sudo install "$CAMERA_DIR/asi.rules" /etc/udev/rules.d

if [ ! -d "$FILTERWHEEL_DIR" ]; then
  echo "Filterwheel directory $FILTERWHEEL_DIR does not exist."
  exit 1
fi

# Find the shared object file (to handle versioned names)
LIB_FILTER=$(ls "$FILTERWHEEL_DIR/$LIB_SUBDIR"/libEFWFilter.so* | head -n 1)
if [ -f "$LIB_FILTER" ]; then
  sudo ln -sf "$LIB_FILTER" /usr/local/lib/libEFWFilter.so
else
  echo "Warning: libEFWFilter.so not found in $FILTERWHEEL_DIR/$LIB_SUBDIR"
fi
sudo install "$FILTERWHEEL_DIR/efw.rules" /etc/udev/rules.d

# Update the library cache
sudo ldconfig

echo "ZWO drivers installed successfully."
echo "Disconnect and reconnect your camera, then running the following command to check if the drivers are loaded:"
echo ""
echo "cat /sys/module/usbcore/parameters/usbfs_memory_mb"
echo ""
echo "You should see the value '200' if the camera is recognized."
