import argparse

from threading import Timer

from peas import weather

# Get the command line option
parser = argparse.ArgumentParser(
    description="Make a plot of the weather for a give date.")

parser.add_argument("-d", "--delay", type=float, dest="delay", default=30.0,
                    help="Interval to read weather")
parser.add_argument("-f", "--file", type=str, dest="filename", default='weather_info.txt',
                    help="Where to save results")
args = parser.parse_args()

# Weather object
aag = weather.AAGCloudSensor()


def read_capture():
    d = aag.capture()

    with open(args.filename, 'w') as f:
        f.write(d)

    Timer(args.delay, read_capture)
