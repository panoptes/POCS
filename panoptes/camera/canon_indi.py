import datetime

from . import AbstractCamera

from ..utils.logger import has_logger
from ..utils import error


@has_logger
class Camera(AbstractCamera):

    def __init__(self, config):
        config['driver'] = 'indi_gphoto_ccd'
        super().__init__(config)

        self.config['init_commands'] = {
            'Auto Focus': {'Set': 'Off'},
            'CAPTURE_FORMAT': {'FORMAT9': 'On'},
            'CCD_COMPRESSION': {'CCD_RAW': 'On'},
            'CCD_ISO': {'ISO0': 'On'},
            'Transfer Format': {'FITS': 'On', 'Native': 'Off'},
            'UPLOAD_MODE': {'UPLOAD_LOCAL': 'On'},
            'UPLOAD_SETTINGS': {'UPLOAD_DIR': '/var/panoptes/images/', 'UPLOAD_PREFIX': 'IMAGE_XXX'},
            'WCS_CONTROL': {'WCS_ENABLE': 'On'},
            'aeb': {'aeb0': 'On', },
            'artist': {'artist': 'Project PANOPTES'},
            'autopoweroff': {'autopoweroff': '0'},
            'copyright': {'copyright': 'Project PANOPTES All Rights Reservered'},
            'imageformatcf': {'imageformatcf9': 'On'},
            'imageformatsd': {'imageformatsd9': 'On'},
            'ownername': {'ownername': 'Project PANOPTES'},
            'picturestyle': {'picturestyle1': 'On', },
            'reviewtime': {'reviewtime0': 'On', },
            'viewfinder': {'viewfinder1': 'On'},
        }

        self.connect()
        assert self.is_connected, error.InvalidCommand("Camera not connected")
        self.logger.info("{} connected".format(self.name))

        self.last_start_time = None

    def start_cooling(self):
        '''
        This does nothing for a Canon DSLR as it does not have cooling.
        '''
        self.logger.info('No camera cooling available')
        self.cooling = True

    def stop_cooling(self):
        '''
        This does nothing for a Canon DSLR as it does not have cooling.
        '''
        self.logger.info('No camera cooling available')
        self.cooling = False

    def construct_filename(self):
        '''
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera
        '''
        if self.last_start_time:
            filename = self.last_start_time.strftime('{}_%Y%m%dat%H%M%S.cr2'.format(self.name))
        else:
            filename = self.last_start_time.strftime('image.cr2')
        return filename

    def take_exposure(self, exptime=5):
        """ Take an exposure """
        self.logger.info("<<<<<<<< Exposure >>>>>>>>>")
        self.logger.info('Taking {} second exposure'.format(exptime))

        try:
            self.set_property('CCD_EXPOSURE', 'CCD_EXPOSURE_VALUE', '{}'.format(exptime))
            self.last_start_time = datetime.datetime.now()
        except Exception as e:
            raise error.PanError(e)
