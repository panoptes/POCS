""" Collection of UI modules for the admin web interface

"""

import tornado

class SensorStatus(tornado.web.UIModule):
	""" UI modules for the environmental sensors """
	def render(self):
		return self.render_string("sensor_status.html")

class Webcam(tornado.web.UIModule):
	""" A module for showing the webcam """
	def render(self, webcam):
		return self.render_string("webcams.html", webcam=webcam)
