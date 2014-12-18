import tornado.web

class SensorStatus(tornado.web.UIModule):
	""" UI modules for the environmental sensors """
	def render(self):
		return self.render_string("sensor_status.html")