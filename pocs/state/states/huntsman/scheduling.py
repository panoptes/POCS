from pocs.utils import error


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
            pocs.logger.info("Observation: {}".format(observation))

            if pocs.force_reschedule:
                pocs.force_reschedule = False

        except error.NoObservation as e:
            pocs.say("No valid observations found. Can't schedule. Going to park.")
        except Exception as e:
            pocs.logger.warning("Error in scheduling: {}".format(e))
        else:

            if observation != existing_observation:
                pocs.say("Got it! I'm going to check out: {}".format(observation.name))

                pocs.logger.debug("Setting Observation coords: {}".format(observation.field))
                if pocs.observatory.mount.set_target_coordinates(observation.field):
                    pocs.next_state = 'preparing'
                else:
                    pocs.logger.warning("Field not properly set. Parking.")
            else:
                pocs.say("I'm sticking with {}".format(observation.name))
                pocs.next_state = 'tracking'
