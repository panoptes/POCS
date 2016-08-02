#!/usr/bin/env python3

import os
from datetime import datetime as dt
from datetime import timedelta as tdelta
import numpy as np

from astropy.time import Time
from astropy.table import Table

from astropy.coordinates import EarthLocation
from astroplan import Observer

import pymongo

from pocs.utils.database import PanMongo
from pocs.utils.config import load_config

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
            self.start = self.date - tdelta(1,0)
            self.end = self.date
        else:
            self.date = dt.strptime('{} 23:59:59'.format(date_string),
                                    '%Y%m%dUT %H:%M:%S')
            self.date_string = date_string
            self.start = dt(self.date.year, self.date.month, self.date.day, 0, 0, 0, 0)
            self.end = dt(self.date.year, self.date.month, self.date.day, 23, 59, 59, 0)

        print(self.start)
        print(self.end)

        self.dpi = kwargs.get('dpi', 100)
        self.fig = plt.figure(figsize=(16, 9), dpi=self.dpi)
#         self.axes = plt.gca()

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
            height=self.cfg['elevation'],
        )
        self.obs = Observer(location=self.loc, name='PANOPTES',
                            timezone=self.cfg['timezone'])

        self.sunset = self.obs.sun_set_time(Time(self.start), which='next').datetime
        self.evening_civil_twilight = self.obs.twilight_evening_civil(Time(self.start),
                                      which='next').datetime
        self.evening_nautical_twilight = self.obs.twilight_evening_nautical(
                                         Time(self.start), which='next').datetime
        self.evening_astronomical_twilight = self.obs.twilight_evening_astronomical(
                                             Time(self.start), which='next').datetime
        self.morning_astronomical_twilight = self.obs.twilight_morning_astronomical(
                                             Time(self.start), which='next').datetime
        self.morning_nautical_twilight = self.obs.twilight_morning_nautical(
                                         Time(self.start), which='next').datetime
        self.morning_civil_twilight = self.obs.twilight_morning_civil(
                                      Time(self.start), which='next').datetime
        self.sunrise = self.obs.sun_rise_time(Time(self.start),
                                              which='next').datetime

        print('start:                         {}'.format(Time(self.start)))
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
        self.plot_positions = [([0.000, 0.835, 0.700, 0.170], [0.720, 0.835, 0.280, 0.170]),
                               ([0.000, 0.635, 0.700, 0.170], [0.720, 0.635, 0.280, 0.170]),
                               ([0.000, 0.450, 0.700, 0.170], [0.720, 0.450, 0.280, 0.170]),
                               ([0.000, 0.265, 0.700, 0.170], [0.720, 0.265, 0.280, 0.170]),
                               ([0.000, 0.185, 0.700, 0.065], [0.720, 0.185, 0.280, 0.065]),
                               ([0.000, 0.000, 0.700, 0.170], [0.720, 0.000, 0.280, 0.170]),
                               ]

        # Connect to sensors collection
        self.db = PanMongo()
        self.entries = [x for x in self.db.weather.find(
                        {'date': {'$gt': self.start, '$lt': self.end}}).sort([
                        ('date', pymongo.ASCENDING)])]

        self.table = Table(names=('ambient_temp_C', 'sky_temp_C', 'sky_condition',
                                  'wind_speed_KPH', 'wind_condition',
                                  'gust_condition', 'rain_frequency',
                                  'rain_condition', 'safe', 'pwm_value',
                                  'rain_sensor_temp_C', 'date'),
                           dtype=('f4', 'f4', 'a15',
                                  'f4', 'a15',
                                  'a15', 'f4',
                                  'a15', bool, 'f4',
                                  'f4', 'a26'),
                           )
        for entry in self.entries:
            data = {'date': entry['date'].isoformat()}
            keys = entry['data'].keys()
            for key in keys:
                if key in self.table.colnames:
                    data[key] = entry['data'][key]
            self.table.add_row(data)
        self.time = [dt.strptime(datestr.decode('utf8').split('.')[0], '%Y-%m-%dT%H:%M:%S')
                     for datestr in self.table['date']]

        if self.today:
            self.current_values = [x for x in self.db.current.find({"type": "weather"})][0]
        else:
            self.current_values = None

        self.plot_ambient_vs_time()
        self.plot_cloudiness_vs_time()
        self.plot_windspeed_vs_time()
        self.plot_rain_freq_vs_time()
        self.plot_safety_vs_time()
        self.plot_pwm_vs_time()
        self.save_plot()


    def plot_ambient_vs_time(self):
        print('Plot Ambient Temperature vs. Time')
        # -------------------------------------------------------------------------
        # Plot Ambient Temperature vs. Time
        t_axes = plt.axes(self.plot_positions[0][0])
        if self.today:
            time_title = self.date
        else:
            time_title = self.end

        plt.title('Weather for {} at {}'.format(self.date_string,
                  time_title.strftime('%H:%M:%S UT')))

        amb_temp = self.table['ambient_temp_C']

        plt.plot_date(self.time, amb_temp, 'ko',
                      markersize=2, markeredgewidth=0, drawstyle="default")

        try:
            max_temp = max(amb_temp)
            min_temp = min(amb_temp)
            label_time = self.end - tdelta(0, 7 * 60 * 60)
            label_temp = 28
            plt.annotate('Low: {:4.1f} $^\circ$C, High: {:4.1f} $^\circ$C'.format(
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
        plt.xlim(self.start, self.end)
        plt.ylim(-5, 35)
        t_axes.xaxis.set_major_locator(self.hours)
        t_axes.xaxis.set_major_formatter(self.hours_fmt)

        if self.obs.is_night(Time(self.start)):
            plt.axvspan(self.start, self.morning_astronomical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.5)
            plt.axvspan(self.morning_astronomical_twilight,
                        self.morning_nautical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.3)
            plt.axvspan(self.morning_nautical_twilight,
                        self.morning_civil_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.2)
            plt.axvspan(self.morning_civil_twilight, self.sunrise,
                        ymin=0, ymax=1, color='blue', alpha=0.1)
            plt.axvspan(self.sunset, self.evening_civil_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.1)
            plt.axvspan(self.evening_civil_twilight,
                        self.evening_nautical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.2)
            plt.axvspan(self.evening_nautical_twilight,
                        self.evening_astronomical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.3)
            plt.axvspan(self.evening_astronomical_twilight, self.end,
                        ymin=0, ymax=1, color='blue', alpha=0.5)
        else:
            plt.axvspan(self.sunset, self.evening_civil_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.1)
            plt.axvspan(self.evening_civil_twilight,
                        self.evening_nautical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.2)
            plt.axvspan(self.evening_nautical_twilight,
                        self.evening_astronomical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.3)
            plt.axvspan(self.evening_astronomical_twilight,
                        self.morning_astronomical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.5)
            plt.axvspan(self.morning_astronomical_twilight,
                        self.morning_nautical_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.3)
            plt.axvspan(self.morning_nautical_twilight,
                        self.morning_civil_twilight,
                        ymin=0, ymax=1, color='blue', alpha=0.2)
            plt.axvspan(self.morning_civil_twilight, self.sunrise,
                        ymin=0, ymax=1, color='blue', alpha=0.1)

        if self.today:
            tlh_axes = plt.axes(self.plot_positions[0][1])
            plt.title('Last Hour')
            plt.plot_date(self.time, amb_temp, 'ko',
                               markersize=4, markeredgewidth=0,
                               drawstyle="default")
            try:
                current_amb_temp = self.current_values['data']['ambient_temp_C']
                current_time = self.current_values['date']
                label_time = current_time - tdelta(0, 50 * 60)
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
            tlh_axes.xaxis.set_major_locator(self.mins)
            tlh_axes.xaxis.set_major_formatter(self.mins_fmt)
            tlh_axes.yaxis.set_ticklabels([])
            plt.xlim(self.date - tdelta(0, 60 * 60), self.date + tdelta(0,5*60))
            plt.ylim(-5, 35)

    def plot_cloudiness_vs_time(self):
        print('Plot Temperature Difference vs. Time')
        # -------------------------------------------------------------------------
        # Plot Temperature Difference vs. Time
        td_axes = plt.axes(self.plot_positions[1][0])

        sky_temp_C = self.table['sky_temp_C']
        ambient_temp_C = self.table['ambient_temp_C']
        sky_condition = self.table['sky_condition']

        temp_diff = np.array(sky_temp_C) - np.array(ambient_temp_C)

        plt.plot_date(self.time, temp_diff, 'ko-', label='Cloudiness',
                          markersize=2, markeredgewidth=0,
                          drawstyle="default")
        wclear = [(x.decode('utf8').strip() == 'Clear') for x in sky_condition.data]
        plt.fill_between(self.time, -60, temp_diff, where=wclear,
                         color='green', alpha=0.5)
        wcloudy = [(x.decode('utf8').strip() == 'Cloudy') for x in sky_condition.data]
        plt.fill_between(self.time, -60, temp_diff, where=wcloudy,
                         color='yellow', alpha=0.5)
        wvcloudy = [(x.decode('utf8').strip() == 'Very Cloudy') for x in sky_condition.data]
        plt.fill_between(self.time, -60, temp_diff, where=wvcloudy,
                         color='red', alpha=0.5)

        plt.ylabel("Cloudiness")
        plt.grid(which='major', color='k')
        plt.yticks(range(-100, 100, 10))
        plt.xlim(self.start, self.end)
        plt.ylim(-60, 10)
        td_axes.xaxis.set_major_locator(self.hours)
        td_axes.xaxis.set_major_formatter(self.hours_fmt)
        td_axes.xaxis.set_ticklabels([])

        if self.today:
            tdlh_axes = plt.axes(self.plot_positions[1][1])
            tdlh_axes.plot_date(self.time, temp_diff, 'ko-',
                                label='Cloudiness', markersize=4,
                                markeredgewidth=0, drawstyle="default")
            plt.fill_between(self.time, -60, temp_diff, where=wclear,
                             color='green', alpha=0.5)
            plt.fill_between(self.time, -60, temp_diff, where=wcloudy,
                             color='yellow', alpha=0.5)
            plt.fill_between(self.time, -60, temp_diff, where=wvcloudy,
                             color='red', alpha=0.5)

            try:
                current_cloudiness = self.current_values['data']['sky_condition']
                current_time = self.current_values['date']
                label_time = current_time - tdelta(0, 50 * 60)
                label_temp = 0
                tdlh_axes.annotate('Currently: {:s}'.format(current_cloudiness),
                                   xy=(current_time, label_temp),
                                   xytext=(label_time, label_temp),
                                   size=16,
                                   )
            except:
                pass

            plt.grid(which='major', color='k')
            plt.yticks(range(-100, 100, 10))
            plt.ylim(-60, 10)
            plt.xlim(self.date - tdelta(0, 60 * 60), self.date + tdelta(0, 5*60))
            tdlh_axes.xaxis.set_major_locator(self.mins)
            tdlh_axes.xaxis.set_major_formatter(self.mins_fmt)
            tdlh_axes.xaxis.set_ticklabels([])
            tdlh_axes.yaxis.set_ticklabels([])

    def plot_windspeed_vs_time(self):
        print('Plot Wind Speed vs. Time')
        # -------------------------------------------------------------------------
        # Plot Wind Speed vs. Time
        w_axes = plt.axes(self.plot_positions[2][0])

        wind_speed = self.table['wind_speed_KPH']
        wind_mavg = moving_average(wind_speed, 10)
        wind_condition = self.table['wind_condition']
        wind_gust = self.table['gust_condition']

        w_axes.plot_date(self.time, wind_speed, 'ko', alpha=0.5,
                         markersize=2, markeredgewidth=0,
                         drawstyle="default")
        w_axes.plot_date(self.time, wind_mavg, 'b-',
                         label='Wind Speed',
                         markersize=3, markeredgewidth=0,
                         linewidth=3, alpha=0.5,
                         drawstyle="default")
        w_axes.plot_date([self.start, self.end], [0, 0], 'k-', ms=1)
        wcalm = [(x.decode('utf8').strip() == 'Calm') for x in wind_condition.data]
        w_axes.fill_between(self.time, -5, wind_speed, where=wcalm,
                            color='green', alpha=0.5)
        wwindy = [(x.decode('utf8').strip() == 'Windy') for x in wind_condition.data]
        w_axes.fill_between(self.time, -5, wind_speed, where=wwindy,
                            color='yellow', alpha=0.5)
        wvwindy = [(x.decode('utf8').strip() == 'Very Windy') for x in wind_condition.data]
        w_axes.fill_between(self.time, -5, wind_speed, where=wvwindy,
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
        plt.ylabel("Wind (km/h)")
        plt.grid(which='major', color='k')
        plt.yticks(range(-100, 100, 10))
        plt.xlim(self.start, self.end)
        wind_max = max([45, np.ceil(max(wind_speed) / 5.) * 5.])
        plt.ylim(0, 75)
        w_axes.xaxis.set_major_locator(self.hours)
        w_axes.xaxis.set_major_formatter(self.hours_fmt)
        w_axes.xaxis.set_ticklabels([])

        if self.today:
            wlh_axes = plt.axes(self.plot_positions[2][1])
            wlh_axes.plot_date(self.time, wind_speed, 'ko', alpha=0.7,
                               markersize=4, markeredgewidth=0,
                               drawstyle="default")
            wlh_axes.plot_date(self.time, wind_mavg, 'b-',
                               label='Wind Speed',
                               markersize=2, markeredgewidth=0,
                               linewidth=3, alpha=0.5,
                               drawstyle="default")
            wlh_axes.plot_date([self.start, self.end], [0, 0], 'k-', ms=1)
            wlh_axes.fill_between(self.time, -5, wind_speed, where=wcalm,
                                color='green', alpha=0.5)
            wlh_axes.fill_between(self.time, -5, wind_speed, where=wwindy,
                                color='yellow', alpha=0.5)
            wlh_axes.fill_between(self.time, -5, wind_speed, where=wvwindy,
                                color='red', alpha=0.5)
            try:
                current_wind = self.current_values['data']['wind_speed_KPH']
                current_time = self.current_values['date']
                label_time = current_time - tdelta(0, 50 * 60)
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
            plt.xlim(self.date - tdelta(0, 60 * 60), self.date + tdelta(0, 5*60))
            wind_max = max([45, np.ceil(max(wind_speed) / 5.) * 5.])
            plt.ylim(0, 75)
            wlh_axes.xaxis.set_major_locator(self.mins)
            wlh_axes.xaxis.set_major_formatter(self.mins_fmt)
            wlh_axes.xaxis.set_ticklabels([])
            wlh_axes.yaxis.set_ticklabels([])

    def plot_rain_freq_vs_time(self):
        print('Plot Rain Frequency vs. Time')
        # -------------------------------------------------------------------------
        # Plot Rain Frequency vs. Time
        rf_axes = plt.axes(self.plot_positions[3][0])

        rf_value = self.table['rain_frequency']
        rain_condition = self.table['rain_condition']

        rf_axes.plot_date(self.time, rf_value, 'ko-', label='Rain',
                          markersize=2, markeredgewidth=0,
                          drawstyle="default")

        wdry = [(x.decode('utf8').strip() == 'Dry') for x in rain_condition.data]
        rf_axes.fill_between(self.time, 0, rf_value, where=wdry,
                             color='green', alpha=0.5)
        wwet = [(x.decode('utf8').strip() == 'Wet') for x in rain_condition.data]
        rf_axes.fill_between(self.time, 0, rf_value, where=wwet,
                             color='orange', alpha=0.5)
        wrain = [(x.decode('utf8').strip() == 'Rain') for x in rain_condition.data]
        rf_axes.fill_between(self.time, 0, rf_value, where=wrain,
                             color='red', alpha=0.5)

        plt.ylabel("Rain Sensor")
        plt.grid(which='major', color='k')
        plt.ylim(1200, 2750)
        plt.xlim(self.start, self.end)
        rf_axes.xaxis.set_major_locator(self.hours)
        rf_axes.xaxis.set_major_formatter(self.hours_fmt)
        rf_axes.xaxis.set_ticklabels([])
        rf_axes.yaxis.set_ticklabels([])

        if self.today:
            rflh_axes = plt.axes(self.plot_positions[3][1])
            rflh_axes.plot_date(self.time, rf_value, 'ko-', label='Rain',
                                markersize=4, markeredgewidth=0,
                                drawstyle="default")
            rflh_axes.fill_between(self.time, 0, rf_value, where=wdry,
                                   color='green', alpha=0.5)
            rflh_axes.fill_between(self.time, 0, rf_value, where=wwet,
                                   color='orange', alpha=0.5)
            rflh_axes.fill_between(self.time, 0, rf_value, where=wrain,
                                   color='red', alpha=0.5)
            try:
                current_rain = self.current_values['data']['rain_condition']
                current_time = self.current_values['date']
                label_time = current_time - tdelta(0, 50 * 60)
                label_y = 2500
                rflh_axes.annotate('Currently: {:s}'.format(current_rain),
                                   xy=(current_time, label_y),
                                   xytext=(label_time, label_y),
                                   size=16,
                                   )
            except:
                pass
            plt.grid(which='major', color='k')
            plt.ylim(1200, 2750)
            plt.xlim(self.date - tdelta(0, 60 * 60), self.date + tdelta(0, 5*60))
            rflh_axes.xaxis.set_major_locator(self.mins)
            rflh_axes.xaxis.set_major_formatter(self.mins_fmt)
            rflh_axes.xaxis.set_ticklabels([])
            rflh_axes.yaxis.set_ticklabels([])

    def plot_safety_vs_time(self):
        print('Plot Safe/Unsafe vs. Time')
        # -------------------------------------------------------------------------
        # Safe/Unsafe vs. Time
        safe_axes = plt.axes(self.plot_positions[4][0])

        safe_value = [int(x) for x in self.table['safe']]

        safe_axes.plot_date(self.time, safe_value, 'ko',
                            markersize=2, markeredgewidth=0,
                            drawstyle="default")
        safe_axes.fill_between(self.time, -1, safe_value,
                               where=(self.table['safe'].data),
                               color='green', alpha=0.5)
        safe_axes.fill_between(self.time, -1, safe_value,
                               where=(~self.table['safe'].data),
                               color='red', alpha=0.5)
        plt.ylabel("Safe")
        plt.xlim(self.start, self.end)
        plt.ylim(-0.1, 1.1)
        plt.yticks([0, 1])
        plt.grid(which='major', color='k')
        safe_axes.xaxis.set_major_locator(self.hours)
        safe_axes.xaxis.set_major_formatter(self.hours_fmt)
        safe_axes.xaxis.set_ticklabels([])
        safe_axes.yaxis.set_ticklabels([])

        if self.today:
            safelh_axes = plt.axes(self.plot_positions[4][1])
            safelh_axes.plot_date(self.time, safe_value, 'ko-',
                                  markersize=4, markeredgewidth=0,
                                  drawstyle="default")
            safelh_axes.fill_between(self.time, -1, safe_value,
                                     where=(self.table['safe'].data),
                                     color='green', alpha=0.5)
            safelh_axes.fill_between(self.time, -1, safe_value,
                                     where=(~self.table['safe'].data),
                                     color='red', alpha=0.5)
            try:
                current_safe = {True: 'Safe', False: 'Unsafe'}[self.current_values['data']['safe']]
                current_time = self.current_values['date']
                label_time = current_time - tdelta(0, 50 * 60)
                label_y = 0.5
                safelh_axes.annotate('Currently: {:s}'.format(current_safe),
                                     xy=(current_time, label_y),
                                     xytext=(label_time, label_y),
                                     size=16,
                                     )
            except:
                pass
            plt.ylim(-0.1, 1.1)
            plt.yticks([0, 1])
            plt.grid(which='major', color='k')
            plt.xlim(self.date - tdelta(0, 60 * 60), self.date + tdelta(0, 5*60))
            safelh_axes.xaxis.set_major_locator(self.mins)
            safelh_axes.xaxis.set_major_formatter(self.mins_fmt)
            safelh_axes.xaxis.set_ticklabels([])
            safelh_axes.yaxis.set_ticklabels([])

    def plot_pwm_vs_time(self):
        print('Plot PWM Value vs. Time')
        # -------------------------------------------------------------------------
        # Plot PWM Value vs. Time
        pwm_axes = plt.axes(self.plot_positions[5][0])
        plt.ylabel("Heater (%)")
        plt.ylim(-5, 105)
        plt.yticks([0, 25, 50, 75, 100])
        plt.xlim(self.start, self.end)
        plt.grid(which='major', color='k')
        rst_axes = pwm_axes.twinx()
        plt.ylim(-1, 21)
        plt.xlim(self.start, self.end)

        pwm_value = self.table['pwm_value']
        rst_delta = self.table['rain_sensor_temp_C'] - self.table['ambient_temp_C']

        rst_axes.plot_date(self.time, rst_delta, 'ro-', alpha=0.5,
                           label='RST Delta (C)',
                           markersize=2, markeredgewidth=0,
                           drawstyle="default")
        pwm_axes.plot_date(self.time, pwm_value, 'bo', label='Heater',
                           markersize=2, markeredgewidth=0,
                           drawstyle="default")
        pwm_axes.xaxis.set_major_locator(self.hours)
        pwm_axes.xaxis.set_major_formatter(self.hours_fmt)

        if self.today:
            pwmlh_axes = plt.axes(self.plot_positions[5][1])
            plt.ylim(-5, 105)
            plt.yticks([0, 25, 50, 75, 100])
            plt.xlim(self.date - tdelta(0, 60 * 60), self.date + tdelta(0, 5*60))
            plt.grid(which='major', color='k')
            rstlh_axes = pwmlh_axes.twinx()
            plt.ylim(-1, 21)
            plt.xlim(self.date - tdelta(0, 60 * 60), self.date + tdelta(0, 5*60))
            rstlh_axes.plot_date(self.time, rst_delta, 'ro-', alpha=0.5,
                                 label='RST Delta (C)',
                                 markersize=4, markeredgewidth=0,
                                 drawstyle="default")
            rstlh_axes.xaxis.set_ticklabels([])
            rstlh_axes.yaxis.set_ticklabels([])
            pwmlh_axes.plot_date(self.time, pwm_value, 'bo', label='Heater',
                                 markersize=4, markeredgewidth=0,
                                 drawstyle="default")
            pwmlh_axes.xaxis.set_major_locator(self.mins)
            pwmlh_axes.xaxis.set_major_formatter(self.mins_fmt)
            pwmlh_axes.yaxis.set_ticklabels([])

    def save_plot(self, plot_filename=None):
        """ Save the plot to file """

        if plot_filename is None:
            if self.today:
                plot_filename = 'today.png'
            else:
                plot_filename = '{}.png'.format(self.date_string)

        plot_file = os.path.expanduser('/var/panoptes/weather_plots/{}'.format(plot_filename))

        print('Saving Figure: {}'.format(plot_file))

        self.fig.savefig(plot_file, dpi=self.dpi, bbox_inches='tight', pad_inches=0.10)


def moving_average(interval, window_size):
    """ A simple moving average function """
    if window_size > len(interval):
        window_size = len(interval)
    window = np.ones(int(window_size)) / float(window_size)
    return np.convolve(interval, window, 'same')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
             description="Make a plot of the weather for a give date.")
    parser.add_argument("-d", "--date", type=str, dest="date", default=None,
                        help="UT Date to plot")
    args = parser.parse_args()

    weather_plotter = WeatherPlotter(date_string=args.date)
