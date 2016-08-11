import os
import sys
sys.path.append(os.getenv('PEAS', '.'))  # Append the $PEAS dir

import argparse

from threading import Timer

from peas import weather

# Get the command line option
parser = argparse.ArgumentParser(
    description="Make a plot of the weather for a give date.")

parser.add_argument("-d", "--delay", type=float, dest="delay", default=30.0,
                    help="Interval to read weather")
parser.add_argument("-f", "--file", type=str, dest="filename", default='weather_info.csv',
                    help="Where to save results")
args = parser.parse_args()

# Weather object
aag = weather.AAGCloudSensor()

# Write out the header to the CSV file
header = "{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
    'Date',
    'Safe',
    'Ambient Temp C',
    'Sky Temp C',
    'Rain Sensor Temp C',
    'Rain Frequency',
    'Wind Speed Kph',
    'Ldr Resistance Ohm',
    'Gust Condition',
    'Wind Condition',
    'Sky Condition',
    'Rain Condition',
)
with open(args.filename, 'w') as f:
    f.write(header)


def read_capture():
    """ A function that reads the AAG weather can calls itself on a timer """
    data = aag.capture()

    entry = "{},{},{},{},{},{},{},{:0.5f},{},{},{},{}\n".format(
        data['date'],
        data['safe'],
        data['ambient_temp_C'],
        data['sky_temp_C'],
        data['rain_sensor_temp_C'],
        data['rain_frequency'],
        data['wind_speed_KPH'],
        data['ldr_resistance_Ohm'],
        data['gust_condition'],
        data['wind_condition'],
        data['sky_condition'],
        data['rain_condition'],
    )

    with open(args.filename, 'a') as f:
        f.write(entry)

    Timer(args.delay, read_capture).start()

# Do the initial call
read_capture()
