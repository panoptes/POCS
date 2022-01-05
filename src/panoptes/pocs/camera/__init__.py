from collections import OrderedDict
import re
import shutil
import subprocess
import random
from contextlib import suppress

import requests

from panoptes.pocs.camera.camera import AbstractCamera  # noqa

from panoptes.pocs.utils.logger import get_logger
from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.library import load_module

logger = get_logger()


def list_connected_cameras(remote_url=None):
    """Detect connected cameras.

    Uses gphoto2 to try and detect which cameras are connected. Cameras should
    be known and placed in config but this is a useful utility.

    Returns:
        list: A list of the ports with detected cameras.
    """

    if remote_url is not None:
        response = requests.post(remote_url, json=dict(arguments='--auto-detect'))
        if response.ok:
            result = response.json()['output']
    else:
        gphoto2 = shutil.which('gphoto2')
        if not gphoto2:  # pragma: no cover
            raise error.NotFound('gphoto2 is missing, please install or use the remote_url option.')
        command = [gphoto2, '--auto-detect']
        result = subprocess.check_output(command).decode('utf-8')
    lines = result.split('\n')

    ports = []

    for line in lines:
        camera_match = re.match(r'([\w\d\s_\.]{30})\s(usb:\d{3},\d{3})', line)
        if camera_match:
            # camera_name = camera_match.group(1).strip()
            port = camera_match.group(2).strip()
            ports.append(port)

    return ports


def create_cameras_from_config(config=None,
                               cameras=None,
                               auto_primary=True,
                               recreate_existing=False,
                               *args, **kwargs):
    """Create camera object(s) based on the config.

    Creates a camera for each camera item listed in the config. Ensures the
    appropriate camera module is loaded.

    Args:
        config (dict or None): A config object for a camera or None to lookup in
            config-server.
        cameras (list of panoptes.pocs.camera.Camera or None): A list of camera
            objects or None.
        auto_primary (bool): If True, when no camera is marked as the primary camera,
            the first camera in the list will be used as primary. Default True.
        recreate_existing (bool): If True, a camera object will be recreated if an
            existing camera with the same `uid` is already assigned. Should currently
            only affect cameras that use the `sdk` (i.g. not DSLRs). Default False
            raises an exception if camera is already assigned.
        *args (list): Passed to `get_config`.
        **kwargs (dict): Can pass a `cameras` object that overrides the info in
            the configuration file. Can also pass `auto_detect`(bool) to try and
            automatically discover the ports. Any other items as passed to `get_config`.

    Returns:
        OrderedDict: An ordered dictionary of created camera objects, with the
            camera name as key and camera instance as value. Returns an empty
            OrderedDict if there is no camera configuration items.

    Raises:
        error.CameraNotFound: Raised if camera cannot be found at specified port or if
            auto_detect=True and no cameras are found.
        error.PanError: Description
    """
    camera_config = config or get_config('cameras', *args, **kwargs)

    if not camera_config:
        # cameras section either missing or empty
        logger.info('No camera information in config.')
        return None

    logger.debug(f"camera_config={camera_config!r}")
    camera_defaults = camera_config.get('defaults', dict())

    cameras = cameras or OrderedDict()
    ports = list()

    auto_detect = camera_defaults.get('auto_detect', False)

    # Lookup the connected ports
    if auto_detect:
        logger.debug("Auto-detecting ports for cameras")
        try:
            ports = list_connected_cameras(remote_url=camera_defaults.get('remote_url', None))
        except error.PanError as e:
            logger.warning(e)

        if len(ports) == 0:
            raise error.CameraNotFound(
                msg="No cameras detected. For testing, use camera simulator.")
        else:
            logger.debug(f"Detected ports={ports!r}")

    primary_camera = None

    device_info = camera_config['devices']
    for cam_num, cfg in enumerate(device_info):
        # Get a copy of the camera defaults and update with device config.
        device_config = camera_defaults.copy()
        device_config.update(cfg)

        cam_name = device_config.setdefault('name', f'Cam{cam_num:02d}')

        # Check for proper connection method.
        model = device_config['model']

        # Assign an auto-detected port. If none are left, skip
        if auto_detect:
            try:
                device_config['port'] = ports.pop()
            except IndexError:
                logger.warning(f"No ports left for {cam_name}, skipping.")
                continue
        elif model == 'simulator':
            device_config['port'] = f'usb:999,{random.randint(0, 1000):03d}'

        logger.debug(f'Creating camera: {model}')

        try:
            module = load_module(model)
            logger.debug(f'Camera module: module={module!r}')

            if recreate_existing:
                with suppress(AttributeError):
                    module._assigned_cameras = set()

            # We either got a class or a module.
            if callable(module):
                camera = module(**device_config)
            else:
                if hasattr(module, 'Camera'):
                    camera = module.Camera(**device_config)
                else:
                    raise error.NotFound(f'module={module!r} does not have a Camera object')
        except error.NotFound:
            logger.error(f'Cannot find camera module with config: {device_config}')
        except Exception as e:
            logger.error(f'Cannot create camera type: {model} {e!r}')
        else:
            # Check if the config specified a primary camera and if it matches.
            if camera.uid == camera_config.get('primary'):
                camera.is_primary = True
                primary_camera = camera

            logger.debug(f"Camera created: camera={camera!r}")

            cameras[cam_name] = camera

    if len(cameras) == 0:
        raise error.CameraNotFound(msg="No cameras available")

    # If no camera was specified as primary use the first
    if primary_camera is None and auto_primary:
        logger.info(f'No primary camera given, assigning the first camera ({auto_primary!r})')
        primary_camera = list(cameras.values())[0]  # First camera
        primary_camera.is_primary = True

    logger.info(f"Primary camera: {primary_camera}")
    logger.success(f"{len(cameras)} cameras created")

    return cameras
