def on_enter(self, event_data):
    """
    Once in the `ready` state our unit has been initialized successfully. The next step is to
    schedule something for the night.
    """
    self.say("Up and ready to go!")

    self.wait_until_mount('is_home', 'schedule')
