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
            'CCD_ISO': {'ISO1': 'On'},
            'Transfer Format': {'FITS': 'On', 'Native': 'Off'},
            'UPLOAD_MODE': {'UPLOAD_LOCAL': 'On'},
            'UPLOAD_SETTINGS': {'UPLOAD_DIR': '/var/panoptes/images/', 'UPLOAD_PREFIX': 'IMAGE_XXX'},
            # 'WCS_CONTROL': {'WCS_ENABLE': 'On'},
            'artist': {'artist': 'Project PANOPTES'},
            'autopoweroff': {'autopoweroff': '0'},
            'copyright': {'copyright': 'Project PANOPTES All Rights Reserved'},
            'imageformatcf': {'imageformatcf8': 'On'},
            'imageformatsd': {'imageformatsd8': 'On'},
            'ownername': {'ownername': 'Project PANOPTES'},
            'picturestyle': {'picturestyle1': 'On', },
            'reviewtime': {'reviewtime0': 'On', },
            'viewfinder': {'viewfinder1': 'On'},
            'autoexposuremode': {'autoexposuremode3': 'On'},
            'CCD_INFO': {'CCD_PIXEL_SIZE': '4.3'},
            # 'CCD_INFO': {'CCD_PIXEL_SIZE_Y': '4.3'},
            'continuousaf': {'continuousaf0': 'On'},
            'capturetarget': {'capturetarget1': 'On'},
        }

        try:
            self.connect()
        except error.InvalidCommand:
            self.logger.warning(
                "Problem connecting to {}, camera unavailable. You should probably try to fix this.".format(self.name))
        else:
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
