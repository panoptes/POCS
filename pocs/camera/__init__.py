from collections import OrderedDict
import re
import shutil
import subprocess

from astropy import units as u

from pocs import hardware
from pocs.utils import error
from pocs.utils import load_module
from pocs.utils.config import load_config

from pocs.camera.camera import AbstractCamera  # pragma: no flakes
from pocs.camera.camera import AbstractGPhotoCamera  # pragma: no flakes

from pocs.utils import logger as logger_module


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


def create_cameras_from_config(config=None, logger=None, **kwargs):
    """Create camera object(s) based on the config.

    Creates a camera for each camera item listed in the config. Ensures the
    appropriate camera module is loaded.

    Args:
        **kwargs (dict): Can pass a `cameras` object that overrides the info in
            the configuration file. Can also pass `auto_detect`(bool) to try and
            automatically discover the ports.

    Returns:
        OrderedDict: An ordered dictionary of created camera objects, with the
            camera name as key and camera instance as value. Returns an empty
            OrderedDict if there is no camera configuration items.

    Raises:
        error.CameraNotFound: Raised if camera cannot be found at specified port or if
            auto_detect=True and no cameras are found.
        error.PanError: Description
    """
    if not logger:
        logger = logger_module.get_root_logger()

    if not config:
        config = load_config(**kwargs)

    # Helper method to first check kwargs then config
    def kwargs_or_config(item, default=None):
        return kwargs.get(item, config.get(item, default))

    simulator_names = hardware.get_simulator_names(config=config, kwargs=kwargs)
    logger.debug(f'simulator_names = {", ".join(simulator_names)}')
    a_simulator = 'camera' in simulator_names

    cameras = OrderedDict()
    camera_info = kwargs_or_config('cameras')
    if not camera_info:
        # cameras section either missing or empty
        if not a_simulator:
            logger.info('No camera information in config.')
            return cameras
        else:
            # Create a minimal dummy camera config to get a simulated camera
            camera_info = {'autodetect': False,
                           'devices': [
                               {'model': 'simulator'}, ]}

    logger.debug("Camera config: {}".format(camera_info))

    auto_detect = camera_info.get('auto_detect', False)

    ports = list()

    # Lookup the connected ports if not using a simulator
    if not a_simulator and auto_detect:
        logger.debug("Auto-detecting ports for cameras")
        try:
            ports = list_connected_cameras()
        except Exception as e:
            logger.warning(e)

        if len(ports) == 0:
            raise error.PanError(
                msg="No cameras detected. For testing, use camera simulator.")
        else:
            logger.debug("Detected Ports: {}".format(ports))

    primary_camera = None

    device_info = camera_info['devices']
    for cam_num, device_config in enumerate(device_info):
        cam_name = 'Cam{:02d}'.format(cam_num)

        if not a_simulator:
            # Assign an auto-detected port. If none are left, skip
            if auto_detect:
                try:
                    device_config['port'] = ports.pop()
                except IndexError:
                    logger.warning("No ports left for {}, skipping.".format(cam_name))
                    continue
            else:
                if not ('port' in device_config or 'serial_number' in device_config):
                    raise error.CameraNotFound(msg="No port specified and auto_detect=False")

            device_config.setdefault('focuser', None)
            device_config.setdefault('filterwheel', None)
            device_config.setdefault('readout_time', 6.0)

        else:
            logger.debug('Using camera simulator.')
            # Set up a simulated camera with fully configured simulated
            # focuser
            device_config['model'] = 'simulator'
            device_config['port'] = '/dev/camera/simulator'
            device_config['focuser'] = {'model': 'simulator',
                                        'focus_port': '/dev/ttyFAKE',
                                        'initial_position': 20000,
                                        'autofocus_range': (40, 80),
                                        'autofocus_step': (10, 20),
                                        'autofocus_seconds': 0.1,
                                        'autofocus_size': 500}
            device_config['filterwheel'] = {'model': 'simulator',
                                            'filter_names': ['one', 'deux', 'drei', 'quattro'],
                                            'move_time': 0.1 * u.second,
                                            'timeout': 0.5 * u.second}
            device_config['readout_time'] = 0.5

        device_config.setdefault('set_point', None)
        device_config.setdefault('filter_type', None)

        logger.debug('Creating camera: {}'.format(device_config['model']))

        try:
            module = load_module('pocs.camera.{}'.format(device_config['model']))
            logger.debug('Camera module: {}'.format(module))
            # Create the camera object
            cam = module.Camera(name=cam_name, **device_config)
        except Exception as e:
            # Warn if bad camera but keep trying other cameras
            logger.error(msg="Cannot find camera type: {} {}".format(device_config['model'], e))
        else:
            is_primary = ''
            if camera_info.get('primary', '') == cam.uid:
                cam.is_primary = True
                primary_camera = cam
                is_primary = ' [Primary]'

            logger.debug("Camera created: {} {}{}".format(
                cam.name, cam.uid, is_primary))

            cameras[cam_name] = cam

    if len(cameras) == 0:
        raise error.CameraNotFound(
            msg="No cameras available. Exiting.", exit=True)

    # If no camera was specified as primary use the first
    if primary_camera is None:
        primary_camera = list(cameras.values())[0]  # First camera
        primary_camera.is_primary = True

    logger.debug("Primary camera: {}", primary_camera)
    logger.debug("{} cameras created", len(cameras))

    return cameras
