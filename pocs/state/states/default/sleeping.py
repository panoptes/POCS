def on_enter(event_data):
    """ """
    pocs = event_data.model

    pocs.say("Another successful night!")
    pocs.say("ZZzzzz...")

    pocs.next_state = 'ready'

    # Wait until next night or shutdown
    pocs.wait_until_safe()
