from astropy import units as u
import time


def on_enter(event_data):
    """ The unit is tracking the target. Proceed to observations. """
    pan = event_data.model
    pan.say("I'm now tracking the target.")

    target = pan.observatory.current_target

    # Get the delay for the RA and Dec and adjust mount accordingly.
    for d in ['ra', 'dec']:
        key = '{}_ms_offset'.format(d)
        pan.logger.debug("{}".format(key))

        # I'm not sure about this...
        if target.current_visit is None or target.current_visit.exp_num < 1:
            continue

        if key in target._offset_info:
            key = '{}_ms_offset'.format(d)

            # Add some offset to the offset
            ms_offset = int(target._offset_info.get(key, 0 * u.ms).value)
            pan.logger.debug("Checking {} {}".format(key, ms_offset))

            # Only adjust a reasonable offset
            if abs(ms_offset) < 10.0:
                pan.logger.debug("Offset not large enough")
                continue

            # One-fourth of time. FIXME
            processing_time_delay = int(ms_offset / 4)
            pan.logger.debug("Processing time delay: {}".format(processing_time_delay))

            ms_offset = ms_offset + processing_time_delay
            pan.logger.debug("Total offset: {}".format(ms_offset))

            # This hurts me to look at
            if d == 'ra':
                if ms_offset > 0:
                    direction = 'west'
                else:
                    ms_offset = abs(ms_offset)
                    direction = 'east'
            elif d == 'dec':
                if ms_offset > 0:
                    direction = 'south'
                else:
                    ms_offset = abs(ms_offset)
                    direction = 'north'

            pan.say("I'm adjusting the tracking by just a bit to the {}.".format(direction))

            move_dir = 'move_ms_{}'.format(direction)
            move_ms = "{:05.0f}".format(ms_offset)
            pan.logger.debug("Adjusting tracking by {} to direction {}".format(move_ms, move_dir))

            pan.observatory.mount.serial_query(move_dir, move_ms)

            # The above is a non-blocking command but if we issue the next command (via the for loop)
            # then it will override the above, so we manually block for one second
            time.sleep(ms_offset / 1000)

    # Reset offset_info
    target._offset_info = {}

    pan.goto('observe')
