import os
import os.path
import sys
import subprocess
import time
import datetime
import multiprocessing
import shutil

sys.path.append(os.path.join(os.path.dirname(__file__), "/var/panoptes/POCS"))
from panoptes.utils import logger, config, database


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
            brightness (str):   Initial camera brightness. Default "50%"
            gain (str):         Initial camera gain. Default "50%"
            delay (int):        Time to wait between captures. Default 1 (seconds)
    """

    def __init__(self, frames=255, resolution="1600x1200", brightness="50%", gain="50%", delay=1):
        self.logger.info("Starting webcams monitoring")

        # Lookup the webcams
        self.webcams = self.config.get('webcams')
        if self.webcams is None:
            err_msg = "No webcams to connect. Please check config.yaml and all appropriate ports"
            self.logger.warning(err_msg)
            sys.exit("")

        self._processes = list()

        # Create the processes
        for webcam in self.webcams:
            webcam_process = multiprocessing.Process(target=self.loop_capture, args=[webcam])
            webcam_process.daemon = True
            webcam_process.name = '{}_process'.format(webcam.get('name')).replace(' ', '_')
            self._processes.append(webcam_process)

        # Command for taking pics
        self.cmd = 'fswebcam'

        # Defaults
        self._timestamp = "%Y-%m-%d %H:%M:%S"
        self._thumbnail_resolution = '240x120'
        self.delay = delay

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
        self.logger.debug("Capturing image for {}...".format(webcam.get('name')))

        # Filename to save
        camera_name = webcam.get('port').split('/')[-1]

        # Create the directory for storing images
        webcam_dir = self.config.get('webcam_dir')
        date_dir = datetime.datetime.strftime(datetime.datetime.utcnow(), '%Y%m%d')
        timestamp = datetime.datetime.strftime(datetime.datetime.utcnow(), '%Y%m%d%H%M%S')

        try:
            os.makedirs("{}/{}".format(webcam_dir, date_dir), exist_ok=True)
        except OSError as err:
            self.logger.warning("Cannot create new dir: {} \t {}".format(date_dir, err))

        # Output file names
        out_file = '{}/{}/{}_{}.jpeg'.format(webcam_dir, date_dir, camera_name, timestamp)
        thumbnail_file = '{}/{}/tn_{}_{}.jpeg'.format(webcam_dir, date_dir, camera_name, timestamp)

        # Static files (always points to most recent)
        static_out_file = '{}/{}.jpeg'.format(webcam_dir, camera_name)
        static_thumbnail_file = '{}/tn_{}.jpeg'.format(webcam_dir, camera_name)

        # Assemble all the parameters
        params = " -d {} --title \"{}\" {} --save {} --scale {} {}".format(
            webcam.get('port'),
            webcam.get('name'),
            self.base_params,
            out_file,
            self._thumbnail_resolution,
            thumbnail_file
        )

        # Actually call the command. NOTE: This is a blocking call. See `start_capturing`
        try:
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

                # Symlink the latest image
                if os.path.lexists(static_out_file):
                    os.remove(static_out_file)
                if os.path.lexists(static_thumbnail_file):
                    os.remove(static_thumbnail_file)

                os.symlink(out_file, static_out_file)
                os.symlink(thumbnail_file, static_thumbnail_file)

                return retcode
        except OSError as e:
            self.logger.warning("Execution failed:".format(e, file=sys.stderr))

    def loop_capture(self, webcam):
        """ Calls `capture` in a loop for an individual camera """
        while True:
            self.logger.debug("Looping {} on process {}".format(
                webcam.get('name'), multiprocessing.current_process().name))
            self.capture(webcam)
            time.sleep(self.delay)

    def start_capturing(self):
        """ Starts the capturing loop for all cameras

        Depending on the number of frames taken for an individual image, capturing can
        take up to ~30 sec.
        """

        for process in self._processes:
            self.logger.info("Staring webcam capture loop for process {}".format(process.name))
            process.start()

    def stop_capturing(self):
        """ Stops the capturing loop for all cameras

        """
        for process in self._processes:
            self.logger.info("Stopping webcam capture loop for {}".format(process.name))
            process.terminate()
            process.join()  # http://pymotw.com/2/multiprocessing/basics.html recommends joining after
