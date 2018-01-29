
def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.say("I'm parked now. Phew.")

    has_valid_observations = pocs.observatory.scheduler.has_valid_observations

    if has_valid_observations:
        if pocs.is_safe():
            if pocs.should_retry is False or pocs.run_once is True:
                pocs.say("Done retrying for this run, going to clean up and shut down!")
                pocs.next_state = 'housekeeping'
            else:
                pocs.say("Things look okay for now. I'm going to try again.")
                pocs.next_state = 'ready'
        else:
            pocs.say("Cleaning up for the night!")
            pocs.next_state = 'housekeeping'
    else:
        if pocs.run_once is False:
            pocs.say("No observations found. Going to stay parked for an hour then try again.")
            pocs.sleep(delay=3600)  # 1 hour = 3600 seconds

            pocs.reset_observing_run()
            pocs.next_state = 'ready'
        else:
            pocs.say("Only wanted to run once so cleaning up!")
            pocs.next_state = 'housekeeping'
