
def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.say("I'm parked now. Phew.")

    if pocs.run_once is True:
        pocs.say("Done running loop, going to clean up and sleep!")
        pocs.next_state = 'housekeeping'
    elif pocs.should_retry is False:
        pocs.say("Done with retrying loop, going to clean up and sleep!")
        pocs.next_state = 'housekeeping'
    else:
        has_valid_observations = pocs.observatory.scheduler.has_valid_observations

        if has_valid_observations:
            if pocs.is_safe():
                pocs.say("Things look okay for now. I'm going to try again.")
                pocs.next_state = 'ready'
            else:  # Normal end of night
                pocs.say("Cleaning up for the night!")
                pocs.next_state = 'housekeeping'
        else:
            pocs.say("No observations found.")
            # TODO Should check if we are close to morning and if so do some morning
            # calibration frames rather than just waiting for 30 minutes then shutting down.
            pocs.say("Going to stay parked for half an hour then will try again.")

            while True:
                pocs.sleep(delay=1800)  # 30 minutes = 1800 seconds

                # We might have shutdown during previous sleep.
                if not pocs.connected:
                    break
                elif pocs.is_safe():
                    pocs.reset_observing_run()
                    pocs.next_state = 'ready'
                    break
                elif pocs.is_dark() is False:
                    pocs.say("Looks like it's not dark anymore. Going to clean up.")
                    pocs.next_state = 'housekeeping'
                    break
                else:
                    pocs.say("Seems to be bad weather. I'll wait another 30 minutes.")
