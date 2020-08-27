"""Information about hardware supported by Panoptes."""
import random
import re
import shutil
import subprocess
from collections import OrderedDict

import panoptes.pocs
from astropy import units as u
from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.library import load_module

import panoptes.pocs.camera.dslr.base
from panoptes.pocs.camera.base import AbstractCamera  # noqa

from panoptes.pocs.utils.logger import get_logger

logger = get_logger()

ALL_NAMES = sorted([
    'camera',
    'dome',
    'mount',
    'night',
    'power',
    'sensors',
    'theskyx',
    'weather',
])


def get_all_names(all_names=ALL_NAMES, without=None):
    """Returns the names of all the categories of hardware that POCS supports.

    Note that this doesn't extend to the Arduinos for the telemetry and camera boards, for
    which no simulation is supported at this time.

    >>> from panoptes.pocs.hardware import get_all_names
    >>> get_all_names()
    ['camera', 'dome', 'mount', 'night', 'power', 'sensors', 'theskyx', 'weather']
    >>> get_all_names(without='mount')  # Single item
    ['camera', 'dome', 'night', 'power', 'sensors', 'theskyx', 'weather']
    >>> get_all_names(without=['mount', 'power'])  # List
    ['camera', 'dome', 'night', 'sensors', 'theskyx', 'weather']

    >>> # You can alter available hardware if needed.
    >>> get_all_names(['foo', 'bar', 'power'], without=['power'])
    ['bar', 'foo']

    Args:
        all_names (list): The list of hardware.
        without (iterable): Return all items expect those in the list.

    Returns:
        list: The sorted list of available hardware except those listed in `without`.
    """
    # Make sure that 'all' gets expanded.
    without = get_simulator_names(simulator=without)

    return sorted([v for v in all_names if v not in without])


def get_simulator_names(simulator=None, kwargs=None):
    """Returns the names of the simulators to be used in lieu of hardware drivers.

    Note that returning a list containing 'X' doesn't mean that the config calls for a driver
    of type 'X'; that is up to the code working with the config to create drivers for real or
    simulated hardware.

    This function is intended to be called from `PanBase` or similar, which receives kwargs that
    may include simulator, config or both. For example::

        get_simulator_names(config=self.config, kwargs=kwargs)

        # Or:

        get_simulator_names(simulator=simulator, config=self.config)

    The reason this function doesn't just take **kwargs as its sole arg is that we need to allow
    for the case where the caller is passing in simulator (or config) twice, once on its own,
    and once in the kwargs (which won't be examined). Python doesn't permit a keyword argument
    to be passed in twice.

    >>> from panoptes.pocs.hardware import get_simulator_names
    >>> get_simulator_names()
    []
    >>> get_simulator_names('all')
    ['camera', 'dome', 'mount', 'night', 'power', 'sensors', 'theskyx', 'weather']


    Args:
        simulator (list): An explicit list of names of hardware to be simulated
            (i.e. hardware drivers to be replaced with simulators).
        kwargs: The kwargs passed in to the caller, which is inspected for an arg
            called 'simulator'.

    Returns:
        List of names of the hardware to be simulated.
    """
    empty = dict()

    def extract_simulator(d):
        return (d or empty).get('simulator')

    for v in [simulator, extract_simulator(kwargs), extract_simulator(get_config())]:
        if not v:
            continue
        if isinstance(v, str):
            v = [v]
        if 'all' in v:
            return ALL_NAMES
        else:
            return sorted(v)
    return []


def list_connected_cameras():
    """Detect connected cameras.

    Uses gphoto2 to try and detect which cameras are connected. Cameras should
    be known and placed in config but this is a useful utility.

    Returns:
        list: A list of the ports with detected cameras.
    """

    gphoto2 = shutil.which('gphoto2')
    if not gphoto2:  # pragma: no cover
        raise error.NotFound('The gphoto2 command is missing, please install.')
    command = [gphoto2, '--auto-detect']
    result = subprocess.check_output(command)
    lines = result.decode('utf-8').split('\n')

    ports = []

    for line in lines:
        camera_match = re.match(r'([\w\d\s_\.]{30})\s(usb:\d{3},\d{3})', line)
        if camera_match:
            # camera_name = camera_match.group(1).strip()
            port = camera_match.group(2).strip()
            ports.append(port)

    return ports


def create_cameras_from_config(*args, **kwargs):
    """Create camera object(s) based on the config.

    Creates a camera for each camera item listed in the config. Ensures the
    appropriate camera module is loaded.

    Args:
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

    config = get_config(*args, **kwargs)

    # Helper method to first check kwargs then config
    def kwargs_or_config(item, default=None):
        return kwargs.get(item, config.get(item, default))

    cameras = OrderedDict()
    camera_info = kwargs_or_config('cameras')
    if not camera_info:
        # cameras section either missing or empty
        logger.info('No camera information in config.')
        return cameras

    logger.debug(f"Camera config: {camera_info}")

    auto_detect = camera_info.get('auto_detect', False)

    ports = list()

    # Lookup the connected ports
    if auto_detect:
        logger.debug("Auto-detecting ports for cameras")
        try:
            ports = list_connected_cameras()
        except error.PanError as e:
            logger.warning(e)

        if len(ports) == 0:
            raise error.CameraNotFound(
                msg="No cameras detected. For testing, use camera simulator.")
        else:
            logger.debug(f"Detected Ports: {ports}")

    primary_camera = None

    # Different models require different connections methods.
    model_requires = {
        'canon_gphoto2': 'port',
        'sbig': 'serial_number',
        'zwo': 'serial_number',
        'fli': 'serial_number',
    }

    device_info = camera_info['devices']
    for cam_num, device_config in enumerate(device_info):
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
        else:
            try:
                # This is either `port` or `serial_number`.
                connect_method = model_requires[model]
                connect_value = device_config[connect_method]
                device_config[connect_method] = connect_value
            except KeyError as e:
                logger.warning(f"Camera error: connect_method missing for {model}: {e!r}")

        logger.debug(f'Creating camera: {model}')

        try:
            module = load_module(f'panoptes.pocs.camera.{model}')
            logger.debug(f'Camera module: {module}')
            # Create the camera object
            cam = panoptes.pocs.camera.dslr.base.Camera(**device_config)
        except error.NotFound:
            logger.error(f"Cannot find camera module with config: {device_config}")
        except Exception as e:
            logger.error(f"Cannot create camera type: {device_config['model']} {e}")
        else:
            is_primary = ''
            if camera_info.get('primary', '') == cam.uid:
                cam.is_primary = True
                primary_camera = cam
                is_primary = ' [Primary]'

            logger.debug(f"Camera created: {cam.name} {cam.uid}{is_primary}")

            cameras[cam_name] = cam

    if len(cameras) == 0:
        raise error.CameraNotFound(msg="No cameras available")

    # If no camera was specified as primary use the first
    if primary_camera is None:
        primary_camera = list(cameras.values())[0]  # First camera
        primary_camera.is_primary = True

    logger.debug(f"Primary camera: {primary_camera}")
    logger.debug(f"{len(cameras)} cameras created")

    return cameras


def create_camera_simulator(num_cameras=2):
    """Create simulator camera object(s).

    Args:
        num_cameras (int): The number of simulated cameras to create, default 2.

    Returns:
        OrderedDict: An ordered dictionary of created camera objects, with the
            camera name as key and camera instance as value. Returns an empty
            OrderedDict if there is no camera configuration items.

    Raises:
        error.CameraNotFound: Raised if camera cannot be found at specified port or if
            auto_detect=True and no cameras are found.
    """
    if num_cameras == 0:
        raise error.CameraNotFound(msg="No cameras available")

    cameras = OrderedDict()

    # Set up a simulated camera with fully configured simulated focuser.
    device_config = {
        'model': 'simulator',
        'port': '/dev/camera/simulator',
        'focuser': {'model': 'simulator',
                    'focus_port': '/dev/ttyFAKE',
                    'initial_position': 20000,
                    'autofocus_range': (40, 80),
                    'autofocus_step': (10, 20),
                    'autofocus_seconds': 0.1,
                    'autofocus_size': 500},
        'filterwheel': {'model': 'simulator',
                        'filter_names': ['one', 'deux', 'drei', 'quattro'],
                        'move_time': 0.1 * u.second,
                        'timeout': 0.5 * u.second},
        'readout_time': 0.5,
    }
    logger.debug(f"SimulatorCamera config: {device_config=}")

    primary_camera = None
    for cam_num in range(num_cameras):
        cam_name = f'SimCam{cam_num:02d}'

        logger.debug(f'Using camera simulator {cam_name}')

        camera_model = device_config['model']
        logger.debug(f'Creating camera: {camera_model}')

        module = load_module(f'panoptes.pocs.camera.{camera_model}')
        logger.debug(f'Camera module: {module}')

        # Create the camera object
        cam = panoptes.pocs.camera.dslr.base.Camera(name=cam_name, **device_config)

        is_primary = ''
        if cam_num == 0:
            cam.is_primary = True
            primary_camera = cam
            is_primary = ' [Primary]'

        logger.debug(f"Camera created: {cam.name} {cam.uid}{is_primary}")

        cameras[cam_name] = cam

    logger.debug(f"Primary camera: {primary_camera}")
    logger.debug(f"{len(cameras)} cameras created")

    return cameras
