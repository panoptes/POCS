#!/usr/bin/env python3

import numpy as np
import os
import pandas as pd
import sys
import warnings

from datetime import datetime as dt
from datetime import timedelta as tdelta

from astropy.table import Table
from astropy.time import Time

from astroplan import Observer
from astropy.coordinates import EarthLocation

from pocs.utils.config import load_config

import matplotlib as mpl
mpl.use('Agg')
from matplotlib import pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.dates import HourLocator
from matplotlib.dates import MinuteLocator
from matplotlib.ticker import FormatStrFormatter
from matplotlib.ticker import MultipleLocator
plt.ioff()
plt.style.use('classic')


def label_pos(lim, pos=0.85):
    return lim[0] + pos * (lim[1] - lim[0])


class WeatherPlotter(object):

    """ Plot weather information for a given time span """

    def __init__(self, date_string=None, data_file=None, *args, **kwargs):
        super(WeatherPlotter, self).__init__()
        self.args = args
        self.kwargs = kwargs

        config = load_config(config_files=['peas'])
        self.cfg = config['weather']['plot']
        location_cfg = config.get('location', None)

        self.thresholds = config['weather'].get('aag_cloud', None)

        if not date_string:
            self.today = True
            self.date = dt.utcnow()
            self.date_string = self.date.strftime('%Y%m%dUT')
            self.start = self.date - tdelta(1, 0)
            self.end = self.date
            self.lhstart = self.date - tdelta(0, 60 * 60)
            self.lhend = self.date + tdelta(0, 5 * 60)

        else:
            self.today = False
            self.date = dt.strptime('{} 23:59:59'.format(date_string),
                                    '%Y%m%dUT %H:%M:%S')
            self.date_string = date_string
            self.start = dt(self.date.year, self.date.month, self.date.day, 0, 0, 0, 0)
            self.end = dt(self.date.year, self.date.month, self.date.day, 23, 59, 59, 0)
        print('Creating weather plotter for {}'.format(self.date_string))

        self.twilights = self.get_twilights(location_cfg)

        self.table = self.get_table_data(data_file)

        if self.table is None:
            warnings.warn("No data")
            sys.exit(0)

        self.time = pd.to_datetime(self.table['date'])
        first = self.time[0].isoformat()
        last = self.time[-1].isoformat()
        print('  Retrieved {} entries between {} and {}'.format(
              len(self.table), first, last))

        if self.today:
            self.current_values = self.table[-1]
        else:
            self.current_values = None

    def make_plot(self, output_file=None):
        # -------------------------------------------------------------------------
        # Plot a day's weather
        # -------------------------------------------------------------------------
        print('  Setting up plot for time range: {} to {}'.format(
              self.start.isoformat(), self.end.isoformat()))
        if self.today:
            print('  Will generate last hour plot for time range: {} to {}'.format(
                self.lhstart.isoformat(), self.lhend.isoformat()))
        self.dpi = self.kwargs.get('dpi', 72)
        self.fig = plt.figure(figsize=(20, 12), dpi=self.dpi)
#         self.axes = plt.gca()
        self.hours = HourLocator(byhour=range(24), interval=1)
        self.hours_fmt = DateFormatter('%H')
        self.mins = MinuteLocator(range(0, 60, 15))
        self.mins_fmt = DateFormatter('%H:%M')
        self.plot_positions = [([0.000, 0.835, 0.700, 0.170], [0.720, 0.835, 0.280, 0.170]),
                               ([0.000, 0.635, 0.700, 0.170], [0.720, 0.635, 0.280, 0.170]),
                               ([0.000, 0.450, 0.700, 0.170], [0.720, 0.450, 0.280, 0.170]),
                               ([0.000, 0.265, 0.700, 0.170], [0.720, 0.265, 0.280, 0.170]),
                               ([0.000, 0.185, 0.700, 0.065], [0.720, 0.185, 0.280, 0.065]),
                               ([0.000, 0.000, 0.700, 0.170], [0.720, 0.000, 0.280, 0.170]),
                               ]
        self.plot_ambient_vs_time()
        self.plot_cloudiness_vs_time()
        self.plot_windspeed_vs_time()
        self.plot_rain_freq_vs_time()
        self.plot_safety_vs_time()
        self.plot_pwm_vs_time()
        self.save_plot(plot_filename=output_file)

    def get_table_data(self, data_file):
        """ Get the table data

        If a `data_file` (csv) is passed, read from that, otherwise use mongo

        """
        table = None

        col_names = ('ambient_temp_C', 'sky_temp_C', 'sky_condition',
                     'wind_speed_KPH', 'wind_condition',
                     'gust_condition', 'rain_frequency',
                     'rain_condition', 'safe', 'pwm_value',
                     'rain_sensor_temp_C', 'date')

        col_dtypes = ('f4', 'f4', 'U15',
                      'f4', 'U15',
                      'U15', 'f4',
                      'U15', bool, 'f4',
                      'f4', 'O')

        if data_file is not None:
            table = Table.from_pandas(pd.read_csv(data_file, parse_dates=True))
        else:
            # -------------------------------------------------------------------------
            # Grab data from Mongo
            # -------------------------------------------------------------------------
            import pymongo
            from pocs.utils.database import PanMongo

            print('  Retrieving data from Mongo database')
            db = PanMongo()
            entries = [x for x in db.weather.find(
                {'date': {'$gt': self.start, '$lt': self.end}}).sort([
                    ('date', pymongo.ASCENDING)])]

            table = Table(names=col_names, dtype=col_dtypes)

            for entry in entries:
                pd.to_datetime(pd.Series(entry['date']))
                data = {'date': pd.to_datetime(entry['date'])}
                for key, val in entry['data'].items():
                    if key in col_names:
                        if key != 'date':
                            data[key] = val

                table.add_row(data)

        table.sort('date')
        return table

    def get_twilights(self, config=None):
        """ Determine sunrise and sunset times """
        print('  Determining sunrise, sunset, and twilight times')

        if config is None:
            from pocs.utils.config import load_config as pocs_config
            config = pocs_config()['location']

        location = EarthLocation(
            lat=config['latitude'],
            lon=config['longitude'],
            height=config['elevation'],
        )
        obs = Observer(location=location, name='PANOPTES',
                       timezone=config['timezone'])

        sunset = obs.sun_set_time(Time(self.start), which='next').datetime
        sunrise = obs.sun_rise_time(Time(self.start), which='next').datetime

        # Calculate and order twilights and set plotting alpha for each
        twilights = [(self.start, 'start', 0.0),
                     (sunset, 'sunset', 0.0),
                     (obs.twilight_evening_civil(Time(self.start),
                                                 which='next').datetime, 'ec', 0.1),
                     (obs.twilight_evening_nautical(Time(self.start),
                                                    which='next').datetime, 'en', 0.2),
                     (obs.twilight_evening_astronomical(Time(self.start),
                                                        which='next').datetime, 'ea', 0.3),
                     (obs.twilight_morning_astronomical(Time(self.start),
                                                        which='next').datetime, 'ma', 0.5),
                     (obs.twilight_morning_nautical(Time(self.start),
                                                    which='next').datetime, 'mn', 0.3),
                     (obs.twilight_morning_civil(Time(self.start),
                                                 which='next').datetime, 'mc', 0.2),
                     (sunrise, 'sunrise', 0.1),
                     ]

        twilights.sort(key=lambda x: x[0])
        final = {'sunset': 0.1, 'ec': 0.2, 'en': 0.3, 'ea': 0.5,
                 'ma': 0.3, 'mn': 0.2, 'mc': 0.1, 'sunrise': 0.0}
        twilights.append((self.end, 'end', final[twilights[-1][1]]))

        return twilights

    def plot_ambient_vs_time(self):
        """ Ambient Temperature vs Time """
        print('Plot Ambient Temperature vs. Time')

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
            label_time = self.end - tdelta(0, 6 * 60 * 60)
            label_temp = label_pos(self.cfg['amb_temp_limits'])
            plt.annotate('Low: {:4.1f} $^\circ$C, High: {:4.1f} $^\circ$C'.format(
                min_temp, max_temp),
                xy=(label_time, max_temp),
                xytext=(label_time, label_temp),
                size=16,
            )
        except Exception:
            pass

        plt.ylabel("Ambient Temp. (C)")
        plt.grid(which='major', color='k')
        plt.yticks(range(-100, 100, 10))
        plt.xlim(self.start, self.end)
        plt.ylim(self.cfg['amb_temp_limits'])
        t_axes.xaxis.set_major_locator(self.hours)
        t_axes.xaxis.set_major_formatter(self.hours_fmt)

        for i, twi in enumerate(self.twilights):
            if i > 0:
                plt.axvspan(self.twilights[i - 1][0], self.twilights[i][0],
                            ymin=0, ymax=1, color='blue', alpha=twi[2])

        if self.today:
            tlh_axes = plt.axes(self.plot_positions[0][1])
            plt.title('Last Hour')
            plt.plot_date(self.time, amb_temp, 'ko',
                          markersize=4, markeredgewidth=0,
                          drawstyle="default")
            plt.plot_date([self.date, self.date], self.cfg['amb_temp_limits'],
                          'g-', alpha=0.4)
            try:
                current_amb_temp = self.current_values['data']['ambient_temp_C']
                current_time = self.current_values['date']
                label_time = current_time - tdelta(0, 58 * 60)
                label_temp = label_pos(self.cfg['amb_temp_limits'])
                tlh_axes.annotate('Currently: {:.1f} $^\circ$C'.format(current_amb_temp),
                                  xy=(current_time, current_amb_temp),
                                  xytext=(label_time, label_temp),
                                  size=16,
                                  )
            except Exception:
                pass

            plt.grid(which='major', color='k')
            plt.yticks(range(-100, 100, 10))
            tlh_axes.xaxis.set_major_locator(self.mins)
            tlh_axes.xaxis.set_major_formatter(self.mins_fmt)
            tlh_axes.yaxis.set_ticklabels([])
            plt.xlim(self.lhstart, self.lhend)
            plt.ylim(self.cfg['amb_temp_limits'])

    def plot_cloudiness_vs_time(self):
        """ Cloudiness vs Time """
        print('Plot Temperature Difference vs. Time')
        td_axes = plt.axes(self.plot_positions[1][0])

        sky_temp_C = self.table['sky_temp_C']
        ambient_temp_C = self.table['ambient_temp_C']
        sky_condition = self.table['sky_condition']

        temp_diff = np.array(sky_temp_C) - np.array(ambient_temp_C)

        plt.plot_date(self.time, temp_diff, 'ko-', label='Cloudiness',
                      markersize=2, markeredgewidth=0,
                      drawstyle="default")

        wclear = [(x.strip() == 'Clear') for x in sky_condition.data]
        plt.fill_between(self.time, -60, temp_diff, where=wclear, color='green', alpha=0.5)

        wcloudy = [(x.strip() == 'Cloudy') for x in sky_condition.data]
        plt.fill_between(self.time, -60, temp_diff, where=wcloudy, color='yellow', alpha=0.5)

        wvcloudy = [(x.strip() == 'Very Cloudy') for x in sky_condition.data]
        plt.fill_between(self.time, -60, temp_diff, where=wvcloudy, color='red', alpha=0.5)

        if self.thresholds:
            st = self.thresholds.get('threshold_very_cloudy', None)
            if st:
                plt.plot_date([self.start, self.end], [st, st], 'r-',
                              markersize=2, markeredgewidth=0, alpha=0.3,
                              drawstyle="default")

        plt.ylabel("Cloudiness")
        plt.grid(which='major', color='k')
        plt.yticks(range(-100, 100, 10))
        plt.xlim(self.start, self.end)
        plt.ylim(self.cfg['cloudiness_limits'])
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
            plt.plot_date([self.date, self.date], self.cfg['cloudiness_limits'],
                          'g-', alpha=0.4)

            if self.thresholds:
                st = self.thresholds.get('threshold_very_cloudy', None)
                if st:
                    plt.plot_date([self.start, self.end], [st, st], 'r-',
                                  markersize=2, markeredgewidth=0, alpha=0.3,
                                  drawstyle="default")

            try:
                current_cloudiness = self.current_values['data']['sky_condition']
                current_time = self.current_values['date']
                label_time = current_time - tdelta(0, 58 * 60)
                label_temp = label_pos(self.cfg['cloudiness_limits'])
                tdlh_axes.annotate('Currently: {:s}'.format(current_cloudiness),
                                   xy=(current_time, label_temp),
                                   xytext=(label_time, label_temp),
                                   size=16,
                                   )
            except Exception:
                pass

            plt.grid(which='major', color='k')
            plt.yticks(range(-100, 100, 10))
            plt.ylim(self.cfg['cloudiness_limits'])
            plt.xlim(self.lhstart, self.lhend)
            tdlh_axes.xaxis.set_major_locator(self.mins)
            tdlh_axes.xaxis.set_major_formatter(self.mins_fmt)
            tdlh_axes.xaxis.set_ticklabels([])
            tdlh_axes.yaxis.set_ticklabels([])

    def plot_windspeed_vs_time(self):
        """ Windspeed vs Time """
        print('Plot Wind Speed vs. Time')
        w_axes = plt.axes(self.plot_positions[2][0])

        wind_speed = self.table['wind_speed_KPH']
        wind_mavg = moving_average(wind_speed, 9)
        matime, wind_mavg = moving_averagexy(self.time, wind_speed, 9)
        wind_condition = self.table['wind_condition']

        w_axes.plot_date(self.time, wind_speed, 'ko', alpha=0.5,
                         markersize=2, markeredgewidth=0,
                         drawstyle="default")
        w_axes.plot_date(matime, wind_mavg, 'b-',
                         label='Wind Speed',
                         markersize=3, markeredgewidth=0,
                         linewidth=3, alpha=0.5,
                         drawstyle="default")
        w_axes.plot_date([self.start, self.end], [0, 0], 'k-', ms=1)
        wcalm = [(x.strip() == 'Calm') for x in wind_condition.data]
        w_axes.fill_between(self.time, -5, wind_speed, where=wcalm,
                            color='green', alpha=0.5)
        wwindy = [(x.strip() == 'Windy') for x in wind_condition.data]
        w_axes.fill_between(self.time, -5, wind_speed, where=wwindy,
                            color='yellow', alpha=0.5)
        wvwindy = [(x.strip() == 'Very Windy') for x in wind_condition.data]
        w_axes.fill_between(self.time, -5, wind_speed, where=wvwindy,
                            color='red', alpha=0.5)

        if self.thresholds:
            st = self.thresholds.get('threshold_very_windy', None)
            if st:
                plt.plot_date([self.start, self.end], [st, st], 'r-',
                              markersize=2, markeredgewidth=0, alpha=0.3,
                              drawstyle="default")
            st = self.thresholds.get('threshold_very_gusty', None)
            if st:
                plt.plot_date([self.start, self.end], [st, st], 'r-',
                              markersize=2, markeredgewidth=0, alpha=0.3,
                              drawstyle="default")

        try:
            max_wind = max(wind_speed)
            label_time = self.end - tdelta(0, 5 * 60 * 60)
            label_wind = label_pos(self.cfg['wind_limits'])
            w_axes.annotate('Max Gust: {:.1f} (km/h)'.format(max_wind),
                            xy=(label_time, label_wind),
                            xytext=(label_time, label_wind),
                            size=16,
                            )
        except Exception:
            pass
        plt.ylabel("Wind (km/h)")
        plt.grid(which='major', color='k')
#         plt.yticks(range(0, 200, 10))

        plt.xlim(self.start, self.end)
        plt.ylim(self.cfg['wind_limits'])
        w_axes.xaxis.set_major_locator(self.hours)
        w_axes.xaxis.set_major_formatter(self.hours_fmt)
        w_axes.xaxis.set_ticklabels([])
        w_axes.yaxis.set_major_locator(MultipleLocator(20))
        w_axes.yaxis.set_major_formatter(FormatStrFormatter('%d'))
        w_axes.yaxis.set_minor_locator(MultipleLocator(10))

        if self.today:
            wlh_axes = plt.axes(self.plot_positions[2][1])
            wlh_axes.plot_date(self.time, wind_speed, 'ko', alpha=0.7,
                               markersize=4, markeredgewidth=0,
                               drawstyle="default")
            wlh_axes.plot_date(matime, wind_mavg, 'b-',
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
            plt.plot_date([self.date, self.date], self.cfg['wind_limits'],
                          'g-', alpha=0.4)

            if self.thresholds:
                st = self.thresholds.get('threshold_very_windy', None)
                if st:
                    plt.plot_date([self.start, self.end], [st, st], 'r-',
                                  markersize=2, markeredgewidth=0, alpha=0.3,
                                  drawstyle="default")
                st = self.thresholds.get('threshold_very_gusty', None)
                if st:
                    plt.plot_date([self.start, self.end], [st, st], 'r-',
                                  markersize=2, markeredgewidth=0, alpha=0.3,
                                  drawstyle="default")

            try:
                current_wind = self.current_values['data']['wind_speed_KPH']
                current_time = self.current_values['date']
                label_time = current_time - tdelta(0, 58 * 60)
                label_wind = label_pos(self.cfg['wind_limits'])
                wlh_axes.annotate('Currently: {:.0f} km/h'.format(current_wind),
                                  xy=(current_time, current_wind),
                                  xytext=(label_time, label_wind),
                                  size=16,
                                  )
            except Exception:
                pass
            plt.grid(which='major', color='k')
#             plt.yticks(range(0, 200, 10))
            plt.xlim(self.lhstart, self.lhend)
            plt.ylim(self.cfg['wind_limits'])
            wlh_axes.xaxis.set_major_locator(self.mins)
            wlh_axes.xaxis.set_major_formatter(self.mins_fmt)
            wlh_axes.xaxis.set_ticklabels([])
            wlh_axes.yaxis.set_ticklabels([])
            wlh_axes.yaxis.set_major_locator(MultipleLocator(20))
            wlh_axes.yaxis.set_major_formatter(FormatStrFormatter('%d'))
            wlh_axes.yaxis.set_minor_locator(MultipleLocator(10))

    def plot_rain_freq_vs_time(self):
        """ Rain Frequency vs Time """

        print('Plot Rain Frequency vs. Time')
        rf_axes = plt.axes(self.plot_positions[3][0])

        rf_value = self.table['rain_frequency']
        rain_condition = self.table['rain_condition']

        rf_axes.plot_date(self.time, rf_value, 'ko-', label='Rain',
                          markersize=2, markeredgewidth=0,
                          drawstyle="default")

        wdry = [(x.strip() == 'Dry') for x in rain_condition.data]
        rf_axes.fill_between(self.time, 0, rf_value, where=wdry,
                             color='green', alpha=0.5)
        wwet = [(x.strip() == 'Wet') for x in rain_condition.data]
        rf_axes.fill_between(self.time, 0, rf_value, where=wwet,
                             color='orange', alpha=0.5)
        wrain = [(x.strip() == 'Rain') for x in rain_condition.data]
        rf_axes.fill_between(self.time, 0, rf_value, where=wrain,
                             color='red', alpha=0.5)

        if self.thresholds:
            st = self.thresholds.get('threshold_wet', None)
            if st:
                plt.plot_date([self.start, self.end], [st, st], 'r-',
                              markersize=2, markeredgewidth=0, alpha=0.3,
                              drawstyle="default")

        plt.ylabel("Rain Sensor")
        plt.grid(which='major', color='k')
        plt.ylim(self.cfg['rain_limits'])
        plt.xlim(self.start, self.end)
        rf_axes.xaxis.set_major_locator(self.hours)
        rf_axes.xaxis.set_major_formatter(self.hours_fmt)
        rf_axes.xaxis.set_ticklabels([])

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
            plt.plot_date([self.date, self.date], self.cfg['rain_limits'],
                          'g-', alpha=0.4)
            if st:
                plt.plot_date([self.start, self.end], [st, st], 'r-',
                              markersize=2, markeredgewidth=0, alpha=0.3,
                              drawstyle="default")

            try:
                current_rain = self.current_values['data']['rain_condition']
                current_time = self.current_values['date']
                label_time = current_time - tdelta(0, 58 * 60)
                label_y = label_pos(self.cfg['rain_limits'])
                rflh_axes.annotate('Currently: {:s}'.format(current_rain),
                                   xy=(current_time, label_y),
                                   xytext=(label_time, label_y),
                                   size=16,
                                   )
            except Exception:
                pass
            plt.grid(which='major', color='k')
            plt.ylim(self.cfg['rain_limits'])
            plt.xlim(self.lhstart, self.lhend)
            rflh_axes.xaxis.set_major_locator(self.mins)
            rflh_axes.xaxis.set_major_formatter(self.mins_fmt)
            rflh_axes.xaxis.set_ticklabels([])
            rflh_axes.yaxis.set_ticklabels([])

    def plot_safety_vs_time(self):
        """ Plot Safety Values """

        print('Plot Safe/Unsafe vs. Time')
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
            plt.plot_date([self.date, self.date], [-0.1, 1.1],
                          'g-', alpha=0.4)
            try:
                safe = self.current_values['data']['safe']
                current_safe = {True: 'Safe', False: 'Unsafe'}[safe]
                current_time = self.current_values['date']
                label_time = current_time - tdelta(0, 58 * 60)
                label_y = 0.35
                safelh_axes.annotate('Currently: {:s}'.format(current_safe),
                                     xy=(current_time, label_y),
                                     xytext=(label_time, label_y),
                                     size=16,
                                     )
            except Exception:
                pass
            plt.ylim(-0.1, 1.1)
            plt.yticks([0, 1])
            plt.grid(which='major', color='k')
            plt.xlim(self.lhstart, self.lhend)
            safelh_axes.xaxis.set_major_locator(self.mins)
            safelh_axes.xaxis.set_major_formatter(self.mins_fmt)
            safelh_axes.xaxis.set_ticklabels([])
            safelh_axes.yaxis.set_ticklabels([])

    def plot_pwm_vs_time(self):
        """ Plot Heater values """

        print('Plot PWM Value vs. Time')
        pwm_axes = plt.axes(self.plot_positions[5][0])
        plt.ylabel("Heater (%)")
        plt.ylim(self.cfg['pwm_limits'])
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

        # Add line with same style as above in order to get in to the legend
        pwm_axes.plot_date([self.start, self.end], [-10, -10], 'ro-',
                           markersize=2, markeredgewidth=0,
                           label='RST Delta (C)')
        pwm_axes.plot_date(self.time, pwm_value, 'bo-', label='Heater',
                           markersize=2, markeredgewidth=0,
                           drawstyle="default")
        pwm_axes.xaxis.set_major_locator(self.hours)
        pwm_axes.xaxis.set_major_formatter(self.hours_fmt)
        pwm_axes.legend(loc='best')

        if self.today:
            pwmlh_axes = plt.axes(self.plot_positions[5][1])
            plt.ylim(self.cfg['pwm_limits'])
            plt.yticks([0, 25, 50, 75, 100])
            plt.xlim(self.lhstart, self.lhend)
            plt.grid(which='major', color='k')
            rstlh_axes = pwmlh_axes.twinx()
            plt.ylim(-1, 21)
            plt.xlim(self.lhstart, self.lhend)
            rstlh_axes.plot_date(self.time, rst_delta, 'ro-', alpha=0.5,
                                 label='RST Delta (C)',
                                 markersize=4, markeredgewidth=0,
                                 drawstyle="default")
            rstlh_axes.plot_date([self.date, self.date], [-1, 21],
                                 'g-', alpha=0.4)
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

            plot_filename = os.path.join(os.path.expandvars(
                '$PANDIR'), 'weather_plots', plot_filename)

        print('Saving Figure: {}'.format(plot_filename))
        self.fig.savefig(plot_filename, dpi=self.dpi, bbox_inches='tight', pad_inches=0.10)


def moving_average(interval, window_size):
    """ A simple moving average function """
    if window_size > len(interval):
        window_size = len(interval)
    window = np.ones(int(window_size)) / float(window_size)
    return np.convolve(interval, window, 'same')


def moving_averagexy(x, y, window_size):
    if window_size > len(y):
        window_size = len(y)
    if window_size % 2 == 0:
        window_size += 1
    nxtrim = int((window_size - 1) / 2)
    window = np.ones(int(window_size)) / float(window_size)
    yma = np.convolve(y, window, 'valid')
    xma = x[2 * nxtrim:]
    assert len(xma) == len(yma)
    return xma, yma


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description="Make a plot of the weather for a give date.")
    parser.add_argument("-d", "--date", type=str, dest="date", default=None,
                        help="UT Date to plot")
    parser.add_argument("-f", "--file", type=str, dest="data_file", default=None,
                        help="Filename for data file")
    parser.add_argument("-o", "--plot_file", type=str, dest="plot_file", default=None,
                        help="Filename for generated plot")
    parser.add_argument('--plotly-user', help="Username for plotly publishing")
    parser.add_argument('--plotly-api-key', help="API for plotly publishing")
    args = parser.parse_args()

    wp = WeatherPlotter(date_string=args.date, data_file=args.data_file)
    wp.make_plot(args.plot_file)

    if args.plotly_user and args.plotly_api_key:
        from plotly import plotly
        plotly.sign_in(args.plotly_user, args.plotly_api_key)
        url = plotly.plot_mpl(wp.fig)
        print('Plotly url: {}'.format(url))
