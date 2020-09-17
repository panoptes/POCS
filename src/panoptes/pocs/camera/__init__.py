import copy
from collections import OrderedDict
import re
import shutil
import subprocess
import random

from astropy import units as u
from panoptes.pocs.camera.camera import AbstractCamera  # noqa
from panoptes.pocs.camera.camera import AbstractGPhotoCamera  # noqa

from panoptes.pocs.utils.logger import get_logger
from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.library import load_module

logger = get_logger()


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


def create_cameras_from_config(config=None, cameras=None, auto_primary=True, *args, **kwargs):
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
    logger.debug(f"{camera_config=}")

    cameras = cameras or OrderedDict()
    ports = list()

    auto_detect = camera_config.get('auto_detect', False)

    # Lookup the connected ports
    if auto_detect:
        logger.debug("Auto-detecting ports for cameras")
        try:
            ports = list_connected_cameras()
        except error.PanError as e:
            logger.warning(e)

        if len(ports) == 0:
            raise error.CameraNotFound(msg="No cameras detected. For testing, use camera simulator.")
        else:
            logger.debug(f"Detected {ports=}")

    primary_camera = None

    device_info = camera_config['devices']
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

        logger.debug(f'Creating camera: {model}')

        try:
            module = load_module(model)
            logger.debug(f'Camera module: {module=}')

            # We either got a class or a module.
            if callable(module):
                camera = module(**device_config)
            else:
                if hasattr(module, 'Camera'):
                    camera = module.Camera(**device_config)
                else:
                    raise error.NotFound(f'{module=} does not have a Camera object')
        except error.NotFound:
            logger.error(f"Cannot find camera module with config: {device_config}")
        except Exception as e:
            logger.error(f"Cannot create camera type: {model} {e}")
        else:
            # Check if the config specified a primary camera and if it matches.
            if camera.uid == camera_config.get('primary'):
                camera.is_primary = True
                primary_camera = camera

            logger.debug(f"Camera created: {camera=}")

            cameras[cam_name] = camera

    if len(cameras) == 0:
        raise error.CameraNotFound(msg="No cameras available")

    # If no camera was specified as primary use the first
    if primary_camera is None and auto_primary:
        logger.info(f'No primary camera given, assigning the first camera ({auto_primary=})')
        primary_camera = list(cameras.values())[0]  # First camera
        primary_camera.is_primary = True

    logger.info(f"Primary camera: {primary_camera}")
    logger.success(f"{len(cameras)} cameras created")

    return cameras


def create_camera_simulator(num_cameras=2, subcomponent_simulators=None, **kwargs):
    """Create simulator camera object(s).

    Args:
        num_cameras (int): The number of simulated cameras to create, default 2.
        simulators (list): Include simulators for listed subcomponents.

    Returns:
        OrderedDict: An ordered dictionary of created camera objects, with the
            camera name as key and camera instance as value. Returns an empty
            OrderedDict if there is no camera configuration items.

    Raises:
        error.CameraNotFound: Raised if camera cannot be found at specified port or if
            auto_detect=True and no cameras are found.
    """
    if num_cameras == 0:
        raise error.CameraNotFound(msg="Can't create zero cameras")

    # Set up a simulated camera config for each number of requested cameras.
    base_sim_config = kwargs.get('config') or {
        'model': 'panoptes.pocs.camera.simulator.dslr.Camera',
        'port': '/dev/camera/simulator',
        'readout_time': 0.5,
    }
    logger.debug(f"SimulatorCamera config: {base_sim_config=}")

    subcomponent_config = {
        'focuser': kwargs.get('focuser') or {'model': 'panoptes.pocs.focuser.simulator.Focuser',
                                             'focus_port': '/dev/ttyFAKE',
                                             'initial_position': 20000,
                                             'autofocus_range': (40, 80),
                                             'autofocus_step': (10, 20),
                                             'autofocus_seconds': 0.1,
                                             'autofocus_size': 500},
        'filterwheel': kwargs.get('filterwheel') or {'model': 'panoptes.pocs.filterwheel.simulator.FilterWheel',
                                                     'filter_names': ['one', 'deux', 'drei', 'quattro'],
                                                     'move_time': 0.1 * u.second,
                                                     'timeout': 0.5 * u.second}
    }

    subcomponent_simulators = subcomponent_simulators or list()

    sim_devices = list()
    for cam_num in range(num_cameras):
        cam_name = f'SimCam{cam_num:02d}'
        logger.debug(f'Using camera simulator {cam_name}')
        sim_cam_config = copy.deepcopy(base_sim_config)
        sim_cam_config['name'] = cam_name

        # Add in the subcomponents if requested.
        for sub_name, sub_config in subcomponent_config.items():
            if sub_name in subcomponent_simulators:
                sim_cam_config[sub_name] = sub_config

        sim_devices.append(sim_cam_config)

    simulator_config = dict(devices=sim_devices)

    return create_cameras_from_config(config=simulator_config)
