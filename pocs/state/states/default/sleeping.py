def on_enter(event_data):
    """ """
    pan = event_data.model

    pan.say("Another successful night!")
    pan.say("ZZzzzz...")

    pan.next_state = 'ready'

    # Wait until next night or shutdown
    pan.wait_until_safe()
