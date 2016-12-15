def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.say("Recording all the data for the night (not really yet! TODO!!!).")

    # Cleanup existing observations
    for seq_time, observation in pocs.observatory.scheduler.observation_list.items():
        pocs.logger.debug("Housekeeping for {}".format(observation))
        del pocs.observatory.scheduler.observation_list[seq_time]

    pocs.say("Ok, looks like I'm done for the day. Time to get some sleep!")
    pocs.next_state = 'sleeping'
