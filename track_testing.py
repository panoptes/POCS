#!/usr/bin/env python

import yaml
import time

from astroquery.simbad import Simbad
from astropy.coordinates import SkyCoord
from astropy import units as u

import panoptes

def track(pan):

    interval = 2

    target = pan.scheduler.get_target(pan.observatory)

    c = target.position
    print("Moving to target: {} {}".format(target.name, c))

    for visit in target.visit:
        # Sidereal

        exp_time = visit.master_exptime

        # Set the mount to visit
        pan.observatory.mount.set_target_coordinates(c)
        pan.observatory.mount.slew_to_target()

        # Wait while slewing
        while pan.observatory.mount.is_slewing():
            pan.logger.debug("Mount is slewing. Sleeping for two seconds...")
            time.sleep(interval)

        with open(tracking_file, 'w+') as f:
            print("{}".format('*' * 20), file=f, flush=True)
            print("Target Coords: {}\nMount Commands: {}\nExp Time: {}".format(
            	target.position, '', exp_time
            	),
                file=f, flush=True)

            line = '\t'.join(['local_date', 'local_time', 'sidereal_time', 'ra', 'dec', 'alt', 'az', 'pier_position'])
            print(line, file=f, flush=True)

            pan.logger.info("Exposing for {} seconds".format(exp_time))

            # Track for exp_time, reporting along the way
            while exp_time > 0:
                alt = pan.observatory.mount.serial_query('get_alt')
                az = pan.observatory.mount.serial_query('get_az')

                ra = pan.observatory.mount.serial_query('get_ra')
                dec = pan.observatory.mount.serial_query('get_dec')

                local_time = pan.observatory.mount.serial_query('get_local_time')
                local_date = pan.observatory.mount.serial_query('get_local_date')
                sidereal_time = pan.observatory.mount.serial_query('get_sidereal_time')

                pier_position = pan.observatory.mount.pier_position()

                line = '\t'.join([local_date, local_time, sidereal_time, ra, dec, alt, az, pier_position])
                print(line, file=f, flush=True)

                time.sleep(interval)
                exp_time -= interval * u.s
                pan.logger.info("Exposing for {} more seconds".format(exp_time))

    pan.observatory.mount.slew_to_home()


if __name__ == '__main__':

    tracking_file = 'tracking_log.txt'

    with panoptes.Panoptes(connect_on_startup=True) as pan:
        track(pan)

    """
-Acquire target
	- track 1 hr sidereal
	- query ra for similar
- Acquire target
	- track 1 hr custom ra rate
	- query ra/dec
- Acquire target
	- track 1 hr custom dec rate
	- query ra/dec
	"""
