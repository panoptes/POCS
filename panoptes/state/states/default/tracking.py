from astropy import units as u
import time


def on_enter(event_data):
    """ The unit is tracking the target. Proceed to observations. """
    pan = event_data.model
    pan.say("Checking our tracking")

    target = pan.observatory.current_target

    # Make sure we have a target
    if target.current_visit is not None:

        # Get the delay for the RA and Dec and adjust mount accordingly.
        for direction in ['dec', 'ra']:

            # Adjust the rate
            # Adjust RA rate. NOTE: Dec not implemented for iOptron yet
            if direction == 'ra':
                delta_ra_rate = target._offset_info.get('delta_ra_rate', 0.0)
                if delta_ra_rate != 0.0:
                    pan.logger.debug("Delta RA Rate: {}".format(delta_ra_rate))
                    pan.say("I'm adjusting the tracking rate")
                    pan.observatory.mount.set_tracking_rate(delta=delta_ra_rate)
                    time.sleep(0.5)  # Make sure command goes through

            # delta_dec_rate = target._offset_info.get('delta_dec_rate', 0.0)
            # pan.logger.debug("Delta Dec Rate: {}".format(delta_dec_rate))

            # Now adjust for existing offset
            key = '{}_ms_offset'.format(direction)
            pan.logger.debug("{}".format(key))

            if key in target._offset_info:
                pan.logger.debug("Check offset values for {} {}".format(direction, target._offset_info))

                # Add some offset to the offset
                ms_offset = target._offset_info.get(key, 0)
                if isinstance(ms_offset, u.Quantity):
                    ms_offset = ms_offset.value

                ms_offset = int(ms_offset)
                pan.logger.debug("Checking {} {}".format(key, ms_offset))

                # Only adjust a reasonable offset
                if abs(ms_offset) > 20.0 and abs(ms_offset) <= 5000.0:

                    # One-fourth of time. FIXME
                    processing_time_delay = int(ms_offset / 4)
                    pan.logger.debug("Processing time delay: {}".format(processing_time_delay))

                    ms_offset = ms_offset + processing_time_delay
                    pan.logger.debug("Total offset: {}".format(ms_offset))

                    if direction == 'ra':
                        if ms_offset > 0:
                            direction_cardinal = 'east'
                        else:
                            direction_cardinal = 'west'
                    elif direction == 'dec':
                        if ms_offset > 0:
                            direction_cardinal = 'south'
                        else:
                            direction_cardinal = 'north'

                    pan.say("I'm adjusting the tracking by just a bit to the {}.".format(direction_cardinal))
                    # Now that we have direction, all ms are positive
                    ms_offset = abs(ms_offset)

                    move_dir = 'move_ms_{}'.format(direction_cardinal)
                    move_ms = "{:05.0f}".format(ms_offset)
                    pan.logger.debug("Adjusting tracking by {} to direction {}".format(move_ms, move_dir))

                    pan.observatory.mount.serial_query(move_dir, move_ms)

                    # The above is a non-blocking command but if we issue the next command (via the for loop)
                    # then it will override the above, so we manually block for one second
                    time.sleep(abs(ms_offset) / 1000)
                else:
                    pan.logger.debug("Offset not in range")

        pan.say("Done with tracking adjustment, going to observe")

    # Reset offset_info
    target._offset_info = {}

    pan.say("Tracking looks good, I'm going to observe")
    pan.goto('observe')
