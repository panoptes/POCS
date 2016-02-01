import os
import os.path
import sys
import subprocess
import time
import datetime
import multiprocessing

from ..utils.logger import get_logger
from ..utils.config import load_config
from ..utils import current_time


class Webcams(object):

    """ Simple module to take a picture with the webcams

    This class will capture images from any webcam entry in the config file.
    The capturing is done on a loop, with defaults of 255 stacked images and
    a minute cadence.


    Note:
            All parameters are optional.

    Note:
            This is a port of Olivier's `SKYCAM_start_webcamloop` function
            in skycam.c

    Note:
            TODO: The images then have their flux measured and the gain and brightness
            adjusted accordingly. Images analysis is stored in the (mongo) database

    Args:
            frames (int):       Number of frames to capture per image. Default 255
            resolution (str):   Resolution for images. Default "1600x1200"
            brightness (str):   Initial camera brightness. Default "50%"
            gain (str):         Initial camera gain. Default "50%"
            delay (int):        Time to wait between captures. Default 60 (seconds)
    """

    def __init__(self, config=None, frames=255, resolution="1600x1200", brightness="50%", gain="50%"):
        self.logger = get_logger(self)
        self.config = load_config()
        assert self.config is not None, self.logger.warning("Config not set for webcams")

        self.logger.info("Creating webcams monitoring")

        # Lookup the webcams
        self.webcams = self.config.get('webcams')
        if self.webcams is None:
            err_msg = "No webcams to connect. Please check config.yaml and all appropriate ports"
            self.logger.warning(err_msg)

        self._is_capturing = False
        self._processes = list()

        # Create the processes
        for webcam in self.webcams:
            webcam_process = multiprocessing.Process(target=self.loop_capture, args=[webcam])
            webcam_process.daemon = True
            webcam_process.name = 'PANOPTES_{}'.format(webcam.get('name')).replace(' ', '_')
            self._processes.append(webcam_process)

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
                    'params': {
                        'rotate': 270
                    },
                }

            The values for the `params` key will be passed directly to fswebcam
        """
        assert isinstance(webcam, dict)
        self.logger.debug("Capturing image for {}...".format(webcam.get('name')))

        # Filename to save
        camera_name = webcam.get('port').split('/')[-1]

        # Create the directory for storing images
        webcam_dir = self.config['directories'].get('webcam')
        timestamp = current_time().isot
        date_dir = timestamp.split('T')[0].replace('-', '')

        try:
            os.makedirs("{}/{}".format(webcam_dir, date_dir), exist_ok=True)
        except OSError as err:
            self.logger.warning("Cannot create new dir: {} \t {}".format(date_dir, err))

        # Output file names
        out_file = '{}/{}/{}_{}.jpeg'.format(webcam_dir, date_dir, camera_name, timestamp)

        # We also create a thumbnail and always link it to the same image
        # name so that it is always current.
        thumbnail_file = '{}/tn_{}.jpeg'.format(webcam_dir, camera_name)

        options = self.base_params
        if 'params' in webcam:
            for opt, val in webcam.get('params').items():
                options += "--{}={}".format(opt, val)

        # Assemble all the parameters
        params = " -d {} --title \"{}\" {} --save {} --scale {} {}".format(
            webcam.get('port'),
            webcam.get('name'),
            options,
            out_file,
            self._thumbnail_resolution,
            thumbnail_file
        )

        # Actually call the command.
        # NOTE: This is a blocking call (within this process). See `start_capturing`
        try:
            self.logger.debug("Webcam subproccess command: {} {}".format(self.cmd, params))
            with open(os.devnull, 'w') as devnull:
                retcode = subprocess.call(self.cmd + params, shell=True, stdout=devnull, stderr=devnull)

            if retcode < 0:
                self.logger.warning(
                    "Image captured terminated for {}. Return code: {} \t Error: {}".format(
                        webcam.get('name'),
                        retcode,
                        sys.stderr
                    )
                )
            else:
                self.logger.debug("Image captured for {}".format(webcam.get('name')))

                # Static files (always points to most recent)
                static_out_file = '{}/{}.jpeg'.format(webcam_dir, camera_name)

                # Symlink the latest image
                if os.path.lexists(static_out_file):
                    os.remove(static_out_file)

                os.symlink(out_file, static_out_file)

                return retcode
        except OSError as e:
            self.logger.warning("Execution failed:".format(e, file=sys.stderr))

    def loop_capture(self, webcam):
        """ Calls `capture` in a loop for an individual camera """
        while True and self.is_capturing:
            self.logger.debug("Looping {} on process {}".format(
                webcam.get('name'), multiprocessing.current_process().name))
            self.capture(webcam)
            time.sleep(webcam.get('delay', 60))

    def start_capturing(self):
        """ Starts the capturing loop for all cameras

        Depending on the number of frames taken for an individual image, capturing can
        take up to ~30 sec.
        """

        self.is_capturing = True
        for process in self._processes:
            self.logger.info("Staring webcam capture loop for process {}".format(process.name))
            try:
                process.start()
            except AssertionError:
                self.logger.info("Can't start, trying to run")
                process.run()

    def stop_capturing(self):
        """ Stops the capturing loop for all cameras

        """
        for process in self._processes:
            self.logger.info("Stopping webcam capture loop for {}".format(process.name))
            self.is_capturing = False
            process.terminate()
            process.join()

    @property
    def is_capturing(self):
        return self._is_capturing

    @is_capturing.setter
    def is_capturing(self, value):
        self._is_capturing = value
