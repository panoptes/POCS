#!/usr/bin/env python3
import argparse
import os

from astropy import units as u
from astropy.coordinates import AltAz
from astropy.coordinates import FK5

import time

from pocs import POCS
from pocs.utils import current_time


def main(num_pics=40, exp_time=30, eastern=True, western=False, simulator=None):
    pocs = POCS(simulator=simulator)
    pocs.logger.info('Performing drift align')
    pocs.initialize()

    mount = pocs.observatory.mount
    location = pocs.observatory.observer.location

    cam0 = pocs.observatory.cameras['Cam00']

    start_time = current_time(flatten=True)

    base_dir = '{}/images/drift_align'.format(os.getenv('PANDIR'))

    try:
        mount.unpark()
        mount.serial_query('set_sidereal_tracking')
        mount.slew_to_home()

        while not mount.is_home:
            time.sleep(3)

        if eastern:
            # Western horizon
            coord = get_coords(30, 102, location)
            mount.set_target_coordinates(coord)
            pocs.logger.info('Slewing to {}'.format(coord))
            mount.slew_to_target()

            while mount.is_slewing:
                time.sleep(3)

            pocs.logger.info('At Eastern Horizon, taking pics')

            # Take 40 x 30s images (20 min)
            for i in range(num_pics):
                fn = '{}/{}_alt_e_{:02d}.cr2'.format(base_dir, start_time, i)
                cam0.take_exposure(seconds=exp_time, filename=fn)
                pocs.logger.info('Taking picture {} of {}'.format(i, num_pics))

                time.sleep(exp_time)
                time.sleep(8)

        if western:
            # Western horizon
            coord = get_coords(20, 262.5, location)
            mount.set_target_coordinates(coord)
            pocs.logger.info('Slewing to {}'.format(coord))
            mount.slew_to_target()

            while mount.is_slewing:
                time.sleep(3)

            pocs.logger.info('At Western Horizon, taking pics')

            # Take 40 x 30s images (20 min)
            for i in range(num_pics):
                fn = '{}/{}_alt_w_{:02d}.cr2'.format(base_dir, start_time, i)
                cam0.take_exposure(seconds=exp_time, filename=fn)
                pocs.logger.info('Taking picture {} of {}'.format(i, num_pics))

                time.sleep(exp_time)
                time.sleep(8)

        # Meridian
        coord = get_coords(70.47, 180, location)
        mount.set_target_coordinates(coord)
        pocs.logger.info('Slewing to {}'.format(coord))
        mount.slew_to_target()

        while mount.is_slewing:
            time.sleep(3)

        pocs.logger.info('At Meridian, taking pics')

        # Take 40 x 30s images (20 min)
        for i in range(num_pics):
            fn = '{}/{}_az_{:02d}.cr2'.format(base_dir, start_time, i)
            cam0.take_exposure(seconds=exp_time, filename=fn)
            pocs.logger.info('Taking picture {} of {}'.format(i, num_pics))

            time.sleep(exp_time)
            time.sleep(8)

        mount.home_and_park()

        while not mount.is_slewing:
            time.sleep(3)

    except:
        pocs.logger.warning('Problem')
    finally:
        pocs.power_down()
        pocs.logger.info('Drift align complete')


def get_coords(alt, az, loc):
    altaz = AltAz(az=az * u.deg, alt=alt * u.deg,
                  obstime=current_time(), location=loc)
    coord = altaz.transform_to(FK5)
    return coord


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Perform a drift align',
        epilog="Don't forget to set the $POCS environment variable."
    )
    parser.add_argument('--simulator', action="append", default=['none'],
                        help='Run the unit in simulator mode. Possible values are: all, mount, camera, weather, night')
    parser.add_argument('--num_pics', default=40, type=int, help='Number of pictures to take')
    parser.add_argument('--exp_time', default=30, type=int, help='Number of pictures to take')
    parser.add_argument('--eastern', default=True, action='store_true', help='Take pictures of the Eastern Horizon')
    parser.add_argument('--western', default=False, action='store_true', help='Take pictures of the Western Horizon')

    args = parser.parse_args()

    main(**vars(args))
