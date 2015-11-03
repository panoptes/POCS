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
            "artist": {"artist": "Project PANOPTES"},
            "autoexposuremode": {"autoexposuremode4": "On"},
            "autofocusdrive": {"autofocusdrive0": "Off", "autofocusdrive1": "On"},
            "autopoweroff": {"autopoweroff": "0"},
            "CAPTURE_FORMAT": {"FORMAT9": "On"},
            "capturetarget": {"capturetarget1": "On"},
            "CCD_COMPRESSION": {"CCD_RAW": "On"},
            "CCD_INFO": {"CCD_PIXEL_SIZE": "4.3", "CCD_PIXEL_SIZE_X": "4.3", "CCD_PIXEL_SIZE_Y": "4.3"},
            "CCD_ISO": {"ISO1": "On"},
            "continuousaf": {"continuousaf0": "Off", "continuousaf1": "On"},
            "copyright": {"copyright": "Project PANOPTES All Rights Reserved"},
            "imageformatcf": {"imageformatcf9": "On"},
            "imageformatsd": {"imageformatsd9": "On"},
            "ownername": {"ownername": "Project PANOPTES"},
            "picturestyle": {"picturestyle1": "On", },
            "reviewtime": {"reviewtime0": "On", },
            'Transfer Format': {'FITS': 'On', 'Native': 'Off'},
            "UPLOAD_MODE": {"UPLOAD_BOTH": "On"},
            "UPLOAD_SETTINGS": {"UPLOAD_DIR": "/var/panoptes/images/", "UPLOAD_PREFIX": "{}_XXX".format(self.name)},
            "viewfinder": {"viewfinder0": "Off", "viewfinder1": "On"},
            # "WCS_CONTROL": {"WCS_ENABLE": "Off"},
            'WCS_CONTROL': {'WCS_ENABLE': 'On'},
        }

        try:
            self.connect()
        except error.InvalidCommand:
            self.logger.warning(
                "Problem connecting to {}, camera unavailable. You should probably try to fix this.".format(self.name))
        else:
            self.logger.info("{} connected".format(self.name))

        self.last_start_time = None

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
            output = self.set_property('CCD_EXPOSURE', {'CCD_EXPOSURE_VALUE': '{:.03f}'.format(exptime)})
            self.logger.info("Output from exposure: {}".format(output))
            self.last_start_time = datetime.datetime.now()
        except Exception as e:
            raise error.PanError(e)
