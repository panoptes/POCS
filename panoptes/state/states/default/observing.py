from ....utils import error


def on_enter(event_data):
    """ """
    pan = event_data.model
    pan.say("I'm finding exoplanets!")

    try:
        imgs_info = pan.observatory.observe()
        img_files = [info['img_file'] for cam_name, info in imgs_info.items()]
    except Exception as e:
        pan.logger.warning("Problem with imaging: {}".format(e))
        pan.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        # Wait for files to exist to finish to set up processing
        try:
            pan.wait_until_files_exist(img_files, transition='analyze')
        except error.Timeout as e:
            pan.logger.warning("Problem taking pointing image")
            pan.goto('park')
        except Exception as e:
            pan.logger.error("Problem waiting for images: {}".format(e))
            pan.goto('park')
