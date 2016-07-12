def on_enter(event_data):
    """
    Once in the `ready` state our unit has been initialized successfully. The next step is to
    schedule something for the night.
    """
    pan = event_data.model

    pan.say("Ok, I'm all set up and ready to go!")

    pan.observatory.mount.unpark()

    pan.next_state = 'scheduling'
