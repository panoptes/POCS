def on_enter(event_data):
    """ """
    pan = event_data.model
    try:
        pan.say("I'm takin' it on home and then parking.")
        pan.observatory.mount.home_and_park()

        # pan.say("Saving any observations")
        # if len(pan.targets) > 0:
        #     for target, info in pan.observatory.observed_targets.items():
        #         raw = info['observations'].get('raw', [])
        #         analyzed = info['observations'].get('analyzed', [])

        #         if len(raw) > 0:
        #             pan.logger.debug("Saving {} with raw observations: {}".format(target, raw))
        #             pan.db.observations.insert({target: observations})

        #         if len(analyzed) > 0:
        #             pan.logger.debug("Saving {} with analyed observations: {}".format(target, observations))
        #             pan.db.observations.insert({target: observations})

        pan.wait_until_mount('is_parked', 'set_park')

    except Exception as e:
        pan.say("Yikes. Problem in parking: {}".format(e))
