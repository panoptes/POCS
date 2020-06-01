from panoptes.utils import error


def on_enter(event_data):
    """
    In the `scheduling` state we attempt to find a field using our scheduler. If field is found,
    make sure that the field is up right now (the scheduler should have taken care of this). If
    observable, set the mount to the field and calls `start_slewing` to begin slew.

    If no observable targets are available, `park` the unit.
    """
    pocs = event_data.model
    pocs.next_state = 'parking'

    if pocs.run_once and len(pocs.observatory.scheduler.observed_list) > 0:
        pocs.say('Looks like we only wanted to run once, parking now')
    else:

        pocs.say("Ok, I'm finding something good to look at...")

        existing_observation = pocs.observatory.current_observation

        # Get the next observation
        try:
            observation = pocs.observatory.get_observation()
            pocs.logger.info(f"Observation: {observation}")
        except error.NoObservation:
            pocs.say("No valid observations found. Can't schedule. Going to park.")
        except Exception as e:
            pocs.logger.warning(f"Error in scheduling: {e!r}")
        else:

            if existing_observation and observation.name == existing_observation.name:
                pocs.say(f"I'm sticking with {observation.name}")

                # Make sure we are using existing observation (with pointing image)
                pocs.observatory.current_observation = existing_observation
                pocs.next_state = 'tracking'
            else:
                pocs.say(f"Got it! I'm going to check out: {observation.name}")

                pocs.logger.debug(f"Setting Observation coords: {observation.field}")
                if pocs.observatory.mount.set_target_coordinates(observation.field):
                    pocs.next_state = 'slewing'
                else:
                    pocs.logger.warning("Field not properly set. Parking.")
