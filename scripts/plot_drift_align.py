import pandas
import seaborn

from astropy import units as u
from matplotlib import markers
from matplotlib import pyplot as plt

from pocs.utils.database import PanMongo

seaborn.set_style('darkgrid')

db = PanMongo()

color = {
    'alt_east': 'green',
    'alt_west': 'blue',
    'az_east': 'red',
    'az_west': 'purple'
}

data = {}
info = {}

# Lookup all the dates
dates = db.drift_align.distinct('start_time')
dates = dict(zip(range(len(dates)), dates))

# Find out which dates to use
for k, v in dates.items():
    print('{:2d}: {}'.format(k, v))

text = input('Remove number(s) from set: ')

if text > '':
    for opt in text.split(' '):
        # Break apart range
        if '-' in opt:
            start, end = opt.split('-')
            for i in range(int(start), int(end) + 1):
                del dates[i]
        else:
            opt = int(opt)

            if opt in dates:
                del dates[opt]

for start_time in dates.values():
    print("Adding data for {}".format(start_time))
    for rec in db.drift_align.find({'start_time': start_time}).sort([('data.FILENAME', 1)]):
        date, test, direction, cam_name, count = rec['data']['FILENAME'].split('_')

        name = '{}_{}'.format(test.lower(), direction.lower())

        if name not in data:
            data[name] = {}
            info[name] = {}

        if date not in data[name]:
            info[name][date] = {
                'Cam00': {'time': [], 'dec': []},
                'Cam01': {'time': [], 'dec': []}
            }
            data[name][date] = {
                'Cam00': {'d_dec': [], 'dt': []},
                'Cam01': {'d_dec': [], 'dt': []}
            }

        dec = rec['data']['CRVAL2'] * u.degree
        t = pandas.to_datetime(rec['data']['DATE-OBS'])

        try:
            dec0 = info[name][date][cam_name]['dec'][0]
            t0 = info[name][date][cam_name]['time'][0]
        except Exception:
            dec0 = dec
            t0 = t

        info[name][date][cam_name]['dec'].append(dec)
        info[name][date][cam_name]['time'].append(t)

        data[name][date][cam_name]['d_dec'].append((dec - dec0).to(u.arcsec).value)
        data[name][date][cam_name]['dt'].append((t - t0).seconds)


f, ax = plt.subplots(2, 1, figsize=(15, 9))

for name in data.keys():
    for j, date in enumerate(data[name].keys()):
        for camera in data[name][date].keys():
            if camera == 'Cam00':
                line = '--'
            else:
                line = '-'

            if 'alt' in name:
                i = 0
                which = 'Altitude'
            else:
                i = 1
                which = 'Azimuth'

            ax[i].plot(
                data[name][date][camera]['dt'], data[name][date][camera][
                    'd_dec'], marker=markers.MarkerStyle.filled_markers[j],
                ms=6, markerfacecolor='None', markeredgewidth=1, markeredgecolor=color[name], alpha=0.5,
                ls=line, color=color[name], label='{} {} {}'.format(camera, name, date.split('T')[-1])
            )
            legend = ax[i].legend(bbox_to_anchor=(1, 1), loc='best', ncol=1)
            legend.get_frame().set_facecolor('#00FFCC')

            ax[i].set_ylabel('$\Delta$ Dec [arcsec]')

            ax[i].set_title('Drift Align - {}'.format(which))

plt.xlabel('$\Delta$ t [seconds]')
plt.savefig('drift_align.png')
