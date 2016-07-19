def on_enter(event_data):
    """ """
    pan = event_data.model
    try:
        pan.say("I'm takin' it on home and then parking.")
        pan.observatory.mount.home_and_park()

        while not pan.observatory.mount.is_parked:
            pan.sleep()

        # The mount is currently not parking in correct position so we manually move it there.
        pan.observatory.mount.unpark()
        pan.observatory.mount.move_direction(direction='south', seconds=11.0)

        pan.next_state = 'parked'

    except Exception as e:
        pan.say("Yikes. Problem in parking: {}".format(e))
