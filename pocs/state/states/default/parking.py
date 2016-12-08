def on_enter(event_data):
    """ """
    pocs = event_data.model
    try:
        # Clear any current observation
        pocs.observatory.current_observation = None

        pocs.say("I'm takin' it on home and then parking.")
        pocs.observatory.mount.home_and_park()

        pocs.next_state = 'parked'

    except Exception as e:
        pocs.say("Yikes. Problem in parking: {}".format(e))
