from pocs.utils import error


def on_enter(event_data):
    """
    In the `scheduling` state we attempt to find a target using our scheduler. If target is found,
    make sure that the target is up right now (the scheduler should have taken care of this). If
    observable, set the mount to the target and calls `start_slewing` to begin slew.

    If no observable targets are available, `park` the unit.
    """
    pocs = event_data.model
    pocs.say("Ok, I'm finding something good to look at...")

    # Get the next observation
    try:
        observation = pocs.observatory.get_observation()
        pocs.logger.info("Observation: {}".format(observation))
    except error.NoObservation as e:
        pocs.say("No valid observations found. Can't schedule. Going to park.")
    except Exception as e:
        pocs.logger.warning("Error in scheduling: {}".format(e))
    else:
        pocs.say("Got it! I'm going to check out: {}".format(observation.name))

        pocs.logger.debug("Setting Observation coords: {}".format(observation.field))
        has_target = pocs.observatory.mount.set_target_coordinates(observation.field)
        pocs.logger.debug("Has target: {}".format(has_target))

        if has_target:
            pocs.logger.debug("Mount set to target {}".format(observation.field))
            pocs.next_state = 'slewing'
        else:
            pocs.logger.warning("Target not properly set. Parking.")
            pocs.next_state = 'parking'
