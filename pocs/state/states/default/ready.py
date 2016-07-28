def on_enter(event_data):
    """
    Once in the `ready` state our unit has been initialized successfully. The next step is to
    schedule something for the night.
    """
    pocs = event_data.model

    pocs.say("Ok, I'm all set up and ready to go!")

    # When we first start the machine it might not be dark, so we wait
    if not pocs.is_safe():
        pocs.say("Looks like it is not safe out there. I'll just wait for a bit")
        pocs.wait_until_safe()

    pocs.observatory.mount.unpark()

    pocs.next_state = 'scheduling'
