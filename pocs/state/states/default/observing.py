from ....utils import error


def on_enter(event_data):
    """ """
    pocs = event_data.model
    pocs.say("I'm finding exoplanets!")

    try:
        pocs.observatory.observe()

        # imgs_info = pocs.observatory.observe()
        # img_files = [info['img_file'] for cam_name, info in imgs_info.items()]

        # TODO: Handle Quantity
        # pocs.db.insert_current('camera', imgs_info)
    except Exception as e:
        pocs.logger.warning("Problem with imaging: {}".format(e))
        pocs.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        # Wait for files to exist to finish to set up processing
        try:
            pocs.next_state = 'analyzing'
        except error.Timeout as e:
            pocs.logger.warning("Timeout while waiting for images. Something wrong with camera, going to park.")
            pocs.next_state = 'parking'
        except Exception as e:
            pocs.logger.error("Problem waiting for images: {}".format(e))
            pocs.next_state = 'parking'
