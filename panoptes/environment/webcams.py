import os
import sys
import subprocess
import time
import datetime
import threading

from panoptes.utils import logger, config, messaging, database


@logger.set_log_level(level='debug')
@logger.has_logger
@config.has_config
class Webcams(object):

    """ Simple module to take a picture with the webcams

    This class will capture images from any webcam entry in the config file.
    The capturing is done on a loop, with defaults of 255 stacked images and
    a minute cadence. The images then have their flux measured and the gain
    and brightness adjusted accordingly. Images analysis is stored in the (mongo)
    database

    Note:
            All parameters are optional.

    Note:
            This is a port of Olivier's `SKYCAM_start_webcamloop` function
            in skycam.c

    Args:
            frames (int):       Number of frames to capture per image. Default 255
            resolution (str):   Resolution for images. Default "1600x1200"
            brightness (str): Initial camera brightness. Default "50%"
            gain (str):       Initial camera gain. Default "50%"
            delay (int):        Time to wait between captures. Default 1 (seconds)
    """

    def __init__(self, frames=5, resolution="1600x1200", brightness="50%", gain="50%", delay=1):
        self.logger.info("Starting webcams monitoring")

        # Lookup the webcams
        self.cams = self.config.get('webcams')
        if self.cams is None:
            err_msg = "No webcams to connect. Please check config.yaml and all appropriate ports"
            self.logger.warning(err_msg)
            sys.exit("")

        # Command for taking pics
        self.cmd = 'fswebcam'

        # Defaults
        self._timestamp = "%Y-%m-%d %H:%M:%S"
        self._thumbnail_resolution = '240x120'

        # Create the string for the params
        self.base_params = "-F {} -r {} --set brightness={} --set gain={} --jpeg 100 --timestamp \"{}\" ".format(
            frames, resolution, brightness, gain, self._timestamp)

    def capture(self, webcam):
        """ Capture an image from a webcam

        Given a webcam, this attempts to capture an image using the subprocess
        command. Also creates a thumbnail of the image

        Args:
            webcam (dict): Entry for the webcam. Example::
                {
                    'name': 'Pier West',
                    'port': '/dev/video0',
                    'params': [{'rotate': 270}],
                }

            The values for the `params` key will be passed directly to fswebcam
        """
        assert isinstance(webcam, dict)

        # Create the directory for storing images
        webcam_dir = self.config.get('webcam_dir')
        date_dir = datetime.datetime.strftime(datetime.datetime.utcnow(), '%Y%m%d')
        timestamp = datetime.datetime.strftime(datetime.datetime.utcnow(), '%Y%m%d%H%M%S')

        try:
            os.makedirs("{}/{}".format(webcam_dir, date_dir), exist_ok=True)
        except OSError as err:
            self.logger.warning("Cannot create new dir: {} \t {}".format(date_dir, err))

        # Filename to save: /dev/video0 to webcam0
        camera_name = webcam.get('port').split('/')[-1].replace('video', 'webcam')

        # Output file names
        out_file = '{}/{}/{}_{}.jpeg'.format(webcam_dir, date_dir, camera_name, timestamp)
        thumbnail_file = '{}/{}/tn_{}_{}.jpeg'.format(webcam_dir, date_dir, camera_name, timestamp)

        # Assemble all the parameters
        params = " -d {} --title {} {} --save {} --scale {} {}".format(
            webcam.get('port'),
            webcam.get('name'),
            self.base_params,
            out_file,
            self._thumbnail_resolution,
            thumbnail_file
        )

        # Actually call the command. NOTE: This is a blocking call. See `start_capturing`
        try:
            self.logger.debug("Capturing image for {}...".format(webcam.get('name')))

            retcode = subprocess.call(self.cmd + params, shell=True, stdout=subprocess.DEVNULL)

            if retcode < 0:
                print("Child was terminated by signal", -retcode, file=sys.stderr)
                self.logger.warning(
                    "Image captured terminated for {}. Return code: {} \t Error: {}".format(
                        webcam.get('name'),
                        retcode,
                        sys.stderr
                    )
                )
            else:
                self.logger.debug("Image captured for {}. Return code: {}".format(
                    webcam.get('name'),
                    retcode
                ))
        except OSError as e:
            print("Execution failed:", e, file=sys.stderr)

    def start_capturing(self):
        """ Starts the capturing loop.

        Depending on the number of frames taken for an individual image, capturing can
        take up to ~30 sec. Because this is I/O bound, we call these in separate threads
        for each webcam.
        """
        self.logger.info("Staring webcam capture loop")
        for webcam in self.webcams:
            webcam_thread = threading.Thread(target=self.capture(webcam))
            webcam_thread.start()


if __name__ == '__main__':
    webcams = Webcams()
    webcams.start_capturing()