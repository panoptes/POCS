from ....utils import error


def on_enter(event_data):
    """ """
    pan = event_data.model
    pan.say("I'm finding exoplanets!")

    try:
        pan.observatory.observe()

        # imgs_info = pan.observatory.observe()
        # img_files = [info['img_file'] for cam_name, info in imgs_info.items()]

        # TODO: Handle Quantity
        # pan.db.insert_current('camera', imgs_info)
    except Exception as e:
        pan.logger.warning("Problem with imaging: {}".format(e))
        pan.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        # Wait for files to exist to finish to set up processing
        try:
            pan.next_state = 'analyzing'
        except error.Timeout as e:
            pan.logger.warning("Timeout while waiting for images. Something wrong with camera, going to park.")
            pan.next_state = 'parking'
        except Exception as e:
            pan.logger.error("Problem waiting for images: {}".format(e))
            pan.next_state = 'parking'
