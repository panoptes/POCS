from ....utils import current_time


def on_enter(event_data):
    """
    In the `scheduling` state we attempt to find a target using our scheduler. If target is found,
    make sure that the target is up right now (the scheduler should have taken care of this). If
    observable, set the mount to the target and calls `start_slewing` to begin slew.

    If no observable targets are available, `park` the unit.
    """
    pan = event_data.model
    pan.say("Ok, I'm finding something good to look at...")

    # Get the next target
    try:
        target = pan.observatory.get_target()
        pan.logger.info("Target: {}".format(target))
    except Exception as e:
        pan.logger.warning("Error in scheduling: {}".format(e))

    if target is not None:
        pan.say("Got it! I'm going to check out: {}".format(target.name))

        pan.logger.debug("Setting Target coords: {}".format(target))
        has_target = pan.observatory.mount.set_target_coordinates(target)

        # target_ha = pan.observatory.scheduler.target_hour_angle(current_time(), target)

    else:
        pan.say("No valid targets found. Can't schedule. Going to park.")

    # If we have a target, start slewing
    pan.logger.debug("Has target: {}".format(has_target))
    if has_target:
        pan.logger.debug("Mount set to target {}".format(target))
        pan.next_state = 'slewing'
    else:
        pan.logger.warning("Target not properly set. Parking.")
