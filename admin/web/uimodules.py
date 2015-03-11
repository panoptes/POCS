""" Collection of UI modules for the admin web interface

"""

import tornado


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
