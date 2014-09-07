#!/usr/bin/python3

import time
import datetime
import json
import serial
import matplotlib.pyplot as plt
import numpy as np
import sys
from PyQt4 import QtGui
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt4agg \
  import FigureCanvasQTAgg as FigureCanvas

from Arduino.SerialIO import SerialData

class ArduinoSerialMonitor(FigureCanvas):
    """Realtime plotting of Arduino serial sensor data"""
    def __init__(self):
        # initialize the iteration counter for scrolling window
        self.count = 0
        self.window_size = 30 # seconds of history to display

        # Get the class for getting data from serial sensor
        self.serial_reader = SerialData()

        # Hold information on sensors read
        self.sensor_readings = dict()
        self.sensor_plots = dict()

        self._setup_plot()

        # Timer
        self.timerEvent(None)
        self.timer = self.startTimer(50)

    def _setup_plot(self):
        # Image setup
        self.fig = Figure()

        FigureCanvas.__init__(self, self.fig)

        # Create plot, set x and y axes
        ax = self.fig.add_subplot(111)
        ax.set_ylim(0, 100)

        # Build up timestamps
        base = datetime.datetime.now()
        date_ranges = [base - datetime.timedelta(seconds=x) for x in range(0,self.window_size)]

        for pin in range(5):
            sensor_values = [0] * self.window_size

            s_plot, = ax.plot(date_ranges,sensor_values, label="Analog {}".format(pin))

            # Add the ax and plot to our monitor
            self.sensor_readings[pin] = sensor_values
            plot_dict = {'plot': s_plot, 'ax': ax}
            self.sensor_plots[pin] = plot_dict

        # Show legend
        ax.legend()

        # Fix date formatting
        self.fig.autofmt_xdate();

        # Draw the initial canvas
        self.fig.canvas.draw()


    def _prepare_sensor_data(self):
        """Helper function to return serial sensor info"""
        sensor_value = self.serial_reader.next()
        print(sensor_value)
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

        for sensor, value in self.get_reading().items():
            if sensor == 'analog':
                for pin in range(5):
                    # Append new data to the datasets
                    self.sensor_readings[pin].append(value[pin])

                    # Scrolling horizontal axis is calculated - basically
                    # if our number of readings is abover the size, start scrolling.
                    # We add 15 so the right edge of line is not butting up against edge
                    # of graph but has some nice buffer space

                    num_readings = len(self.sensor_readings[pin])

                    # Build up timestamps
                    base = datetime.datetime.now()
                    date_ranges = [base - datetime.timedelta(seconds=x) for x in range(0,num_readings*5,5)]

                    # Update lines data using the lists with new data
                    plot_data = (range(num_readings),self.sensor_readings[pin])
                    self.sensor_plots[pin]['plot'].set_data(date_ranges,self.sensor_readings[pin])

        # Force a redraw of the Figure
        self.fig.canvas.draw()

        self.count += 1


# Build and run the actual appliation
app = QtGui.QApplication(sys.argv)
widget = ArduinoSerialMonitor()
widget.setWindowTitle("Serial Monitor")
widget.show()
sys.exit(app.exec_())