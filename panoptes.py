#!/usr/bin/env python

import panoptes.utils as utils

def state_sleeping():
    '''
    The sleeping state happens during the day, after components have been
    connected, while we are waiting for darkness.
    
    From the sleeping state you can exit to parking and getting ready.
    '''
    pass

def state_shutdown():
    '''
    '''
    pass



def main():
    logger = utils.Logger()

    mount = panoptes.mount.Mount()
    cameras = [panoptes.camera.Camera(), panoptes.camera.Camera()]
    observatory = panoptes.observatory.Observatory()

    states = {'sleeping':state_sleeping,
              'shutdown':state_shutdown,
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
