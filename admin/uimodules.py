import tornado.web

class SensorStatus(tornado.web.UIModule):
	""" UI modules for the environmental sensors """
	def render(self, sensor_data):
		return self.render_string("sensor_status.html", sensor_data=sensor_data)