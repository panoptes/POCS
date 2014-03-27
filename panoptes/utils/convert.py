class Convert():
    """
        Convert convenience functions
    """

    def __init__(self):

        # Attach to the logger
        self.logger = Logger()

    def HA_to_Dec(self,J2000_coordinate, site):
        """
            HA to Dec
        """
        assert type(J2000_coordinate) == coords.FK5
        assert J2000_coordinate.equinox.value == 'J2000.000'

        ## Coordinate precessed to Jnow (as an astropy coordinate object)
        Jnow_coordinate = J2000_coordinate.precess_to(Time.now())

        ## Coordinate as a pyephem coordinate (J2000)
        RA_string, Dec_string = J2000_coordinate.to_string(precision=2, sep=':').split(' ')
        ephem_coordinate = ephem.FixedBody(RA_string, Dec_string, epoch=ephem.J2000)
        ephem_coordinate = ephem.readdb('Polaris,f|M|F7,{},{},2.02,2000'.format(RA_string, Dec_string))
        ephem_coordinate.compute(site)

        HourAngle = ephem_coordinate.ra - site.sidereal_time()

        self.logger.info('Astropy J2000: {}'.format(J2000_coordinate.to_string(precision=2, sep=':')))
        self.logger.info('pyephem Jnow:  {} {}'.format(ephem_coordinate.ra, ephem_coordinate.dec))
        self.logger.info('RA decimal = {:f}'.format(ephem_coordinate.ra))
        self.logger.info('LST decimal = {:f}'.format(site.sidereal_time()))
        self.logger.info('HA decimal = {:f}'.format(HourAngle))

        return HourAngle