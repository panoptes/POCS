import subprocess
import panoptes.utils.logger as logger

@logger.has_logger
class AbstractCamera:
    """
    Main camera class
    """

    def __init__(self):
        ## Properties for all cameras
        self.connected = False
        self.cooling = None
        self.cooled = None
        self.exposing = None


def list_connected_cameras(logger=None):
    """
    Uses gphoto2 to try and detect which cameras are connected.

    Cameras should be known and placed in config but this is a useful utility.
    """

    command = ['gphoto2', '--auto-detect']
    result = subprocess.check_output(command)
    lines = result.decode('utf-8').split('\n')

    ports = []

    for line in lines:
        camera_match = re.match('([\w\d\s_\.]{30})\s(usb:\d{3},\d{3})', line)
        if camera_match:
            camera_name = camera_match.group(1).strip()
            port = camera_match.group(2).strip()
            if logger: logger.info('Found "{}" on port "{}"'.format(camera_name, port))
            ports.append(port)

    return ports