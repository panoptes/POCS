
def on_enter(event_data):
    """
    In the `scheduling` state we attempt to find a target using our scheduler. If target is found,
    make sure that the target is up right now (the scheduler should have taken care of this). If
    observable, set the mount to the target and calls `start_slewing` to begin slew.

    If no observable targets are available, `park` the unit.
    """
    pocs = event_data.model
    pocs.say("Ok, I'm finding something good to look at...")

    # Get the next target
    try:
        target = pocs.observatory.get_target()
        pocs.logger.info("Target: {}".format(target))
    except Exception as e:
        pocs.logger.warning("Error in scheduling: {}".format(e))

    if target is not None:
        pocs.say("Got it! I'm going to check out: {}".format(target.name))
        pocs.send_message({'target': {
            'target_name': target.name,
            'target_ra': target.ra.value,
            'target_ha': target.ra.value,
            'target_dec': target.dec.value,
        }}, channel='TARGET')

        pocs.logger.debug("Setting Target coords: {}".format(target))
        has_target = pocs.observatory.mount.set_target_coordinates(target)

        # target_ha = pocs.observatory.scheduler.target_hour_angle(current_time(), target)

    else:
        pocs.say("No valid targets found. Can't schedule. Going to park.")

    # If we have a target, start slewing
    pocs.logger.debug("Has target: {}".format(has_target))
    if has_target:
        pocs.logger.debug("Mount set to target {}".format(target))
        pocs.next_state = 'slewing'
    else:
        pocs.logger.warning("Target not properly set. Parking.")
