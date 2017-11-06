import datetime
import pandas
import time

from plotly import graph_objs as plotly_go
from plotly import plotly
from plotly import tools as plotly_tools

from peas import weather

names = [
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
]

header = ','.join(names)


def get_plot(filename=None):
    stream_tokens = plotly_tools.get_credentials_file()['stream_ids']
    token_1 = stream_tokens[0]
    token_2 = stream_tokens[1]
    token_3 = stream_tokens[2]
    stream_id1 = dict(token=token_1, maxpoints=1500)
    stream_id2 = dict(token=token_2, maxpoints=1500)
    stream_id3 = dict(token=token_3, maxpoints=1500)

    # Get existing data
    x_data = {
        'time': [],
    }
    y_data = {
        'temp': [],
        'cloudiness': [],
        'rain': [],
    }

    if filename is not None:
        data = pandas.read_csv(filename, names=names)
        data.date = pandas.to_datetime(data.date)
        # Convert from UTC
        data.date = data.date + datetime.timedelta(hours=11)
        x_data['time'] = data.date
        y_data['temp'] = data.ambient_temp_C
        y_data['cloudiness'] = data.sky_temp_C
        y_data['rain'] = data.rain_frequency

    trace1 = plotly_go.Scatter(
        x=x_data['time'], y=y_data['temp'], name='Temperature', mode='lines', stream=stream_id1)
    trace2 = plotly_go.Scatter(
        x=x_data['time'], y=y_data['cloudiness'], name='Cloudiness', mode='lines', stream=stream_id2)
    trace3 = plotly_go.Scatter(
        x=x_data['time'], y=y_data['rain'], name='Rain', mode='lines', stream=stream_id3)

    fig = plotly_tools.make_subplots(rows=3, cols=1, shared_xaxes=True, shared_yaxes=False)
    fig.append_trace(trace1, 1, 1)
    fig.append_trace(trace2, 2, 1)
    fig.append_trace(trace3, 3, 1)

    fig['layout'].update(title="MQ Observatory Weather")

    fig['layout']['xaxis1'].update(title="Time [AEDT]")

    fig['layout']['yaxis1'].update(title="Temp [C]")
    fig['layout']['yaxis2'].update(title="Cloudiness")
    fig['layout']['yaxis3'].update(title="Rain Sensor")

    url = plotly.plot(fig, filename='MQObs Weather - Temp')
    print("Plot available at {}".format(url))

    stream_temp = plotly.Stream(stream_id=token_1)
    stream_temp.open()

    stream_cloudiness = plotly.Stream(stream_id=token_2)
    stream_cloudiness.open()

    stream_rain = plotly.Stream(stream_id=token_3)
    stream_rain.open()

    streams = {
        'temp': stream_temp,
        'cloudiness': stream_cloudiness,
        'rain': stream_rain,
    }

    return streams


def write_header(filename):
    # Write out the header to the CSV file
    with open(filename, 'w') as f:
        f.write(header)


def write_capture(filename=None, data=None):
    """ A function that reads the AAG weather can calls itself on a timer """
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


if __name__ == '__main__':
    import argparse

    # Get the command line option
    parser = argparse.ArgumentParser(
        description="Make a plot of the weather for a give date.")

    parser.add_argument('--loop', action='store_true', default=True,
                        help="If should keep reading, defaults to True")
    parser.add_argument("-d", "--delay", dest="delay", default=30.0, type=float,
                        help="Interval to read weather")
    parser.add_argument("-f", "--filename", dest="filename", default=None,
                        help="Where to save results")
    parser.add_argument('--serial-port', dest='serial_port', default=None,
                        help='Serial port to connect')
    parser.add_argument('--plotly-stream', action='store_true', default=False, help="Stream to plotly")
    parser.add_argument('--store-mongo', action='store_true', default=True, help="Save to mongo")
    parser.add_argument('--send-message', action='store_true', default=True, help="Send message")
    args = parser.parse_args()

    # Weather object
    aag = weather.AAGCloudSensor(serial_address=args.serial_port, use_mongo=args.store_mongo)

    if args.plotly_stream:
        streams = None
        streams = get_plot(filename=args.filename)

    while True:
        data = aag.capture(use_mongo=args.store_mongo, send_message=args.send_message)

        # Save to file
        if args.filename is not None:
            write_capture(filename=args.filename, data=data)

        if args.plotly_stream:
            now = datetime.datetime.now()
            streams['temp'].write({'x': now, 'y': data['ambient_temp_C']})
            streams['cloudiness'].write({'x': now, 'y': data['sky_temp_C']})
            streams['rain'].write({'x': now, 'y': data['rain_frequency']})

        if not args.loop:
            break

        time.sleep(args.delay)
