from ....utils import current_time


def on_enter(event_data):
    """
    In the `scheduling` state we attempt to find a target using our scheduler. If target is found,
    make sure that the target is up right now (the scheduler should have taken care of this). If
    observable, set the mount to the target and calls `slew_to_target` to begin slew.

    If no observable targets are available, `park` the unit.
    """
    pan = event_data.model
    pan.say("Ok, I'm finding something good to look at...")

    # Get the next target
    try:
        target = pan.observatory.get_target()
        pan.logger.info("Target: {}".format(target))
    except Exception as e:
        pan.logger.error("Error in scheduling: {}".format(e))

    # Assign the _method_
    next_state = 'park'

    if target is not None:

        pan.say("Got it! I'm going to check out: {}".format(target.name))

        # Check if target is up
        if pan.observatory.scheduler.target_is_up(current_time(), target):
            pan.logger.debug("Setting Target coords: {}".format(target))

            has_target = pan.observatory.mount.set_target_coordinates(target)

            if has_target:
                pan.logger.debug("Mount set to target.".format(target))
                next_state = 'slew_to_target'
            else:
                pan.logger.warning("Target not properly set. Parking.")
        else:
            pan.say("That's weird, I have a target that is not up. Parking.")
    else:
        pan.say("No valid targets found. Can't schedule. Going to park.")

    pan.goto(next_state)
