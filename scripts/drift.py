
# coding: utf-8

from matplotlib import pyplot as plt
import numpy as np
import glob
import datetime

import pandas as pd

plt.style.use('ggplot')


# Load the PANOPTES module dir
import sys
sys.path.append('/var/panoptes/POCS')


from panoptes.utils.images import *


dir1 = '/var/panoptes/images/20160113/*.cr2'


cr2_files = glob.glob(dir1)
cr2_files.sort()
cr2_files


def compare_files(f0, f1, compare=False):
    d1 = read_image_data(f0)
    d2 = read_image_data(f1)
    offset = measure_offset(d1, d2)

    exif_01 = read_exif(f1)

    fmt = '%a %b %d %H:%M:%S %Y'
    t = datetime.datetime.strptime(exif_01.get('Timestamp'), fmt)

    return (offset.get('delta_ra').value, offset.get('delta_dec').value, t)


compare_files(cr2_files[0], cr2_files[1])


comparison = []

for i in np.arange(len(cr2_files)):
    if i < len(cr2_files) - 1:
        comparison.append(compare_files(cr2_files[i], cr2_files[i + 1]))


comparison


x0 = [x[0] for x in comparison]
y0 = [x[1] * -1 for x in comparison]

dates = [x[-1] for x in comparison]
dt_index = pd.DatetimeIndex(dates)
dt_index


x0_offset = pd.DataFrame(x0, dt_index)
y0_offset = pd.DataFrame(y0, dt_index)


series = pd.concat([x0_offset, y0_offset], axis=1)
series.columns = ["Gee $\Delta{x}$", "Gee $\Delta{y}$"]

series.index = dt_index


series


series.plot(figsize=(3, 1), title="Periodic Error")
plt.legend(loc=1)
plt.savefig('drift.png')
plt.show()
