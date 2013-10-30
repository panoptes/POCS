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
    
    From the getting ready state, you can go to slewing to park and scheduling.
    '''
    pass


def while_scheduling():
    '''
    The scheduling state happend while it is dark after we have requested a
    target from the scheduler, but before the target has been returned.  This
    assumes that the scheduling happens in another thread.
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
              'analyzing':while_analyzing,
              'parking':while_parking,
              'parked':while_parked,
              'imaging':while_imaging
             }

    thingtoexectute = states['sleeping']
    thingtoexectute()

if __name__ == '__main__':
    start_session()
