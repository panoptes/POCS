
def on_enter(self, event_data):
    """ """
    self.say("I'm parked now. Phew.")

    next_state = 'sleep'

    # Assume dark (we still check weather)
    if self.is_dark():
        # Assume bad weather so wait
        if not self.weather_station.is_safe():
            next_state = 'wait'
        else:
            self.say("Weather is good and it is dark. Something must have gone wrong. Sleeping")
    else:
        self.say("Another successful night! I'm going to get some sleep!")

    # Either wait until safe or goto next state (sleeping)
    if next_state == 'wait':
        self.wait_until_safe()
    else:
        self.goto(next_state)
