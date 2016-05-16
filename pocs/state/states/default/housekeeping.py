def on_enter(event_data):
    """ """
    pan = event_data.model
    pan.say("Recording all the data for the night (not really yet! TODO!!!).")

    pan.say("Ok, looks like I'm done for the day. Time to get some sleep!")
    pan.sleep()
