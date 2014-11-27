#!/usr/bin/python3

import time
import datetime
import json
import matplotlib.pyplot as plt
import numpy as np
import sys
from PyQt4 import QtGui
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg \
  import FigureCanvasQTAgg as FigureCanvas

import panoptes.utils.config as config
import panoptes.utils.logger as logger
import panoptes.utils.serial as serial
import panoptes.utils.error as error

@logger.set_log_level('debug')
@logger.has_logger
@config.has_config
class ArduinoSerialMonitor(FigureCanvas):
    """Realtime plotting of Arduino serial sensor data"""
    def __init__(self):
        # initialize the iteration counter for scrolling window
        self.count = 0
        self.window_size = 30 # seconds of history to display

        # Hold information on sensors read
        self.sensor_readings = dict()
        self.sensor_plots = dict()

        self._setup_plot()

        # Get the class for getting data from serial sensor
        self.port = self.config.get('camera_box').get('port', '/dev/ttyACM0')
        self.serial_reader = serial.SerialData(port=self.port, threaded=True)
        self.serial_reader.connect()

        self.logger.info(self.serial_reader.read())

        # Timer
        self.timerEvent(None)
        self.timer = self.startTimer(100)

    def _setup_plot(self):
        # Image setup
        self.fig = Figure()

        FigureCanvas.__init__(self, self.fig)

        # Create plot, set x and y axes
        self.ax = self.fig.add_subplot(111)
        self.ax.set_ylim(0, 100)

        # Build up timestamps
        base = datetime.datetime.now()
        date_ranges = [base - datetime.timedelta(seconds=x) for x in range(0,self.window_size)]

        for pin in ['c', 'h']:
            sensor_values = [0] * self.window_size

            s_plot, = self.ax.plot(date_ranges,sensor_values, label="{}".format(pin))

            # Add the ax and plot to our monitor
            self.sensor_readings[pin] = sensor_values
            plot_dict = {'plot': s_plot}
            self.sensor_plots[pin] = plot_dict

        # Show legend
        self.ax.legend()

        # Fix date formatting
        self.fig.autofmt_xdate();

        # Draw the initial canvas
        self.fig.canvas.draw()


    def _prepare_sensor_data(self):
        """Helper function to return serial sensor info"""
        sensor_value = self.serial_reader.next()

        sensor_data = dict()
        if len(sensor_value) > 0:
            try:
                sensor_data = json.loads(sensor_value)
            except ValueError:
                print("Bad JSON: {0}".format(sensor_value))

        return sensor_data

    def get_reading(self):
        """Get the serial reading from the sensor"""
        # take the current serial sensor information
        return self._prepare_sensor_data()

    def timerEvent(self, evt):
        """Custom timerEvent code, called at timer event receive"""

        sensor_data = self.get_reading()
        self.logger.debug(sensor_data)

        # for sensor, value in sensor_data.items():
        #     self.logger.debug("Sensor: {} \t Value: {}".format(sensor, value))
        #     if sensor == 'temperature':
        #         self.logger.debug("Plotting temperature")
        #         for pin in value.keys():
        #             self.logger.debug("{} = {}".format(pin, value.get(pin)))
        #             # Append new data to the datasets
        #             self.sensor_readings[pin].append(value.get(pin))

        #             # Scrolling horizontal axis is calculated - basically
        #             # if our number of readings is abover the size, start scrolling.
        #             # We add 15 so the right edge of line is not butting up against edge
        #             # of graph but has some nice buffer space

        #             num_readings = len(self.sensor_readings[pin])
        #             self.logger.debug("num_readings: {}".format(num_readings))

        #             # Build up timestamps
        #             base = datetime.datetime.now()
        #             date_ranges = [base - datetime.timedelta(seconds=x) for x in range(0,num_readings*5,5)]

        #             # Update lines data using the lists with new data
        #             # plot_data = (range(num_readings),self.sensor_readings[pin])
        #             try:
        #                 plt = self.sensor_plots[pin]['plot']
        #                 self.logger.debug(date_ranges)
        #                 plt.set_data(date_rangess,stelf.sensor_readings[pin])
        #             except:
        #                 self.logger.error("Some problem")


        # # force a redraw of the Figure - we start with an initial
        # # horizontal axes but 'scroll' as time goes by
        # if(self.count >= self.window_size):
        #     self.logger.debug("Forcing redraw")
        #     self.ax.set_xlim(self.count - self.window_size, self.count + 15)
        #     self.fig.canvas.draw()

        # self.count += 1


# Build and run the actual appliation
app = QtGui.QApplication(sys.argv)
widget = ArduinoSerialMonitor()
widget.setWindowTitle("Serial Monitor")
widget.show()
sys.exit(app.exec_())