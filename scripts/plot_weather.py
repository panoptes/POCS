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

import matplotlib as mpl
mpl.use('Agg')
from matplotlib import pyplot as plt
from matplotlib.dates import HourLocator, MinuteLocator, DateFormatter
plt.ioff()


class WeatherPlotter(object):
    """ Plot weather information for a given time span """

    def __init__(self, date_string=None, *args, **kwargs):
        super(WeatherPlotter, self).__init__()
        self.args = args
        self.kwargs = kwargs

        self.today = False

        if not date_string:
            self.today = True
            self.date = dt.utcnow()
            self.date_string = self.date.strftime('%Y%m%dUT')
        else:
            self.date = dt.strptime('{} 23:59:59'.format(date_string), '%Y%m%dUT %H:%M:%S')
            self.date_string = date_string

        self.start = dt(self.date.year, self.date.month, self.date.day, 0, 0, 0, 0)
        self.end = dt(self.date.year, self.date.month, self.date.day, 23, 59, 59, 0)

        dpi = kwargs.get('dpi', 100)
        self.self.plt.figure(figsize=(16, 9), dpi=dpi)

        self.hours = HourLocator(byhour=range(24), interval=1)
        self.hours_fmt = DateFormatter('%H')
        self.mins = MinuteLocator(range(0, 60, 15))
        self.mins_fmt = DateFormatter('%H:%M')

        # ------------------------------------------------------------------------
        # determine sunrise and sunset times
        # ------------------------------------------------------------------------
        self.cfg = load_config()['location']
        self.loc = EarthLocation(
            lat=self.cfg['latitude'],
            lon=self.cfg['longitude'],
            height=self.self.cfg['elevation'],
        )
        self.obs = Observer(location=self.loc, name='PANOPTES', timezone=self.cfg['timezone'])

        self.sunset = self.obs.sun_set_time(Time(self.start), which='next').datetime
        self.evening_civil_twilight = self.obs.twilight_evening_civil(Time(self.start), which='next').datetime
        self.evening_nautical_twilight = self.obs.twilight_evening_nautical(Time(self.start), which='next').datetime
        self.evening_astronomical_twilight = self.obs.twilight_evening_astronomical(Time(self.start), which='next').datetime
        self.morning_astronomical_twilight = self.obs.twilight_morning_astronomical(Time(self.start), which='next').datetime
        self.morning_nautical_twilight = self.obs.twilight_morning_nautical(Time(self.start), which='next').datetime
        self.morning_civil_twilight = self.obs.twilight_morning_civil(Time(self.start), which='next').datetime
        self.sunrise = self.obs.sun_rise_time(Time(self.start), which='next').datetime

        print('start:                         {}'.format(Time(self.start)))
        print(self.obs.is_night(Time(self.start)))
        print('self.sunset:                        {}'.format(self.sunset))
        print('self.evening_civil_twilight:        {}'.format(self.evening_civil_twilight))
        print('self.evening_nautical_twilight:     {}'.format(self.evening_nautical_twilight))
        print('self.evening_astronomical_twilight: {}'.format(self.evening_astronomical_twilight))
        print('self.morning_astronomical_twilight: {}'.format(self.morning_astronomical_twilight))
        print('self.morning_nautical_twilight:     {}'.format(self.morning_nautical_twilight))
        print('self.morning_civil_twilight:        {}'.format(self.morning_civil_twilight))

        # -------------------------------------------------------------------------
        # Plot a day's weather
        # -------------------------------------------------------------------------
        # What is this doing? --wtgee
        self.plot_positions = [([0.000, 0.835, 0.700, 0.170], [0.720, 0.835, 0.280, 0.170]),
                               ([0.000, 0.635, 0.700, 0.170], [0.720, 0.635, 0.280, 0.170]),
                               ([0.000, 0.450, 0.700, 0.170], [0.720, 0.450, 0.280, 0.170]),
                               ([0.000, 0.265, 0.700, 0.170], [0.720, 0.265, 0.280, 0.170]),
                               ([0.000, 0.185, 0.700, 0.065], [0.720, 0.185, 0.280, 0.065]),
                               ([0.000, 0.000, 0.700, 0.170], [0.720, 0.000, 0.280, 0.170]),
                               ]

        # Connect to sensors collection
        self.db = PanMongo()
        self.entries = [x for x in self.db.weather.find({'date': {'$gt': self.start, '$lt': self.end}}).sort([
            ('date', pymongo.ASCENDING)])]

        if self.today:
            self.current_values = [x for x in self.db.current.find({"type": "weather"})][0]
        else:
            self.current_values = None

        self.get_ambient_vs_time()
        self.get_temp_vs_time()

        self.save_plot()

    def get_field_data(self, field_name):
        """ Return an array for given field from entries """
        data = [x['data'][field_name] for x in self.entries if field_name in x['data'].keys()]
        time = [x['date'] for x in self.entries if field_name in x['data'].keys()]

        return (time, data)

    def get_ambient_vs_time(self):
        print('Plot Ambient Temperature vs. Time')
        # -------------------------------------------------------------------------
        # Plot Ambient Temperature vs. Time
        t_axes = self.plt.axes(self.plot_positions[0][0])
        if self.today:
            time_title = self.date
        else:
            time_title = self.end

        self.plt.title('Weather for {} at {}'.format(self.date_string, time_title.strftime('%H:%M:%S UT')))

        time, amb_temp = self.get_field_data('ambient_temp_C')

        t_axes.plot_date(time, amb_temp, 'ko', markersize=2, markeredgewidth=0, drawstyle="default")

        try:
            max_temp = max(amb_temp)
            min_temp = min(amb_temp)
            label_time = self.end - tdelta(0, 7 * 60 * 60)
            label_temp = 28
            t_axes.annotate('Low: {:4.1f} $^\circ$C, High: {:4.1f} $^\circ$C'.format(
                            min_temp, max_temp),
                            xy=(label_time, max_temp),
                            xytext=(label_time, label_temp),
                            size=16,
                            )
        except:
            pass

        self.plt.ylabel("Ambient Temp. (C)")
        self.plt.grid(which='major', color='k')
        self.plt.yticks(range(-100, 100, 10))
        self.plt.xlim(self.start, self.end)
        self.plt.ylim(-5, 35)
        t_axes.xaxis.set_major_locator(self.hours)
        t_axes.xaxis.set_major_formatter(self.hours_fmt)

        if self.obs.is_night(Time(self.start)):
            self.plt.axvspan(self.start, self.morning_astronomical_twilight, ymin=0, ymax=1, color='blue', alpha=0.5)
            self.plt.axvspan(self.morning_astronomical_twilight, self.morning_nautical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.3)
            self.plt.axvspan(self.morning_nautical_twilight, self.morning_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
            self.plt.axvspan(self.morning_civil_twilight, self.sunrise, ymin=0, ymax=1, color='blue', alpha=0.1)
            self.plt.axvspan(self.sunset, self.evening_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.1)
            self.plt.axvspan(self.evening_civil_twilight, self.evening_nautical_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
            self.plt.axvspan(self.evening_nautical_twilight, self.evening_astronomical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.3)
            self.plt.axvspan(self.evening_astronomical_twilight, self.end, ymin=0, ymax=1, color='blue', alpha=0.5)
        else:
            self.plt.axvspan(self.sunset, self.evening_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.1)
            self.plt.axvspan(self.evening_civil_twilight, self.evening_nautical_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
            self.plt.axvspan(self.evening_nautical_twilight, self.evening_astronomical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.3)
            self.plt.axvspan(self.evening_astronomical_twilight, self.morning_astronomical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.5)
            self.plt.axvspan(self.morning_astronomical_twilight, self.morning_nautical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.3)
            self.plt.axvspan(self.morning_nautical_twilight, self.morning_civil_twilight, ymin=0, ymax=1, color='blue', alpha=0.2)
            self.plt.axvspan(self.morning_civil_twilight, self.sunrise, ymin=0, ymax=1, color='blue', alpha=0.1)

        tlh_axes = self.plt.axes(self.plot_positions[0][1])
        self.plt.title('Last Hour')
        tlh_axes.plot_date(time, amb_temp, 'ko',
                           markersize=4, markeredgewidth=0,
                           drawstyle="default")
        try:
            current_amb_temp = self.current_values['data']['ambient_temp_C']
            current_time = self.current_values['date']
            label_time = current_time - tdelta(0, 30 * 60)
            label_temp = 28  # current_amb_temp + 7
            tlh_axes.annotate('Currently: {:.1f} $^\circ$C'.format(current_amb_temp),
                              xy=(current_time, current_amb_temp),
                              xytext=(label_time, label_temp),
                              size=16,
                              )
        except:
            pass

        self.plt.grid(which='major', color='k')
        self.plt.yticks(range(-100, 100, 10))
        tlh_axes.xaxis.set_major_locator(self.mins)
        tlh_axes.xaxis.set_major_formatter(self.mins_fmt)
        tlh_axes.yaxis.set_ticklabels([])
        self.plt.xlim(self.date - tdelta(0, 60 * 60), self.date + tdelta(0, 5 * 60))
        self.plt.ylim(-5, 35)

    def get_temp_vs_time(self):
        print('Plot Temperature Difference vs. Time')
        # -------------------------------------------------------------------------
        # Plot Temperature Difference vs. Time
        td_axes = self.plt.axes(self.plot_positions[1][0])
        required_cols = ('sky_temp_C' and 'sky_condition' and 'ambient_temp_C')

        sky_time, sky_temp_C = self.get_field_data('sky_temp_C')
        ambient_time, ambient_temp_C = self.get_field_data('ambient_temp_C')
        sky_condition_time, sky_condition = self.get_field_data('sky_condition')

        temp_diff = sky_temp_C - ambient_temp_C

        td_axes.plot_date(sky_time, temp_diff, 'ko-', label='Cloudiness',
                          markersize=2, markeredgewidth=0,
                          drawstyle="default")
        td_axes.fill_between(sky_time, -60, temp_diff, where=np.array(sky_condition) == 'Clear', color='green', alpha=0.5)
        td_axes.fill_between(sky_time, -60, temp_diff, where=np.array(sky_condition) == 'Cloudy', color='yellow', alpha=0.5)
        td_axes.fill_between(time, -60, temp_diff, where=np.array(sky_condition) == 'Very Cloudy', color='red', alpha=0.5)

        self.plt.ylabel("Cloudiness")
        self.plt.grid(which='major', color='k')
        self.plt.yticks(range(-100, 100, 10))
        self.plt.xlim(self.start, self.end)
        self.plt.ylim(-60, 10)
        td_axes.xaxis.set_major_locator(self.hours)
        td_axes.xaxis.set_major_formatter(self.hours_fmt)
        td_axes.xaxis.set_ticklabels([])

        tdlh_axes = self.plt.axes(self.plot_positions[1][1])
        tdlh_axes.plot_date(sky_time, temp_diff, 'ko-', label='Cloudiness', markersize=4, markeredgewidth=0, drawstyle="default")
        tdlh_axes.fill_between(sky_time, -60, temp_diff, where=np.array(sky_condition) == 'Clear', color='green', alpha=0.5)
        tdlh_axes.fill_between(sky_time, -60, temp_diff, where=np.array(sky_condition) == 'Cloudy', color='yellow', alpha=0.5)
        tdlh_axes.fill_between(sky_time, -60, temp_diff, where=np.array(sky_condition) == 'Very Cloudy', color='red', alpha=0.5)

        self.plt.grid(which='major', color='k')
        self.plt.yticks(range(-100, 100, 10))
        self.plt.ylim(-60, 10)
        self.plt.xlim(self.date - tdelta(0, 60 * 60), self.date + tdelta(0, 5 * 60))
        tdlh_axes.xaxis.set_major_locator(self.mins)
        tdlh_axes.xaxis.set_major_formatter(self.mins_fmt)
        tdlh_axes.xaxis.set_ticklabels([])
        tdlh_axes.yaxis.set_ticklabels([])

    def get_windspeed_vs_time(self):
        print('Plot Wind Speed vs. Time')
        # -------------------------------------------------------------------------
        # Plot Wind Speed vs. Time
        trans = {'Calm': 0, 'Windy': 1, 'Gusty': 1, 'Very Windy': 10, 'Very Gusty': 10, 'Unknown': 0}

        w_axes = self.plt.axes(self.plot_positions[2][0])
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
        w_axes.plot_date([start, self.end], [0, 0], 'k-', ms=1)
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
            label_time = self.end - tdelta(0, 6 * 60 * 60)
            label_wind = 61
            w_axes.annotate('Max Gust: {:.1f} (km/h)'.format(max_wind),
                            xy=(label_time, max_wind),
                            xytext=(label_time, label_wind),
                            size=16,
                            )
        except:
            pass
        self.plt.ylabel("Wind (km/h)")
        self.plt.grid(which='major', color='k')
        self.plt.yticks(range(-100, 100, 10))
        self.plt.xlim(self.start, self.end)
        wind_max = max([45, np.ceil(max(wind_speed) / 5.) * 5.])
        self.plt.ylim(0, 75)
        w_axes.xaxis.set_major_locator(self.hours)
        w_axes.xaxis.set_major_formatter(self.hours_fmt)
        w_axes.xaxis.set_ticklabels([])

        wlh_axes = self.plt.axes(self.plot_positions[2][1])
        wlh_axes.plot_date(time, wind_speed, 'ko', alpha=0.7,
                           markersize=4, markeredgewidth=0,
                           drawstyle="default")
        wlh_axes.plot_date(time, wind_mavg, 'b-',
                           label='Wind Speed',
                           markersize=2, markeredgewidth=0,
                           linewidth=3, alpha=0.5,
                           drawstyle="default")
        wlh_axes.plot_date([start, self.end], [0, 0], 'k-', ms=1)
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
            current_wind = self.current_values['data']['wind_speed_KPH']
            current_time = self.current_values['date']
            label_time = current_time - tdelta(0, 30 * 60)
            label_wind = 61
            wlh_axes.annotate('Currently: {:.0f} km/h'.format(current_wind),
                              xy=(current_time, current_wind),
                              xytext=(label_time, label_wind),
                              size=16,
                              )
        except:
            pass
        self.plt.grid(which='major', color='k')
        self.plt.yticks(range(-100, 100, 10))
        self.plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
        wind_max = max([45, np.ceil(max(wind_speed) / 5.) * 5.])
        self.plt.ylim(0, 75)
        wlh_axes.xaxis.set_major_locator(self.mins)
        wlh_axes.xaxis.set_major_formatter(self.mins_fmt)
        wlh_axes.xaxis.set_ticklabels([])
        wlh_axes.yaxis.set_ticklabels([])

    def get_rain_freq_vs_time(self):
        print('Plot Rain Frequency vs. Time')
        # -------------------------------------------------------------------------
        # Plot Rain Frequency vs. Time
        required_cols = ('rain_frequency' and 'rain_condition')

        rf_axes = self.plt.axes(self.plot_positions[3][0])
        rf_value = [x['data']['rain_frequency'] for x in entries if required_cols in x['data'].keys()]
        rain_condition = [x['data']['rain_condition'] for x in entries if required_cols in x['data'].keys()]
        time = [x['date'] for x in entries if required_cols in x['data'].keys()]

        rf_axes.plot_date(time, rf_value, 'ko-', label='Rain',
                          markersize=2, markeredgewidth=0,
                          drawstyle="default")

        rf_axes.fill_between(time, 0, rf_value, where=np.array(rain_condition) == 'Dry', color='green', alpha=0.5)
        rf_axes.fill_between(time, 0, rf_value, where=np.array(rain_condition) == 'Rain', color='red', alpha=0.5)

        self.plt.ylabel("Rain Sensor")
        self.plt.grid(which='major', color='k')
        self.plt.ylim(120, 275)
        self.plt.xlim(self.start, self.end)
        rf_axes.xaxis.set_major_locator(self.hours)
        rf_axes.xaxis.set_major_formatter(self.hours_fmt)
        rf_axes.xaxis.set_ticklabels([])
        rf_axes.yaxis.set_ticklabels([])

        rflh_axes = self.plt.axes(self.plot_positions[3][1])
        rflh_axes.plot_date(time, rf_value, 'ko-', label='Rain',
                            markersize=4, markeredgewidth=0,
                            drawstyle="default")
        rflh_axes.fill_between(time, 0, rf_value, where=np.array(rain_condition) == 'Dry',
                               color='green', alpha=0.5)
        rflh_axes.fill_between(time, 0, rf_value, where=np.array(rain_condition) == 'Rain',
                               color='red', alpha=0.5)
        self.plt.grid(which='major', color='k')
        self.plt.ylim(120, 275)
        self.plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
        rflh_axes.xaxis.set_major_locator(self.mins)
        rflh_axes.xaxis.set_major_formatter(self.mins_fmt)
        rflh_axes.xaxis.set_ticklabels([])
        rflh_axes.yaxis.set_ticklabels([])

    def get_safety_vs_time(self):
        print('Plot Safe/Unsafe vs. Time')
        # -------------------------------------------------------------------------
        # Safe/Unsafe vs. Time
        safe_axes = self.plt.axes(self.plot_positions[4][0])
        safe_value = [int(x['data']['safe']) for x in entries if 'safe' in x['data'].keys()]
        safe_time = [x['date'] for x in entries if 'safe' in x['data'].keys()]

        safe_axes.plot_date(safe_time, safe_value, 'ko',
                            markersize=2, markeredgewidth=0,
                            drawstyle="default")
        safe_axes.fill_between(safe_time, -1, safe_value, where=np.array(safe_value) == 1,
                               color='green', alpha=0.5)
        safe_axes.fill_between(safe_time, -1, safe_value, where=np.array(safe_value) == 0,
                               color='red', alpha=0.5)
        self.plt.ylabel("Safe")
        self.plt.xlim(self.start, self.end)
        self.plt.ylim(-0.1, 1.1)
        self.plt.yticks([0, 1])
        self.plt.grid(which='major', color='k')
        safe_axes.xaxis.set_major_locator(self.hours)
        safe_axes.xaxis.set_major_formatter(self.hours_fmt)
        safe_axes.xaxis.set_ticklabels([])
        safe_axes.yaxis.set_ticklabels([])

        safelh_axes = self.plt.axes(self.plot_positions[4][1])
        safelh_axes.plot_date(safe_time, safe_value, 'ko-',
                              markersize=4, markeredgewidth=0,
                              drawstyle="default")
        safelh_axes.fill_between(safe_time, -1, safe_value, where=np.array(safe_value) == 1,
                                 color='green', alpha=0.5)
        safelh_axes.fill_between(safe_time, -1, safe_value, where=np.array(safe_value) == 0,
                                 color='red', alpha=0.5)
        self.plt.ylim(-0.1, 1.1)
        self.plt.yticks([0, 1])
        self.plt.grid(which='major', color='k')
        self.plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
        safelh_axes.xaxis.set_major_locator(self.mins)
        safelh_axes.xaxis.set_major_formatter(self.mins_fmt)
        safelh_axes.xaxis.set_ticklabels([])
        safelh_axes.yaxis.set_ticklabels([])

    def get_pwm_vs_time(self):
        print('Plot PWM Value vs. Time')
        # -------------------------------------------------------------------------
        # Plot PWM Value vs. Time
        required_cols = ('pwm_value' and 'rain_sensor_temp_C' and 'ambient_temp_C')

        pwm_axes = self.plt.axes(self.plot_positions[5][0])
        self.plt.ylabel("Heater (%)")
        self.plt.ylim(-5, 105)
        self.plt.yticks([0, 25, 50, 75, 100])
        self.plt.xlim(self.start, self.end)
        self.plt.grid(which='major', color='k')
        rst_axes = pwm_axes.twinx()
        self.plt.ylim(-1, 21)
        self.plt.xlim(self.start, self.end)

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
        pwm_axes.xaxis.set_major_locator(self.hours)
        pwm_axes.xaxis.set_major_formatter(self.hours_fmt)

        pwmlh_axes = self.plt.axes(self.plot_positions[5][1])
        self.plt.ylim(-5, 105)
        self.plt.yticks([0, 25, 50, 75, 100])
        self.plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
        self.plt.grid(which='major', color='k')
        rstlh_axes = pwmlh_axes.twinx()
        self.plt.ylim(-1, 21)
        self.plt.xlim(date - tdelta(0, 60 * 60), date + tdelta(0, 5 * 60))
        rstlh_axes.plot_date(time, rst_delta, 'ro-', alpha=0.5,
                             label='RST Delta (C)',
                             markersize=4, markeredgewidth=0,
                             drawstyle="default")
        rstlh_axes.xaxis.set_ticklabels([])
        rstlh_axes.yaxis.set_ticklabels([])
        pwmlh_axes.plot_date(time, pwm_value, 'bo', label='Heater',
                             markersize=4, markeredgewidth=0,
                             drawstyle="default")
        pwmlh_axes.xaxis.set_major_locator(self.mins)
        pwmlh_axes.xaxis.set_major_formatter(self.mins_fmt)
        pwmlh_axes.yaxis.set_ticklabels([])

    def save_plot(self, plot_filename=None):
        """ Save the plot to file """

        if plot_filename is None:
            plot_filename = '{}.png'.format(self.date_string)

        plot_file = os.path.expanduser('/var/panoptes/weather_plots/{}'.format(plot_filename))

        print('Save Figure: {}'.format(plot_file))

        self.self.plt.savefig(plot_file, dpi=self.dpi, bbox_inches='tight', pad_inches=0.10)

        if self.today:
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

    weather_plotter = WeatherPlotter(date_string=args.date)
