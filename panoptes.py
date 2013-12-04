#!/usr/bin/env python

import panoptes.utils as utils


def while_shutdown():
    '''
    The shutdown state happens during the day, before components have been
    connected.
    
    From the shutdown state, you can go to sleeping.  This transition should be
    triggered by timing.  At a user configured time, the system will connect to
    components and start cooling the camera in preparation for observing.  This
    time checking should be built in to this while_shutdown function and trigger
    a change of state.
    
    In shutdown state:
    - it is:                day
    - camera connected:     no
    - camera cooling:       N/A
    - camera cooled:        N/A
    - camera exposing:      N/A
    - mount connected:      no
    - mount tracking:       N/A
    - mount slewing:        N/A
    - mount parked:         N/A
    - weather:              either
    - target chosen:        N/A
    - test image taken:     N/A
    - target completed:     N/A
    - analysis attempted:   N/A
    - analysis in progress: N/A
    - astrometry solved:    N/A
    - levels determined:    N/A
    
    Timeout Condition:  This state has a timeout built in as it will end at a
    given time each day.
    '''
    currentState = "shutdown"
    ## First check state of observatory
    ## - If all conditions meet expected values for shutdown state, do nothing
    if not observatory.is_dark() and not camera.is_connected() and
       not mount.is_connected():
        ## All conditions are met.  Do nothing.
        logger.debug("Conditions expected for shutdown state are met.")
    elif not observatory.is_dark() and not camera.is_connected() and
        mount.is_connected():
        ## Mount is connected when not expected to be.
        logger.warning("Mount is connected in shutdown state.")
    elif not observatory.is_dark() and camera.is_connected() and
        not mount.is_connected():
        ## Camera is connected when not expected to be.
        logger.warning("Camera is connected in shutdown state.")
    elif not observatory.is_dark() and camera.is_connected() and
        mount.is_connected():
        ## Camera and mount are connected when not expected to be.
        logger.warning("Camera and mount are connected in shutdown state.")
    else:
        ## It is night.  Transition to sleeping state by connecting to camera 
        ## and mount.
        logger.info("Connect to camera and mount.  Transition to sleeping.")
        currentState = "sleeping"
        try:
            camera.connect()
        except:
            ## Failed to connect to camera
            ## Exit to parking state and log problem.
            currentState = "parking"
            logger.critical("Unable to connect to camera.  Parking.")
            mount.park()
        try:
            mount.connect()
        except:
            ## Failed to connect to mount
            ## Exit to parking state and log problem.
            currentState = "parking"
            logger.critical("Unable to connect to mount.  Parking.")
            mount.park()
    ## If still in shutdown state, wait one minute.
    if currentState == "shutdown":
        logger.info("In shutdown state.  Waiting for dark.")
        time.sleep(60)
    return currentState


def while_sleeping():
    '''
    The sleeping state happens during the day, after components have been
    connected, while we are waiting for darkness.
    
    From the sleeping state you can go to parking and getting ready.  Moving to
    parking state should be triggered by bad weather.  Moving to getting reeady
    state should be triggered by timing.  At a user configured time (i.e. at
    the end of twilight), the system will go to getting ready.
    
    In sleeping state:
    - it is:                day
    - camera connected:     yes
    - camera cooling:       no
    - camera cooled:        no
    - camera exposing:      no
    - mount connected:      yes
    - mount tracking:       no
    - mount slewing:        no
    - mount parked:         yes
    - weather:              either
    - target chosen:        no
    - test image taken:     N/A
    - target completed:     N/A
    - analysis attempted:   N/A
    - analysis in progress: N/A
    - astrometry solved:    N/A
    - levels determined:    N/A
    
    Timeout Condition:  This state does not have a formal timeout, but should
    check to see if it is night as this state should not happen during night.
    '''
    pass


def while_getting_ready():
    '''
    The getting ready state happens while it is dark, it checks if we are ready
    to observe.
    
    From the getting ready state, you can go to parking and scheduling.
    
    In the getting ready state:
    - it is:                night
    - camera connected:     yes
    - camera cooling:       on
    - camera cooled:        no
    - camera exposing:      no
    - mount connected:      yes
    - mount tracking:       no
    - mount slewing:        no
    - mount parked:         either
    - weather:              safe
    - target chosen:        no
    - test image taken:     N/A
    - target completed:     N/A
    - analysis attempted:   N/A
    - analysis in progress: N/A
    - astrometry solved:    N/A
    - levels determined:    N/A
    
    To transition to the scheduling state the camera must reach the cooled
    condition.
    
    Timeout Condition:  There should be a reasonable timeout on this state.  The
    timeout period should be set such that the camera can go from ambient to
    cooled within the timeout period.  The state should only timeout under
    extreme circumstances as the cooling process should monitor whether the
    target temperature is reachable and adjust the camera set point higher if
    needed and this may need time to iterate and settle down to operating temp.
    If a timeout occurs, the system should go to parking state.
    '''
    pass


def while_scheduling():
    '''
    The scheduling state happens while it is dark after we have requested a
    target from the scheduler, but before the target has been returned.  This
    assumes that the scheduling happens in another thread.
    
    From the scheduling state you can go to the parking state and the
    slewing state.
    
    In the scheduling state:
    - it is:                night
    - camera connected:     yes
    - camera cooling:       on
    - camera cooled:        yes
    - camera exposing:      no
    - mount connected:      yes
    - mount tracking:       no
    - mount slewing:        no
    - mount parked:         either
    - weather:              safe
    - target chosen:        no
    - test image taken:     N/A
    - target completed:     N/A
    - analysis attempted:   N/A
    - analysis in progress: N/A
    - astrometry solved:    N/A
    - levels determined:    N/A

    To transition to the slewing state, the target field must be populated, then
    the slew command is sent to the mount.

    This sets:
    - target chosen:        yes
    - test image taken:     no
    - target completed:     no
    - analysis attempted:   no
    - analysis in progress: no
    - astrometry solved:    no
    - levels determined:    no
    
    Timeout Condition:  A reasonable timeout period for this state should be
    set.  Some advanced scheduling algorithms with many targets to consider may
    need a significant amount of time to schedule, but that reduces observing
    efficiency, so I think the timout for this state should be of order 10 sec.
    If a timeout occurs, the system should go to getting ready state.  This does
    allow a potential infinite loop scenario if scheduling is broken, because
    going to the getting ready state will usually just bouce the system back to
    scheduling, but this is okay because it does not endanger the system as it
    will still park on bad weather and at the end of the night.
    '''
    pass


def while_slewing():
    '''
    The slewing state happens while the system is slewing to a target position
    (note: this is distinct from the slew which happens on the way to the park
    position).
    
    From the slewing state, you can go to the parking state, the taking
    test image state, and the imaging state.

    In the slewing state:
    - it is:                night
    - camera connected:     yes
    - camera cooling:       on
    - camera cooled:        yes
    - camera exposing:      no
    - mount connected:      yes
    - mount tracking:       no
    - mount slewing:        yes
    - mount parked:         no
    - weather:              safe
    - target chosen:        yes
    - test image taken:     either
    - target completed:     no
    - analysis attempted:   no
    - analysis in progress: no
    - astrometry solved:    no
    - levels determined:    no

    To go to the taking test image state, the slew must complete and test image
    taken is no.
    
    To go to the imaging state, the slew must complete and the test image taken
    must be yes.

    Completion of the slew sets:
    - mount slewing:        no
    
    Timeout Condition:  There should be a reasonable timeout condition on the
    slew which allows for long slews with a lot of extra time for settling and
    other considerations which may vary between mounts.  If a timeout occurs,
    the system should go to getting ready state.
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
    than a science image.  For example, for a given target, only one test image
    needs to be taken, where we probably want >1 science image.  Also, we can
    use a flag to turn off this operation.
    
    From the taking test image state, you can go to the parking state
    and the analyzing state.

    In the taking test image state:
    - it is:                night
    - camera connected:     yes
    - camera cooling:       on
    - camera cooled:        yes
    - camera exposing:      yes
    - mount connected:      yes
    - mount tracking:       yes
    - mount slewing:        no
    - mount parked:         no
    - weather:              safe
    - target chosen:        yes
    - test image taken:     no
    - target completed:     no
    - analysis attempted:   no
    - analysis in progress: no
    - astrometry solved:    no
    - levels determined:    no
    
    To move to the analyzing state, the image must complete:

    This sets:
    - test image taken:     yes
    
    Timeout Condition:  A reasonable timeout should be set which allows for a
    short exposure time, plus download time and some additional overhead.  If a
    timeout occurs, ... actually I'm not sure what should happen in this case.
    Going to getting ready state will also just wait for the image to finish, so
    nothing is gained relative to having no timeout.  This suggests that we DO
    need a method to cancel an exposure which is invoked in case of a timeout,
    which is something I had specifically hoped NOT to have to create.
    '''
    pass


def while_analyzing():
    '''
    The analyzing state happens after one has taken an image or test image.  It
    always operates on the last image taken (whose file name should be stored
    in a variable somewhere).
    
    From the analyzing state, you can go to the parking state, the
    getting ready state, or the slewing state.

    In the analyzing state:
    - it is:                night
    - camera connected:     yes
    - camera cooling:       on
    - camera cooled:        yes
    - camera exposing:      no
    - mount connected:      yes
    - mount tracking:       yes
    - mount slewing:        no
    - mount parked:         no
    - weather:              safe
    - target chosen:        yes
    - test image taken:     yes
    - target completed:     no
    - analysis attempted:   no
    - analysis in progress: no
    - astrometry solved:    no
    - levels determined:    no
    
    If the analysis is successful, this sets:
    - analysis attempted:   yes
    - analysis in progress: yes
    - astrometry solved:    yes
    - levels determined:    yes
    
    As part of analysis step, the system compares the number of images taken of
    this target since it was chosen to the minimum number requested by scheduler
    (typically three).  If we have taken enough images of this target, we set
    target completed to yes, if not, we leave it at no.
    
    To move to the slewing state, target complete must be no and astrometry
    solved is yes.  The slew recenters the target based on the astrometric
    solution.
    
    To move to the getting ready state, the target completed must be yes.  After
    a brief stop in getting ready state (to check that all systems are still
    ok), we would presumably go back to scheduling.  The scheduler may choose to
    observe this target again.  The minimum number of images is just that, a
    minimum, it defines the smallest schedulable block.

    We need to discuss what happens when analysis fails.
    
    Timeout Condition:  A readonable timeout should be set.  If a timeout
    occurs, we should handle that identically to a failure of the analysis.
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
    case.  This avoids the requirement of writing complicated exposure
    cancelling code in to each camera driver.
    
    As a result, if the system has to park during an
    exposure (i.e. if the weather goes bad), the camera will contine to expose.
    This means that there are cases when the camera is exposing, but you are not
    in the imaging state.  There are some edge cases we need to test (especially
    in the parking and parked states) to ensure that the camera exposure
    finishes before those states are left.

    When we enter this state, we must reset the following:
    - analysis attempted:   no
    - analysis in progress: no
    - astrometry solved:    no
    - levels determined:    no

    In the imaging state:
    - it is:                night
    - camera connected:     yes
    - camera cooling:       on
    - camera cooled:        yes
    - camera exposing:      yes
    - mount connected:      yes
    - mount tracking:       yes
    - mount slewing:        no
    - mount parked:         no
    - weather:              safe
    - target chosen:        yes
    - test image taken:     yes
    - target completed:     no
    - analysis attempted:   no
    - analysis in progress: no
    - astrometry solved:    no
    - levels determined:    no
    
    Timeout Condition:  A reasonable timeout should be set is based on the
    exposure time, plus download time and some additional overhead.  If a
    timeout occurs, ... actually I'm not sure what should happen in this case.
    Going to getting ready state will also just wait for the image to finish, so
    nothing is gained relative to having no timeout.  This suggests that we DO
    need a method to cancel an exposure which is invoked in case of a timeout,
    which is something I had specifically hoped NOT to have to create.
    '''
    pass


def while_parking():
    '''
    This is the state which is the emergency exit.  A park command has been
    issued to put the system in a safe state, but we have not yet reached the
    park position.
    
    From the parking state, one can only exit to the parked state.
    
    Timeout Condition:  There are two options I see for a timeout on the parking
    state.  The first is to not have a timeout simply because if a park has been
    commanded, then we should assume that it is critical to safety to park and
    nothing should interrupt a park command.  Alternatively, I can imagine
    wanting to resend the park command if the system does not reach park.  The
    downside to this is that we might end up in a repeating loop of issuing a
    park command to the mount over and over again in a situation where there is
    a physical obstruction to the park operation and this damages the motors.
    There might be a third alternative which is to limit the number of retries
    on the park command after timeouts.
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
    
    Timeout Condition:  There is a natural timeout to this state which occurs at
    the end of the night which causes a transition to the shutdown state.
    '''
    pass


def checkObservatoryProperties():
    '''
    Queries the states of the various observatory components and populates
    properties of the observatory object (or should this be a dictionary?).
    
    This checks all the properties discussed above in the while_state functions.
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

    ## Operations Loop
    currentState = 'shutdown'  # assume we are in shutdown on program startup
    while True:
        ## Check Component Properties
        observatoryProperties = checkObservatoryProperties()
        ## Check to see if properties are consistent with the state we are in
        ##   if yes, then execute current state
        thingtoexectute = states[currentState]
        currentState = thingtoexectute()

if __name__ == '__main__':
    start_session()
