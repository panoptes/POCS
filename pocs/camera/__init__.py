from collections import OrderedDict

from pocs.utils import error
from pocs.utils import load_module
from pocs.utils.config import load_config

from pocs.camera.camera import AbstractCamera  # pragma: no flakes
from pocs.camera.camera import AbstractGPhotoCamera  # pragma: no flakes

from pocs.utils import list_connected_cameras
from pocs.utils import logger as logger_module


def create_cameras_from_config(config=None, logger=None, **kwargs):
    """Creates a camera object(s)

    Loads the cameras via the configuration.

    Creates a camera for each camera item listed in the config. Ensures the
    appropriate camera module is loaded.

    Note:
        This does not actually make a connection to the camera. To do so,
        call 'camera.connect()' explicitly.

    Args:
        **kwargs (dict): Can pass a `cameras` object that overrides the info in
            the configuration file. Can also pass `auto_detect`(bool) to try and
            automatically discover the ports.

    Returns:
        OrderedDict: An ordered dictionary of created camera objects.

    Raises:
        error.CameraNotFound: Description
        error.PanError: Description
    """
    if not logger:
        logger = logger_module.get_root_logger()

    if not config:
        config = load_config(**kwargs)

    if 'cameras' not in config:
        logger.info('No camera information in config.')
        return None

    def kwargs_or_config(item, default=None):
        return kwargs.get(item, config.get(item, default))

    camera_info = kwargs_or_config('cameras')
    logger.debug("Camera config: \n {}".format(camera_info))

    a_simulator = 'camera' in kwargs_or_config('simulator', default=list())
    if a_simulator:
        logger.debug("Using simulator for camera")

    ports = list()

    # Lookup the connected ports if not using a simulator
    auto_detect = kwargs_or_config('auto_detect', default=False)

    if not a_simulator and auto_detect:
        logger.debug("Auto-detecting ports for cameras")
        try:
            ports = list_connected_cameras()
        except Exception as e:
            logger.warning(e)

        if len(ports) == 0:
            raise error.PanError(
                msg="No cameras detected. Use --simulator=camera for simulator.")
        else:
            logger.debug("Detected Ports: {}".format(ports))

    cameras = OrderedDict()
    primary_camera = None

    device_info = camera_info['devices']
    for cam_num, device_config in enumerate(device_info):
        cam_name = 'Cam{:02d}'.format(cam_num)

        if not a_simulator:
            camera_model = device_config.get('model')

            # Assign an auto-detected port. If none are left, skip
            if auto_detect:
                try:
                    camera_port = ports.pop()
                except IndexError:
                    logger.warning(
                        "No ports left for {}, skipping.".format(cam_name))
                    continue
            else:
                try:
                    camera_port = device_config['port']
                except KeyError:
                    raise error.CameraNotFound(
                        msg="No port specified and auto_detect=False")

            camera_focuser = device_config.get('focuser', None)
            camera_readout = device_config.get('readout_time', 6.0)

        else:
            # Set up a simulated camera with fully configured simulated
            # focuser
            camera_model = 'simulator'
            camera_port = '/dev/camera/simulator'
            camera_focuser = {'model': 'simulator',
                              'focus_port': '/dev/ttyFAKE',
                              'initial_position': 20000,
                              'autofocus_range': (40, 80),
                              'autofocus_step': (10, 20),
                              'autofocus_seconds': 0.1,
                              'autofocus_size': 500}
            camera_readout = 0.5

        camera_set_point = device_config.get('set_point', None)
        camera_filter = device_config.get('filter_type', None)

        logger.debug('Creating camera: {}'.format(camera_model))

        try:
            module = load_module('pocs.camera.{}'.format(camera_model))
            logger.debug('Camera module: {}'.format(module))
        except ImportError:
            raise error.CameraNotFound(msg=camera_model)
        else:
            # Create the camera object
            cam = module.Camera(name=cam_name,
                                model=camera_model,
                                port=camera_port,
                                set_point=camera_set_point,
                                filter_type=camera_filter,
                                focuser=camera_focuser,
                                readout_time=camera_readout)

            is_primary = ''
            if camera_info.get('primary', '') == cam.uid:
                primary_camera = cam
                is_primary = ' [Primary]'

            logger.debug("Camera created: {} {} {}".format(
                cam.name, cam.uid, is_primary))

            cameras[cam_name] = cam

    if len(cameras) == 0:
        raise error.CameraNotFound(
            msg="No cameras available. Exiting.", exit=True)

    # If no camera was specified as primary use the first
    if primary_camera is None:
        primary_camera = cameras['Cam00']

    logger.debug("Finished creating cameras from config")

    return cameras
