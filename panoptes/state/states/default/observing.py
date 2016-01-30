def on_enter(self, event_data):
    """ """
    self.say("I'm finding exoplanets!")

    try:
        img_files = self.observatory.observe()
    except Exception as e:
        self.logger.warning("Problem with imaging: {}".format(e))
        self.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        # Wait for files to exist to finish to set up processing
        try:
            self.wait_until_files_exist(img_files, transition='analyze')
        except Exception as e:
            self.logger.error("Problem waiting for images: {}".format(e))
            self.goto('park')
