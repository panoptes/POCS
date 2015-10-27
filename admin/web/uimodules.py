""" Collection of UI modules for the admin web interface

"""

import tornado
import glob

from astropy.time import Time
from panoptes.utils import load_config

config = load_config()


class MountControl(tornado.web.UIModule):

    """ UI modules for controlling the MountControl

    The mount is controlled by exchanging messages back and forth
    with the running Panoptes instance, which acts as a message broker
    for the mount. See `Panoptes` for more information.
    """

    def render(self):
        return self.render_string("mount_control.html")


class SensorStatus(tornado.web.UIModule):

    """ UI modules for the environmental sensors """

    def render(self):

        return self.render_string("sensor_status.html")


class Webcam(tornado.web.UIModule):

    """ A module for showing the webcam """

    def render(self, webcam):
        return self.render_string("webcams.html", webcam=webcam)


class ImageList(tornado.web.UIModule):

    """ UI modules for listing the current images """

    def render(self):

        image_dir = config.get('image_dir', '/var/panoptes/images/')

        # Get the date
        date_dir = Time.now().iso.split(' ')[0].replace('-', '')

        img_list = glob.glob("{}/**/*.jpg".format(image_dir))

        return self.render_string("image_list.html", img_list=img_list)
