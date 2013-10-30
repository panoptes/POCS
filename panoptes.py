#!/usr/bin/env python

import panoptes.utils as utils


def while_shutdown():
    '''
    The shutdown state happens during the day, before components have been
    connected.
    
    From the shutdown state, you can go to sleeping.
    '''
    pass


def while_sleeping():
    '''
    The sleeping state happens during the day, after components have been
    connected, while we are waiting for darkness.
    
    From the sleeping state you can go to parking and getting ready.
    '''
    pass


def while_getting_ready():
    '''
    The getting ready state happens while it is dark, it checks if we are ready
    to observe.
    
    From the getting ready state, you can go to parking and scheduling.
    '''
    pass


def while_scheduling():
    '''
    The scheduling state happens while it is dark after we have requested a
    target from the scheduler, but before the target has been returned.  This
    assumes that the scheduling happens in another thread.
    
    From the scheduling state you can go to the parking state and the
    slewing state.
    '''
    pass


def while_slewing():
    '''
    The slewing state happens while the system is slewing to a target position
    (note: this is distinct from the slew which happens on the way to the park
    position).
    
    From the slewing state, you can go to the parking state, the taking
    test image state, and the imaging state.
    '''
    pass


def while_taking_test_image():
    '''
    The taking test image state happens after one makes a large (threshold
    controlled by a setting) slew.  The system takes a short image, plate solves
    it, then determines the pointing offset and commands a correcting slew.  One
    might also check the image background levels in this test image an use them
    to set the exposure time in the science image.
    
    Note:  One might argue that this is so similar to the imaging state that
    they should be merged in to one state, but I think this is a useful
    distinction to make as the settings for the test image will be different
    than a science image.
    
    From the taking test image state, you can go to the parking state
    and the analyzing state.
    '''
    pass


def while_analyzing():
    '''
    The analyzing state happens after one has taken an image or test image.
    
    From the analyzing state, you can go to the parking state, the
    getting ready state, or the slewing state.
    '''
    pass


def while_imaging():
    '''
    This state happens as the camera is exposing.
    
    From the imaging state, you can go to the parking statee and the analyzing
    state.
    
    Note: as we are currently envisioning the system operations, you can not
    cancel an exposure.  The logic behind this is that if we want to go to a
    parked state, then we don't care about the image and it is easy to simply
    tag an image header with information that the exposure was interrupted by
    a park operation, so we don't care if the data gets written to disk in this
    case.  As a result, if the system has to park during an
    exposure (i.e. if the weather goes bad), the camera will contine to expose.
    This means that there are cases when the camera is exposing, but you are not
    in the imaging state.  There are some edge cases we need to test (especially
    in the parking and parked states) to ensure that the camera exposure
    finishes before those states are left.
    '''
    pass


def while_parking():
    '''
    This is the state which is the emergency exit.  A park command has been
    issued to put the system in a safe state, but we have not yet reached the
    park position.
    
    From the parking state, one can only exit to the parked state.
    '''
    pass


def while_parked():
    '''
    The parked state is where the system exists at night when not observing.
    During the day, we are at the physical parked position for the mount, but
    we would be in either the shutdown or sleeping state.
    
    From the parked state we can go to shutdown (i.e. when the night ends), or
    we can go to getting ready (i.e. it is still night, conditions are now safe,
    and we can return to operations).
    '''
    pass


def main():
    logger = utils.Logger()

    mount = panoptes.mount.Mount()
    cameras = [panoptes.camera.Camera(), panoptes.camera.Camera()]
    observatory = panoptes.observatory.Observatory()

    states = {
              'shutdown':while_shutdown,
              'sleeping':while_sleeping,
              'getting ready':while_getting_ready,
              'scheduling':while_scheduling,
              'slewing':while_slewing,
              'taking test image':while_taking_test_image,
              'analyzing':while_analyzing,
              'imaging':while_imaging,
              'parking':while_parking,
              'parked':while_parked,
             }

    thingtoexectute = states['sleeping']
    thingtoexectute()

if __name__ == '__main__':
    start_session()
