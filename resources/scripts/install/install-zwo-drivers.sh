#!/usr/bin/env bash

CAMERA_DIR="../../cameras/zwo/"
FILTERWHEEL_DIR="../../filterwheel/zwo/"

# Link the ZWO drivers
set -e
if [ ! -d "$CAMERA_DIR" ]; then
  echo "Camera directory $CAMERA_DIR does not exist."
  exit 1
fi

sudo ln -sf "$CAMERA_DIR/armv8/libASICamera2.so" /usr/local/lib/
sudo install "$CAMERA_DIR/asi.rules"  /etc/udev/rules.d

if [ ! -d "$FILTERWHEEL_DIR" ]; then
  echo "Filterwheel directory $FILTERWHEEL_DIR does not exist."
  exit 1
fi

sudo ln -sf "$FILTERWHEEL_DIR/armv8/libEFWFilter.so" /usr/local/lib/
sudo install "$FILTERWHEEL_DIR/efw.rules"  /etc/udev/rules.d

echo "ZWO drivers installed successfully."
echo "Disconnect and reconnect your camera, then running the following command to check if the drivers are loaded:"
echo ""
echo "cat /sys/module/usbcore/parameters/usbfs_memory_mb"
echo ""
echo "You should see the value '200' if the camera is recognized."
