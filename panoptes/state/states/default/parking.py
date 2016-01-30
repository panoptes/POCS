def on_enter(self, event_data):
    """ """
    try:
        self.say("I'm takin' it on home and then parking.")
        self.observatory.mount.home_and_park()

        self.say("Saving any observations")
        # if len(self.targets) > 0:
        #     for target, info in self.observatory.observed_targets.items():
        #         raw = info['observations'].get('raw', [])
        #         analyzed = info['observations'].get('analyzed', [])

        #         if len(raw) > 0:
        #             self.logger.debug("Saving {} with raw observations: {}".format(target, raw))
        #             self.db.observations.insert({target: observations})

        #         if len(analyzed) > 0:
        #             self.logger.debug("Saving {} with analyed observations: {}".format(target, observations))
        #             self.db.observations.insert({target: observations})

        self.wait_until_mount('is_parked', 'set_park')

    except Exception as e:
        self.say("Yikes. Problem in parking: {}".format(e))
