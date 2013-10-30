#!/usr/bin/env python

import panoptes.utils as utils


def state_shutdown():
    '''
    The shutdown state happens during the day, before components have been
    connected.
    
    From the shutdown state, you can go to sleeping.
    '''
    pass


def state_sleeping():
    '''
    The sleeping state happens during the day, after components have been
    connected, while we are waiting for darkness.
    
    From the sleeping state you can go to parking and getting ready.
    '''
    pass


def state_getting_ready():
    '''
    The getting ready state happens while it is dark, it checks if we are ready
    to observe.
    
    From the getting ready state, you can go to slewing to park and scheduling.
    '''
    pass


def state_scheduling():
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
              'shutdown':state_shutdown,
              'sleeping':state_sleeping,
              'getting ready':state_getting_ready,
              'scheduling':state_scheduling,
              'slewing':state_slewing,
              'analyzing':state_analyzing,
              'parking':state_parking,
              'parked':state_parked,
              'imaging':state_imaging
             }

    thingtoexectute = states['sleeping']
    thingtoexectute()

if __name__ == '__main__':
    start_session()
