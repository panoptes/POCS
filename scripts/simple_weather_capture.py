import datetime
import os
import sys

from threading import Timer

from plotly import graph_objs as go
from plotly import plotly

sys.path.append(os.getenv('PEAS', '.'))  # Append the $PEAS dir

from peas import weather

header = "{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
    'date',
    'safe',
    'ambient_temp_C',
    'sky_temp_C',
    'rain_sensor_temp_C',
    'rain_frequency',
    'wind_speed_KPH',
    'ldr_resistance_Ohm',
    'pwm_value',
    'gust_condition',
    'wind_condition',
    'sky_condition',
    'rain_condition',
)

stream = None


def get_temp_plot(stream_token):
    trace0 = go.Scatter(x=[], y=[], name='MQ Observatory Temperature', mode='lines',
                        stream={'token': stream_token, 'maxpoints': 200}
                        )
    layout = go.Layout(
        xaxis={
            'title': 'Time'
        },
        yaxis={
            'title': 'Temp [C]'
        })

    fig = go.Figure(data=[trace0], layout=layout)

    url = plotly.plot(fig, filename='MQObs Weather - Temp')
    print("Plot available at {}".format(url))

    stream = plotly.Stream(stream_token)
    stream.open()


def write_header(filename):
    # Write out the header to the CSV file
    with open(filename, 'w') as f:
        f.write(header)


def read_capture(delay=30.0, continuous=True, plotly_stream=False, filename=None, **kwargs):
    """ A function that reads the AAG weather can calls itself on a timer """
    data = aag.capture()

    if plotly_stream:
        stream.write({'x': datetime.datetime.now(), 'y': data['ambient_temp_C']})

    entry = "{},{},{},{},{},{},{},{:0.5f},{:0.5f},{},{},{},{}\n".format(
        data['date'].strftime('%Y-%m-%d %H:%M:%S'),
        data['safe'],
        data['ambient_temp_C'],
        data['sky_temp_C'],
        data['rain_sensor_temp_C'],
        data['rain_frequency'],
        data['wind_speed_KPH'],
        data['ldr_resistance_Ohm'],
        data['pwm_value'],
        data['gust_condition'],
        data['wind_condition'],
        data['sky_condition'],
        data['rain_condition'],
    )

    if filename is not None:
        with open(filename, 'a') as f:
            f.write(entry)

    if continuous:
        Timer(delay, read_capture).start()


if __name__ == '__main__':
    import argparse

    # Weather object
    aag = weather.AAGCloudSensor(use_mongo=False)

    # Get the command line option
    parser = argparse.ArgumentParser(
        description="Make a plot of the weather for a give date.")

    parser.add_argument('--loop', action='store_true', default=True,
                        help="If should keep reading, defaults to True")
    parser.add_argument("-d", "--delay", dest="delay", default=30.0,
                        help="Interval to read weather")
    parser.add_argument("-f", "--filename", dest="filename", default='weather_info.csv',
                        help="Where to save results")
    parser.add_argument('--plotly_stream', help="Stream to plotly")
    parser.add_argument('--stream-token', help="Plotly stream token", default=None)
    args = parser.parse_args()

    if args.stream_token is not None:
        args.plotly_stream = True

    if args.plotly_stream:
        assert args.stream_token is not None
        get_temp_plot(args.stream_token)

    # Do the initial call
    read_capture(**vars(args))
