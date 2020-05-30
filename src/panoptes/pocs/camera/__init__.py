from collections import OrderedDict
import re
import shutil
import subprocess

from astropy import units as u
from panoptes.pocs.camera.camera import AbstractCamera  # pragma: no flakes
from panoptes.pocs.camera.camera import AbstractGPhotoCamera  # pragma: no flakes

from panoptes.pocs.utils.logger import get_logger
from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.library import load_module


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


def create_cameras_from_config(config_port='6563', **kwargs):
    """Create camera object(s) based on the config.

    Creates a camera for each camera item listed in the config. Ensures the
    appropriate camera module is loaded.

    Args:
        config_port (str, optional): config_server port, default '6563'.
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
    logger = get_logger()

    config = get_config(port=config_port)

    # Helper method to first check kwargs then config
    def kwargs_or_config(item, default=None):
        return kwargs.get(item, config.get(item, default))

    cameras = OrderedDict()
    camera_info = kwargs_or_config('cameras')
    if not camera_info:
        # cameras section either missing or empty
        logger.info('No camera information in config.')
        return cameras

    logger.debug("Camera config: {}".format(camera_info))

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
            logger.debug("Detected Ports: {}".format(ports))

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
                logger.warning("No ports left for {}, skipping.".format(cam_name))
                continue
        else:
            try:
                connection_method = model_requires[model]
                if connection_method not in device_config:
                    logger.warning(f"Camera error: {connection_method} missing for {model}.")
            except KeyError as e:
                logger.warning(e)

        logger.debug(f'Creating camera: {model}')

        try:
            module = load_module(f'panoptes.pocs.camera.{model}')
            logger.debug('Camera module: {}'.format(module))
            # Create the camera object
            cam = module.Camera(config_port=config_port, **device_config)
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


def create_camera_simulator(num_cameras=2, config_port='6563', **kwargs):
    """Create simulator camera object(s).

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
    logger = get_logger()

    cameras = OrderedDict()

    # Create a minimal dummy camera config to get a simulated camera
    camera_info = {'autodetect': False,
                   'devices': [
                       {'model': 'simulator'}, ]}

    logger.debug("Camera config: {}".format(camera_info))

    primary_camera = None

    for cam_num in range(num_cameras):
        cam_name = 'SimCam{:02d}'.format(cam_num)

        logger.debug('Using camera simulator.')
        # Set up a simulated camera with fully configured simulated focuser
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
            # Simulator config should always ignore local settings.
            'ignore_local_config': True
        }

        logger.debug('Creating camera: {}'.format(device_config['model']))

        try:
            module = load_module('panoptes.pocs.camera.{}'.format(device_config['model']))
            logger.debug('Camera module: {}'.format(module))
            # Create the camera object
            cam = module.Camera(name=cam_name, config_port=config_port, **device_config)
        except error.NotFound:  # pragma: no cover
            logger.error("Cannot find camera module: {}".format(device_config['model']))
        except Exception as e:  # pragma: no cover
            logger.error("Cannot create camera type: {} {}".format(device_config['model'], e))
        else:
            is_primary = ''
            if cam_num == 0:
                cam.is_primary = True
                primary_camera = cam
                is_primary = ' [Primary]'

            logger.debug("Camera created: {} {}{}".format(cam.name, cam.uid, is_primary))

            cameras[cam_name] = cam

    if len(cameras) == 0:
        raise error.CameraNotFound(msg="No cameras available")

    logger.debug("Primary camera: {}", primary_camera)
    logger.debug("{} cameras created", len(cameras))

    return cameras
