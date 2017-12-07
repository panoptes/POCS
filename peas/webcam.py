import os
import os.path
import shutil
import subprocess
import sys

from glob import glob

from pocs.utils import current_time
from pocs.utils.logger import get_root_logger

from pocs.utils.config import load_config


class Webcam(object):

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
            webcam (dict):      Config options for the camera, required.
            frames (int):       Number of frames to capture per image. Default 255
            resolution (str):   Resolution for images. Default "1600x1200"
            brightness (str):   Initial camera brightness. Default "50%"
            gain (str):         Initial camera gain. Default "50%"
            delay (int):        Time to wait between captures. Default 60 (seconds)
    """

    def __init__(self,
                 webcam_config,
                 frames=255,
                 resolution="1600x1200",
                 brightness="50%",
                 gain="50%"):

        self.config = load_config(config_files='peas')

        self.logger = get_root_logger()

        self._today_dir = None

        self.webcam_dir = self.config['directories'].get('webcam', '/var/panoptes/webcams/')
        assert os.path.exists(self.webcam_dir), self.logger.warning(
            "Webcam directory must exist: {}".format(self.webcam_dir))

        self.logger.info("Creating webcams")

        # Lookup the webcams
        if webcam_config is None:
            err_msg = "No webcams to connect. Please check config.yaml and all appropriate ports"
            self.logger.warning(err_msg)

        self.webcam_config = webcam_config
        self.name = self.webcam_config.get('name', 'GenericWebCam')

        self.port_name = self.webcam_config.get('port').split('/')[-1]

        # Command for taking pics
        self.cmd = shutil.which('fswebcam')

        # Defaults
        self._timestamp = "%Y-%m-%d %H:%M:%S"
        self._thumbnail_resolution = '240x120'

        # Create the string for the params
        self.base_params = "-F {} -r {} --set brightness={} --set gain={} --jpeg 100 --timestamp \"{}\" ".format(
            frames, resolution, brightness, gain, self._timestamp)

        self.logger.info("{} created".format(self.name))

    def capture(self):
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
        webcam = self.webcam_config

        assert isinstance(webcam, dict)

        self.logger.debug("Capturing image for {}...".format(webcam.get('name')))

        camera_name = self.port_name

        # Create the directory for storing images
        timestamp = current_time(flatten=True)
        today_dir = timestamp.split('T')[0]
        today_path = "{}/{}".format(self.webcam_dir, today_dir)

        try:

            if today_path != self._today_dir:
                # If yesterday is not None, archive it
                if self._today_dir is not None:
                    self.logger.debug("Making timelapse for webcam")
                    self.create_timelapse(
                        self._today_dir, out_file="{}/{}_{}.mp4".format(
                            self.webcam_dir, today_dir, self.port_name),
                        remove_after=True)

                # If today doesn't exist, make it
                if not os.path.exists(today_path):
                    self.logger.debug("Making directory for day's webcam")
                    os.makedirs(today_path, exist_ok=True)
                    self._today_dir = today_path

        except OSError as err:
            self.logger.warning("Cannot create new dir: {} \t {}".format(today_path, err))

        # Output file names
        out_file = '{}/{}_{}.jpeg'.format(today_path, camera_name, timestamp)

        # We also create a thumbnail and always link it to the same image
        # name so that it is always current.
        thumbnail_file = '{}/tn_{}.jpeg'.format(self.webcam_dir, camera_name)

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

        static_out_file = ''

        # Actually call the command.
        # NOTE: This is a blocking call (within this process). See `start_capturing`
        try:
            self.logger.debug("Webcam subproccess command: {} {}".format(self.cmd, params))

            with open(os.devnull, 'w') as devnull:
                retcode = subprocess.call(self.cmd + params, shell=True,
                                          stdout=devnull, stderr=devnull)

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
                static_out_file = '{}/{}.jpeg'.format(self.webcam_dir, camera_name)
                static_tn_out_file = '{}/tn_{}.jpeg'.format(self.webcam_dir, camera_name)

                # Symlink the latest image and thumbnail
                if os.path.lexists(static_out_file):
                    os.remove(static_out_file)
                os.symlink(out_file, static_out_file)

                if os.path.lexists(static_tn_out_file):
                    os.remove(static_tn_out_file)
                os.symlink(out_file, static_tn_out_file)

                return retcode
        except OSError as e:
            self.logger.warning("Execution failed:".format(e, file=sys.stderr))

        return {'out_fn': static_out_file}

    def create_timelapse(self, directory, fps=12, out_file=None, remove_after=False):
        """ Create a timelapse movie for the given directory """
        assert os.path.exists(directory), self.logger.warning(
            "Directory does not exist: {}".format(directory))
        ffmpeg_cmd = shutil.which('ffmpeg')

        if out_file is None:
            out_file = self.port_name
            out_file = '{}/{}.mp4'.format(directory, out_file)

        cmd = [ffmpeg_cmd, '-f', 'image2', '-r', str(fps), '-pattern_type', 'glob',
               '-i', '{}{}*.jpeg'.format(directory, self.port_name), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', out_file]

        self.logger.debug("Timelapse command: {}".format(cmd))
        try:
            subprocess.run(cmd)
        except subprocess.CalledProcessError as err:
            self.logger.warning("Problem making timelapse: {}".format(err))

        if remove_after:
            self.logger.debug("Removing all images files")
            for f in glob('{}{}*.jpeg'.format(directory, self.port_name)):
                os.remove(f)
