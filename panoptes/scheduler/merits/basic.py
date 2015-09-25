import ephem
from ..observatory import Observatory

def observable(target, observatory):
    """Merit function to evaluate if a target is observable.
    Args:
        target (Target): Target object to evaluate.
        observatory (Observatory): The observatory object for which to evaluate
        the target.
    Returns:
        (1, observable): Returns 1 as the merit (a merit value of 1 indicates
        that all elevations are equally meritorious).  Will return True for
        observable if the target is observable or return Fale if not (which
        vetoes the target.
    """
    assert isinstance(observatory, Observatory)
    site = observatory.site
    assert isinstance(site, ephem.Observer)
    assert isinstance(target, Target)

    target_ra = '{}:{}:{}'.format(
        target.position.ra.hms.h,
        target.position.ra.hms.m,
        target.position.ra.hms.s,
    )
    target_dec = '{}:{}:{}'.format(
        target.position.dec.dms.d,
        target.position.dec.dms.m,
        target.position.dec.dms.s,
    )

    ephemdb = '{},f|M,{},{},'.format(target.name, target_ra, target_dec )
    fixedbody = ephem.readdb(ephemdb)

    visit_duration = target.estimate_visit_duration()

    observatory.logger.debug('ra:\t\t{}'.format(target_ra))
    observatory.logger.debug('dec:\t\t{}'.format(target_dec))

    observatory.logger.debug('target:\t\t{}'.format(target.name))
    observatory.logger.debug('\tduration:\t{}'.format(visit_duration))

    # Loop through duration of observation and see if any position is
    # unobservable.  This loop is needed in case the shape of the horizon is
    # complex and some values in between the starting and ending points are
    # rejected even though the starting and ending points are ok.  The time
    # step is arbitrarily chosen as 30 seconds.
    time_step = 30

    duration = int(visit_duration.to(u.s).value) + time_step

    start_time = datetime.datetime.utcnow()
    observatory.logger.debug('\tstart_time:\t{}'.format(start_time))

    site.date = ephem.Date(start_time)

    for dt in np.arange(0, duration, time_step):
        observatory.logger.debug('')

        # Add the time_step to date
        site.date = site.date + (time_step * ephem.second)
        observatory.logger.debug('\tdate:\t\t{}'.format(site.date))

        # Recompute
        fixedbody.compute(site)

        # Convert to astropy coords
        alt = float(fixedbody.alt) * u.radian
        az = float(fixedbody.az) * u.radian
        observatory.logger.debug('\talt:\t\t{:0.3f}\t{:0.3f}'.format(alt, alt.to(u.deg)))
        observatory.logger.debug('\taz:\t\t{:0.3f}\t{:0.3f}'.format(az, az.to(u.deg)))

        if not observatory.horizon(alt, az):
            return (1, False)

    # Return 1 as merit if none of the time steps returned False (unobservable)
    return (1, True)
