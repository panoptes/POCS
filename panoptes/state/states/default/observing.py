from ....utils import error


def on_enter(event_data):
    """ """
    pan = event_data.model
    pan.say("I'm finding exoplanets!")

    try:
        imgs_info = pan.observatory.observe()
        img_files = [info['img_file'] for cam_name, info in imgs_info.items()]

        pan.db.insert_current('camera', imgs_info)
    except Exception as e:
        pan.logger.warning("Problem with imaging: {}".format(e))
        pan.say("Hmm, I'm not sure what happened with that exposure.")
    else:
        # Wait for files to exist to finish to set up processing
        try:
            if pan.wait_until_files_exist(img_files):
                pan.analyze()
        except error.Timeout as e:
            pan.logger.warning("Timeout while waiting for images. Something wrong with camera, going to park.")
            pan.park()
        except Exception as e:
            pan.logger.error("Problem waiting for images: {}".format(e))
            pan.park()
