#!/usr/bin/env python3

import os
from datetime import datetime as dt
from datetime import timedelta as tdelta
import numpy as np

from astropy.time import Time

from astropy.coordinates import EarthLocation
from astroplan import Observer

import pymongo

from panoptes.utils.database import PanMongo
from panoptes.utils.config import load_config


def plot_weather(date_string):
    print("Plotting weather")
    import matplotlib as mpl
    mpl.use('Agg')
    from matplotlib import pyplot as plt
    from matplotlib.dates import HourLocator, MinuteLocator, DateFormatter
    plt.ioff()

    dpi = 100
    plt.figure(figsize=(16, 9), dpi=dpi)

    hours = HourLocator(byhour=range(24), interval=1)
    hours_fmt = DateFormatter('%H')
    mins = MinuteLocator(range(0, 60, 15))
    mins_fmt = DateFormatter('%H:%M')

    if not date_string:
        today = True
        date = dt.utcnow()
        date_string = date.strftime('%Y%m%dUT')
    else:
        today = False
        date = dt.strptime('{} 23:59:59'.format(date_string), '%Y%m%dUT %H:%M:%S')

    start = dt(date.year, date.month, date.day, 0, 0, 0, 0)
    end = dt(date.year, date.month, date.day, 23, 59, 59, 0)

    # ------------------------------------------------------------------------
    # determine sunrise and sunset times
    # ------------------------------------------------------------------------
    cfg = load_config()['location']
    loc = EarthLocation(
        lat=cfg['latitude'],
        lon=cfg['longitude'],
        height=cfg['elevation'],
    )
    obs = Observer(location=loc, name='PANOPTES', timezone=cfg['timezone'])

    sunset = obs.sun_set_time(Time(start), which='next').datetime
    evening_civil_twilight = obs.twilight_evening_civil(Time(start), which='next').datetime
    evening_nautical_twilight = obs.twilight_evening_nautical(Time(start), which='next').datetime
    evening_astronomical_twilight = obs.twilight_evening_astronomical(Time(start), which='next').datetime
    morning_astronomical_twilight = obs.twilight_morning_astronomical(Time(start), which='next').datetime
    morning_nautical_twilight = obs.twilight_morning_nautical(Time(start), which='next').datetime
    morning_civil_twilight = obs.twilight_morning_civil(Time(start), which='next').datetime
    sunrise = obs.sun_rise_time(Time(start), which='next').datetime

    print('start:                         {}'.format(Time(start)))
    print(obs.is_night(Time(start)))
    print('sunset:                        {}'.format(sunset))
    print('evening_civil_twilight:        {}'.format(evening_civil_twilight))
    print('evening_nautical_twilight:     {}'.format(evening_nautical_twilight))
    print('evening_astronomical_twilight: {}'.format(evening_astronomical_twilight))
    print('morning_astronomical_twilight: {}'.format(morning_astronomical_twilight))
    print('morning_nautical_twilight:     {}'.format(morning_nautical_twilight))
    print('morning_civil_twilight:        {}'.format(morning_civil_twilight))

    # -------------------------------------------------------------------------
    # Plot a day's weather
    # -------------------------------------------------------------------------
    plot_positions = [([0.000, 0.835, 0.700, 0.170], [0.720, 0.835, 0.280, 0.170]),
                      ([0.000, 0.635, 0.700, 0.170], [0.720, 0.635, 0.280, 0.170]),
                      ([0.000, 0.450, 0.700, 0.170], [0.720, 0.450, 0.280, 0.170]),
                      ([0.000, 0.265, 0.700, 0.170], [0.720, 0.265, 0.280, 0.170]),
                      ([0.000, 0.185, 0.700, 0.065], [0.720, 0.185, 0.280, 0.065]),
                      ([0.000, 0.000, 0.700, 0.170], [0.720, 0.000, 0.280, 0.170]),
                      ]

    # Connect to sensors collection
    db = PanMongo()
    entries = [x for x in db.weather.find({'date': {'$gt': start, '$lt': end}}).sort([('date', pymongo.ASCENDING)])]
    if today:
        current_values = [x for x in db.current.find({"type": "weather"})][0]
    else:
        current_values = None

    print('Plot Ambient Temperature vs. Time')
    # -------------------------------------------------------------------------
    # Plot Ambient Temperature vs. Time
    t_axes = plt.axes(plot_positions[0][0])
    if today:
        time_title = date
    else:
        time_title = end
    plt.title('Weather for {} at {}'.format(date_string, time_title.strftime('%H:%M:%S UT')))
    amb_temp = [x['data']['ambient_temp_C']
                for x in entries
                if 'ambient_temp_C' in x['data'].keys()]
    time = [x['date'] for x in entries
            if 'ambient_temp_C' in x['data'].keys()]
    t_axes.plot_date(time, amb_temp, 'ko',
                     markersize=2, markeredgewidth=0,
                     drawstyle="default")
    try:
        max_temp = max(amb_temp)
        min_temp = min(amb_temp)
        label_time = end - tdelta(0, 7 * 60 * 60)
        label_temp = 28
        t_axes.annotate('Low: {:4.1f} $^\circ$C, High: {:4.1f} $^\circ$C'.format(
                        min_temp, max_temp),
                        xy=(label_time, max_temp),
                        xytext=(label_time, label_temp),
                        size=16,
                        )
    except:
        pass
    plt.ylabel("Ambient Temp. (C)")
    plt.grid(which='major', color='k')
    plt.yticks(range(-100, 100, 10))
    plt.xlim(start, end)
    plt.ylim(-5, 35)
    t_axes.xaxis.set_major_locator(hours)
    t_axes.xaxis.set_major_formatter(hours_fmt)

    if obs.is_night(Time(start)):
        plt.axvspan(start, morning_astronomical_twilight, ymin=0, ymax=1, color='blue', alpha=0.5)
        plt.axvspan(morning_astronomical_twilight, morning_nautical_twilight, ymin=0, ymax=1, color='blue', alpha=0.3)
        plt.axvspan(morning_nautical_twilight, morning_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
        plt.axvspan(morning_civil_twilight, sunrise, ymin=0, ymax=1, color='blue', alpha=0.1)
        plt.axvspan(sunset, evening_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.1)
        plt.axvspan(evening_civil_twilight, evening_nautical_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
        plt.axvspan(evening_nautical_twilight, evening_astronomical_twilight, ymin=0, ymax=1, color='blue', alpha=0.3)
        plt.axvspan(evening_astronomical_twilight, end, ymin=0, ymax=1, color='blue', alpha=0.5)
    else:
        plt.axvspan(sunset, evening_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.1)
        plt.axvspan(evening_civil_twilight, evening_nautical_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
        plt.axvspan(evening_nautical_twilight, evening_astronomical_twilight, ymin=0, ymax=1, color='blue', alpha=0.3)
        plt.axvspan(evening_astronomical_twilight, morning_astronomical_twilight,
                    ymin=0, ymax=1, color='blue', alpha=0.5)
        plt.axvspan(morning_astronomical_twilight, morning_nautical_twilight, ymin=0, ymax=1, color='blue', alpha=0.3)
        plt.axvspan(morning_nautical_twilight, morning_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
        plt.axvspan(morning_civil_twilight, sunrise, ymin=0, ymax=1, color='blue', alpha=0.1)

    tlh_axes = plt.axes(plot_positions[0][1])
    plt.title('Last Hour')
    tlh_axes.plot_date(time, amb_temp, 'ko',
                       markersize=4, markeredgewidth=0,
                       drawstyle="default")
    try:
        current_amb_temp = current_values['data']['ambient_temp_C']
        current_time = current_values['date']
        label_time = current_time - tdelta(0, 30 * 60)
        label_temp = 28  # current_amb_temp + 7
        tlh_axes.annotate('Currently: {:.1f} $^\circ$C'.format(current_amb_temp),
                          xy=(current_time, current_amb_temp),
                          xytext=(label_time, label_temp),
                          size=16,
                          )
    except:
        pass
    plt.grid(which='major', color='k')
    plt.yticks(range(-100, 100, 10))
    tlh_axes.xaxis.set_major_locator(mins)
    tlh_axes.xaxis.set_major_formatter(mins_fmt)
    tlh_axes.yaxis.set_ticklabels([])
    plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
    plt.ylim(-5, 35)

    print('Plot Temperature Difference vs. Time')
    # -------------------------------------------------------------------------
    # Plot Temperature Difference vs. Time
    td_axes = plt.axes(plot_positions[1][0])
    required_cols = ('sky_temp_C' and 'sky_condition' and 'ambient_temp_C')

    temp_diff = [x['data']['sky_temp_C'] - x['data']['ambient_temp_C']
                 for x in entries if required_cols in x['data'].keys()]
    time = [x['date'] for x in entries if required_cols in x['data'].keys()]
    sky_condition = [x['data']['sky_condition'] for x in entries if required_cols in x['data'].keys()]

    td_axes.plot_date(time, temp_diff, 'ko-', label='Cloudiness',
                      markersize=2, markeredgewidth=0,
                      drawstyle="default")
    td_axes.fill_between(time, -60, temp_diff, where=np.array(sky_condition) == 'Clear', color='green', alpha=0.5)
    td_axes.fill_between(time, -60, temp_diff, where=np.array(sky_condition) == 'Cloudy', color='yellow', alpha=0.5)
    td_axes.fill_between(time, -60, temp_diff, where=np.array(sky_condition) == 'Very Cloudy', color='red', alpha=0.5)
    plt.ylabel("Cloudiness")
    plt.grid(which='major', color='k')
    plt.yticks(range(-100, 100, 10))
    plt.xlim(start, end)
    plt.ylim(-60, 10)
    td_axes.xaxis.set_major_locator(hours)
    td_axes.xaxis.set_major_formatter(hours_fmt)
    td_axes.xaxis.set_ticklabels([])

    tdlh_axes = plt.axes(plot_positions[1][1])
    tdlh_axes.plot_date(time, temp_diff, 'ko-', label='Cloudiness',
                        markersize=4, markeredgewidth=0,
                        drawstyle="default")
    tdlh_axes.fill_between(time, -60, temp_diff, where=np.array(sky_condition) == 'Clear', color='green', alpha=0.5)
    tdlh_axes.fill_between(time, -60, temp_diff, where=np.array(sky_condition) == 'Cloudy', color='yellow', alpha=0.5)
    tdlh_axes.fill_between(time, -60, temp_diff, where=np.array(sky_condition)
                           == 'Very Cloudy', color='red', alpha=0.5)
    plt.grid(which='major', color='k')
    plt.yticks(range(-100, 100, 10))
    plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
    plt.ylim(-60, 10)
    tdlh_axes.xaxis.set_major_locator(mins)
    tdlh_axes.xaxis.set_major_formatter(mins_fmt)
    tdlh_axes.xaxis.set_ticklabels([])
    tdlh_axes.yaxis.set_ticklabels([])

    print('Plot Wind Speed vs. Time')
    # -------------------------------------------------------------------------
    # Plot Wind Speed vs. Time
    trans = {'Calm': 0, 'Windy': 1, 'Gusty': 1, 'Very Windy': 10, 'Very Gusty': 10, 'Unknown': 0}

    w_axes = plt.axes(plot_positions[2][0])
    required_cols = ('wind_speed_KPH' and 'wind_condition' and 'gust_condition')

    wind_speed = [x['data']['wind_speed_KPH'] for x in entries if required_cols in x['data'].keys()]

    wind_mavg = moving_average(wind_speed, 10)

    wind_condition = [trans[x['data']['wind_condition']] + trans[x['data']['gust_condition']]
                      for x in entries if required_cols in x['data'].keys()]

    time = [x['date'] for x in entries if required_cols in x['data'].keys()]

    w_axes.plot_date(time, wind_speed, 'ko', alpha=0.5,
                     markersize=2, markeredgewidth=0,
                     drawstyle="default")
    w_axes.plot_date(time, wind_mavg, 'b-',
                     label='Wind Speed',
                     markersize=3, markeredgewidth=0,
                     linewidth=3, alpha=0.5,
                     drawstyle="default")
    w_axes.plot_date([start, end], [0, 0], 'k-', ms=1)
    w_axes.fill_between(time, -5, wind_speed,
                        where=np.array(wind_condition) == 0,
                        color='green', alpha=0.5)
    w_axes.fill_between(time, -5, wind_speed,
                        where=(np.array(wind_condition) > 0) & (np.array(wind_condition) < 10),
                        color='yellow', alpha=0.5)
    w_axes.fill_between(time, -5, wind_speed,
                        where=np.array(wind_condition) > 10,
                        color='red', alpha=0.5)
    try:
        max_wind = max(wind_speed)
        label_time = end - tdelta(0, 6 * 60 * 60)
        label_wind = 61
        w_axes.annotate('Max Gust: {:.1f} (km/h)'.format(max_wind),
                        xy=(label_time, max_wind),
                        xytext=(label_time, label_wind),
                        size=16,
                        )
    except:
        pass
    plt.ylabel("Wind (km/h)")
    plt.grid(which='major', color='k')
    plt.yticks(range(-100, 100, 10))
    plt.xlim(start, end)
    wind_max = max([45, np.ceil(max(wind_speed) / 5.) * 5.])
    plt.ylim(0, 75)
    w_axes.xaxis.set_major_locator(hours)
    w_axes.xaxis.set_major_formatter(hours_fmt)
    w_axes.xaxis.set_ticklabels([])

    wlh_axes = plt.axes(plot_positions[2][1])
    wlh_axes.plot_date(time, wind_speed, 'ko', alpha=0.7,
                       markersize=4, markeredgewidth=0,
                       drawstyle="default")
    wlh_axes.plot_date(time, wind_mavg, 'b-',
                       label='Wind Speed',
                       markersize=2, markeredgewidth=0,
                       linewidth=3, alpha=0.5,
                       drawstyle="default")
    wlh_axes.plot_date([start, end], [0, 0], 'k-', ms=1)
    wlh_axes.fill_between(time, -5, wind_speed,
                          where=np.array(wind_condition) == 0,
                          color='green', alpha=0.5)
    wlh_axes.fill_between(time, -5, wind_speed,
                          where=(np.array(wind_condition) > 0) & (np.array(wind_condition) < 10),
                          color='yellow', alpha=0.5)
    wlh_axes.fill_between(time, -5, wind_speed,
                          where=np.array(wind_condition) > 10,
                          color='red', alpha=0.5)
    try:
        current_wind = current_values['data']['wind_speed_KPH']
        current_time = current_values['date']
        label_time = current_time - tdelta(0, 30 * 60)
        label_wind = 61
        wlh_axes.annotate('Currently: {:.0f} km/h'.format(current_wind),
                          xy=(current_time, current_wind),
                          xytext=(label_time, label_wind),
                          size=16,
                          )
    except:
        pass
    plt.grid(which='major', color='k')
    plt.yticks(range(-100, 100, 10))
    plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
    wind_max = max([45, np.ceil(max(wind_speed) / 5.) * 5.])
    plt.ylim(0, 75)
    wlh_axes.xaxis.set_major_locator(mins)
    wlh_axes.xaxis.set_major_formatter(mins_fmt)
    wlh_axes.xaxis.set_ticklabels([])
    wlh_axes.yaxis.set_ticklabels([])

    print('Plot Rain Frequency vs. Time')
    # -------------------------------------------------------------------------
    # Plot Rain Frequency vs. Time
    required_cols = ('rain_frequency' and 'rain_condition')

    rf_axes = plt.axes(plot_positions[3][0])
    rf_value = [x['data']['rain_frequency'] for x in entries if required_cols in x['data'].keys()]
    rain_condition = [x['data']['rain_condition'] for x in entries if required_cols in x['data'].keys()]
    time = [x['date'] for x in entries if required_cols in x['data'].keys()]

    rf_axes.plot_date(time, rf_value, 'ko-', label='Rain',
                      markersize=2, markeredgewidth=0,
                      drawstyle="default")

    rf_axes.fill_between(time, 0, rf_value, where=np.array(rain_condition) == 'Dry', color='green', alpha=0.5)
    rf_axes.fill_between(time, 0, rf_value, where=np.array(rain_condition) == 'Rain', color='red', alpha=0.5)

    plt.ylabel("Rain Sensor")
    plt.grid(which='major', color='k')
    plt.ylim(120, 275)
    plt.xlim(start, end)
    rf_axes.xaxis.set_major_locator(hours)
    rf_axes.xaxis.set_major_formatter(hours_fmt)
    rf_axes.xaxis.set_ticklabels([])
    rf_axes.yaxis.set_ticklabels([])

    rflh_axes = plt.axes(plot_positions[3][1])
    rflh_axes.plot_date(time, rf_value, 'ko-', label='Rain',
                        markersize=4, markeredgewidth=0,
                        drawstyle="default")
    rflh_axes.fill_between(time, 0, rf_value, where=np.array(rain_condition) == 'Dry',
                           color='green', alpha=0.5)
    rflh_axes.fill_between(time, 0, rf_value, where=np.array(rain_condition) == 'Rain',
                           color='red', alpha=0.5)
    plt.grid(which='major', color='k')
    plt.ylim(120, 275)
    plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
    rflh_axes.xaxis.set_major_locator(mins)
    rflh_axes.xaxis.set_major_formatter(mins_fmt)
    rflh_axes.xaxis.set_ticklabels([])
    rflh_axes.yaxis.set_ticklabels([])

    print('Plot Safe/Unsafe vs. Time')
    # -------------------------------------------------------------------------
    # Safe/Unsafe vs. Time
    safe_axes = plt.axes(plot_positions[4][0])
    safe_value = [int(x['data']['safe']) for x in entries if 'safe' in x['data'].keys()]
    safe_time = [x['date'] for x in entries if 'safe' in x['data'].keys()]

    safe_axes.plot_date(safe_time, safe_value, 'ko',
                        markersize=2, markeredgewidth=0,
                        drawstyle="default")
    safe_axes.fill_between(safe_time, -1, safe_value, where=np.array(safe_value) == 1,
                           color='green', alpha=0.5)
    safe_axes.fill_between(safe_time, -1, safe_value, where=np.array(safe_value) == 0,
                           color='red', alpha=0.5)
    plt.ylabel("Safe")
    plt.xlim(start, end)
    plt.ylim(-0.1, 1.1)
    plt.yticks([0, 1])
    plt.grid(which='major', color='k')
    safe_axes.xaxis.set_major_locator(hours)
    safe_axes.xaxis.set_major_formatter(hours_fmt)
    safe_axes.xaxis.set_ticklabels([])
    safe_axes.yaxis.set_ticklabels([])

    safelh_axes = plt.axes(plot_positions[4][1])
    safelh_axes.plot_date(safe_time, safe_value, 'ko-',
                          markersize=4, markeredgewidth=0,
                          drawstyle="default")
    safelh_axes.fill_between(safe_time, -1, safe_value, where=np.array(safe_value) == 1,
                             color='green', alpha=0.5)
    safelh_axes.fill_between(safe_time, -1, safe_value, where=np.array(safe_value) == 0,
                             color='red', alpha=0.5)
    plt.ylim(-0.1, 1.1)
    plt.yticks([0, 1])
    plt.grid(which='major', color='k')
    plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
    safelh_axes.xaxis.set_major_locator(mins)
    safelh_axes.xaxis.set_major_formatter(mins_fmt)
    safelh_axes.xaxis.set_ticklabels([])
    safelh_axes.yaxis.set_ticklabels([])

    print('Plot PWM Value vs. Time')
    # -------------------------------------------------------------------------
    # Plot PWM Value vs. Time
    required_cols = ('pwm_value' and 'rain_sensor_temp_C' and 'ambient_temp_C')

    pwm_axes = plt.axes(plot_positions[5][0])
    plt.ylabel("Heater (%)")
    plt.ylim(-5, 105)
    plt.yticks([0, 25, 50, 75, 100])
    plt.xlim(start, end)
    plt.grid(which='major', color='k')
    rst_axes = pwm_axes.twinx()
    plt.ylim(-1, 21)
    plt.xlim(start, end)

    pwm_value = [x['data']['pwm_value'] for x in entries if required_cols in x['data'].keys()]
    rst_delta = [x['data']['rain_sensor_temp_C'] - x['data']['ambient_temp_C']
                 for x in entries if required_cols in x['data'].keys()]
    time = [x['date'] for x in entries if required_cols in x['data'].keys()]

    rst_axes.plot_date(time, rst_delta, 'ro-', alpha=0.5,
                       label='RST Delta (C)',
                       markersize=2, markeredgewidth=0,
                       drawstyle="default")
    pwm_axes.plot_date(time, pwm_value, 'bo', label='Heater',
                       markersize=2, markeredgewidth=0,
                       drawstyle="default")
    pwm_axes.xaxis.set_major_locator(hours)
    pwm_axes.xaxis.set_major_formatter(hours_fmt)

    pwmlh_axes = plt.axes(plot_positions[5][1])
    plt.ylim(-5, 105)
    plt.yticks([0, 25, 50, 75, 100])
    plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
    plt.grid(which='major', color='k')
    rstlh_axes = pwmlh_axes.twinx()
    plt.ylim(-1, 21)
    plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
    rstlh_axes.plot_date(time, rst_delta, 'ro-', alpha=0.5,
                         label='RST Delta (C)',
                         markersize=4, markeredgewidth=0,
                         drawstyle="default")
    rstlh_axes.xaxis.set_ticklabels([])
    rstlh_axes.yaxis.set_ticklabels([])
    pwmlh_axes.plot_date(time, pwm_value, 'bo', label='Heater',
                         markersize=4, markeredgewidth=0,
                         drawstyle="default")
    pwmlh_axes.xaxis.set_major_locator(mins)
    pwmlh_axes.xaxis.set_major_formatter(mins_fmt)
    pwmlh_axes.yaxis.set_ticklabels([])

    plot_filename = '{}.png'.format(date_string)
    plot_file = os.path.expanduser('/var/panoptes/weather_plots/{}'.format(plot_filename))
    print('Save Figure: {}'.format(plot_file))
    plt.savefig(plot_file, dpi=dpi, bbox_inches='tight', pad_inches=0.10)
    # Link
    today_name = '/var/panoptes/weather_plots/today.png'
    if os.path.exists(today_name):
        os.remove(today_name)

    os.symlink(plot_file, today_name)


def moving_average(interval, window_size):
    """ A simple moving average function """
    window = np.ones(int(window_size)) / float(window_size)
    return np.convolve(interval, window, 'same')

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Make a plot of the weather for a give date.")

    parser.add_argument("-d", "--date", type=str, dest="date", default=None, help="UT Date to plot")
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Be verbose.")

    args = parser.parse_args()

    plot_weather(args.date)
