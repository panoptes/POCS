def on_enter(self, event_data):
    """
    In the `scheduling` state we attempt to find a target using our scheduler. If target is found,
    make sure that the target is up right now (the scheduler should have taken care of this). If
    observable, set the mount to the target and calls `slew_to_target` to begin slew.

    If no observable targets are available, `park` the unit.
    """
    self.say("Ok, I'm finding something good to look at...")

    # Get the next target
    try:
        target = self.observatory.get_target()
        self.logger.info(target)
    except Exception as e:
        self.logger.error("Error in scheduling: {}".format(e))

    # Assign the _method_
    next_state = 'park'

    if target is not None:

        self.say("Got it! I'm going to check out: {}".format(target.name))

        # Check if target is up
        if self.observatory.scheduler.target_is_up(self.observatory.now(), target):
            self.logger.debug("Setting Target coords: {}".format(target))

            has_target = self.observatory.mount.set_target_coordinates(target)

            if has_target:
                self.logger.debug("Mount set to target.".format(target))
                next_state = 'slew_to_target'
            else:
                self.logger.warning("Target not properly set. Parking.")
        else:
            self.say("That's weird, I have a target that is not up. Parking.")
    else:
        self.say("No valid targets found. Can't schedule. Going to park.")

    self.goto(next_state)
