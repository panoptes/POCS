from ..utils.indi import PanIndiDevice

from ..utils.logger import has_logger
from ..utils import error
from ..utils import listify

import shutil
import subprocess


@has_logger
class AbstractCamera(object):

    """ Base class for both INDI and gphoto2 cameras """

    def __init__(self, config):
        self.config = config

        self.properties = None
        self.cooled = True
        self.cooling = False

        # Get the model and port number
        model = config.get('model')
        port = config.get('port')
        name = config.get('name')

        self.model = model
        self.port = port
        self.name = name

        self._connected = False

        self.logger.info('Camera {} created on {}'.format(self.name, self.config.get('port')))

##################################################################################################
# Methods
##################################################################################################

    def construct_filename(self):
        """
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera
        """
        return NotImplementedError()


class AbstractIndiCamera(AbstractCamera, PanIndiDevice):

    """ Abstract Camera class that uses INDI.

    Args:
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """
    pass

    def __init__(self, config):
        super().__init__(config)


class AbstractGPhotoCamera(AbstractCamera):

    """ Abstract camera class that uses gphoto2 interaction

    Args:
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """

    def __init__(self, config):
        super().__init__(config)

        self._gphoto2 = shutil.which('gphoto2')
        assert self._gphoto2 is not None, error.PanError("Can't find gphoto2")

        self.logger.info('Camera {} created on {}'.format(self.name, self.config.get('port')))

    def command(self, cmd):
        """ Run gphoto2 command """

        # Build the command.
        run_cmd = [self._gphoto2, '--port', self.port]
        run_cmd.extend(listify(cmd))

        self.logger.debug("gphoto2 command: {}".format(run_cmd))

        output = ''
        try:
            output = subprocess.check_output(cmd, universal_newlines=True).strip().split('\n')
            self.logger.debug("Output: {} {}".format(output, type(output)))
        except subprocess.CalledProcessError as e:
            raise error.InvalidCommand("Can't send command to server. {} \t {}".format(e, output))
        except Exception as e:
            raise error.PanError(e)

        return output
