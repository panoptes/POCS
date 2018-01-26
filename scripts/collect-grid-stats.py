#!/usr/bin/env python

import os
import json 
from time import sleep
from astropy.coordinates import SkyCoord
from astropy import units as u

from pocs.core import POCS
from pocs.utils import current_time
from pocs.utils.database import PanMongo
from pocs.utils import images as img_utils

def main(num_images=3, exp_time=30, without_camera=False, daytime=False):
    db = PanMongo()

    has = [4, 2, 0.25, 23.75, 22, 20] * u.hourangle
    decs = [30, 15, 0, -15, -30] * u.deg

    readings = list()

    # Image names will all contain base time
    t0 = current_time(flatten=True)

    print("Setting up POCS")
    simulator = list()
    if without_camera:
        simulator.append('camera')
    if daytime:
        simulator.append('night')

    if len(simulator) > 0:
        pocs = POCS(messaging=True,simulator=simulator)
    else:
        pocs = POCS(messaging=True)

    pocs.initialize()
    mount = pocs.observatory.mount

    # Quick convenience for getting accelerometer values
    get_accel = lambda : db.current.find({'type': 'environment'}).next()['data']['camera_board']

    def get_stats(state=None):
        stats = pocs.status()
        try:
            stats.update(get_accel())
        except KeyError:
            pass

        if state is not None:
            stats.update({'state': state})

        readings.append(stats)

    pocs.say("Unparking mount and slewing to home")
    get_stats(state='parking')
    mount.unpark()

    mount.slew_to_home()
    while mount.is_home is False:
        print('.', end='')
        sleep(1)

    get_stats(state='home')
    pocs.say("At home")


    i = 0
    for ha in has:
        for dec in decs:
            if pocs.is_safe() is False:
                break

            # Get LST
            t = current_time()
            t.location = pocs.observatory.earth_location
            lst = t.sidereal_time('apparent')

            # Make RA/Dec coordinate from HA
            ra = lst - ha
            coord = SkyCoord(ra, dec)

            pocs.say("Going to coord: {} {}".format(ra, dec))
            mount.set_target_coordinates(coord)
            mount.slew_to_target()

            while mount.is_tracking is False:
                get_stats(state='slewing')
                sleep(1)

            if without_camera is False:
                files = list()
                for img_num in range(int(num_images)):
                    if pocs.is_safe() is False:
                        break
                    pocs.say("Taking {}/{} on {}/{}".format(img_num + 1, num_images, i + 1, len(has) * len(decs)))
                    for cam_nam, cam in pocs.observatory.cameras.items():
                        fn = '/var/panoptes/images/temp/{}_{}_{:02d}_{:02d}.cr2'.format(t0, cam_nam, i, img_num)
                        cam.take_exposure(seconds=exp_time, filename=fn)
                        files.append(fn)

                    while not all([os.path.exists(f) for f in files]):
                        get_stats(state='tracking')
                        sleep(2)

                    img_utils.make_pretty_image(files[-1])
                    get_stats(state='tracking')
                    sleep(4)
                    get_stats(state='tracking')

                for f in files:
                    os.remove(f)
            else:
                secs = 0
                pocs.say("Faking on {}/{}".format(i + 1, len(has) * len(decs)))
                while secs < int(exp_time):
                    get_stats(state='tracking')
                    secs += 2

            i += 1

    get_stats(state='slewing')
    pocs.say("Going home and parking")
    mount.home_and_park()
    get_stats(state='parking')

    pocs.say("Writing {} records".format(len(readings)))
    with open('stats.json', 'w+') as f:
        f.write(json.dumps(readings))

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="Take sky grid and collect stats")
    parser.add_argument('--num-images', default=3, help='Number of exposures at each location, defaults to 3')
    parser.add_argument('--exp-time', default=30, help='Exposure time, defaults to 30 seconds')
    parser.add_argument('--without-camera', default=False, action='store_true', help='Take pictures')
    parser.add_argument('--daytime', default=False, action='store_true', help='Run in day')

    args = parser.parse_args()

    main(**vars(args))
