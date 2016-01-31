""" Collection of UI modules for the admin web interface

"""

import tornado
import glob


class MountInfo(tornado.web.UIModule):

    """ Displays information about the mount """

    def render(self):
        return self.render_string("mount_info.html")


class TargetInfo(tornado.web.UIModule):

    """ Displays information about the target """

    def render(self):
        return self.render_string("target_info.html")


class SensorStatus(tornado.web.UIModule):

    """ UI modules for the environmental sensors """

    def render(self):

        return self.render_string("sensor_status.html")


class BotChat(tornado.web.UIModule):

    """ UI modules for chatting with the bot """

    def render(self):

        return self.render_string("bot_chat.html")


class Webcam(tornado.web.UIModule):

    """ A module for showing the webcam """

    def render(self, webcam):
        return self.render_string("webcams.html", webcam=webcam)


class CurrentImage(tornado.web.UIModule):

    """ UI modules for listing the current images """

    def render(self, img_fn, title=''):

        return self.render_string("display_image.html", img=img_fn, title=title)


class ImageList(tornado.web.UIModule):

    """ UI modules for listing the current images """

    def render(self):

        # image_dir = config.get('image_dir', '/var/panoptes/images/')

        # Get the date
        # date_dir = Time.now().iso.split(' ')[0].replace('-', '')

        img_list = glob.glob("{}/**/*.jpg".format('/var/panoptes/images'))

        images = [img.replace('/var/panoptes/images', '') for img in img_list]

        images.sort()
        images.reverse()

        return self.render_string("image_list.html", img_list=images)
