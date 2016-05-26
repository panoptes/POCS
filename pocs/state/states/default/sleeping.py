def on_enter(event_data):
    """ """
    pan = event_data.model

    pan.say("Another successful night!")
    pan.say("ZZzzzz...")
    pan = event_data.model

    # Wait until next night or shutdown
