# Observatory Control Software

For this discussion, I'm laying out how I would think about a single threaded version of the observatory control software.  Since I know python, this is all loosely based on python objects.

## Objects

### Observatory

Contains all observatory properties such as lat, long, elevation, etc.  Could also contain the mount object, camera object, etc. to minimize the issue of passing information.  If that's the case, everything happens in the observatory object.

* Observatory.operate - Boolean value:  whether or not it is safe to observe.
* Observatory.Dark() - Method which compares the current time to sunrise and sunset times (or twilight times if preferred) and returns True or False depending on whether it is night.
* Observatory.Heartbeat() - Method to touch a heartbeat file.  If the timestamp on this file gets stale, a monitor program will kill this program and park mount just like Oli does in skycam.c.


### Mount

Each mount should have the following methods which behave the same.  We should probably define a mount class and then build objects for each specific model of mount.

* Mount.Connect() - Opens serial connection to mount, tests communication.
* Mount.StartSlewToTarget() - Slews to given RA, Dec.  Incorporates mount model in command.  Also starts sidereal tracking (modified by mount model if desired).
* Mount.QuerySlewingState() - Queries the mount to see if it is still slewing.
* Mount.SyncWithImage() - Take short exposure (needs access to camera object), solve astrometry, then sync on this position (or add to mount model).
* Mount.Park() - Parks mount in safe condition.  Stops tracking.


### Camera

Similar to the way mounts are handled, each camera should have the following methods which behave the same.  We should probably define a camera class and then build objects for each specific model.

* Camera.Connect() - Opens connection to camera, tests communication.
* Camera.IsCool() - If CCD cooler on and has stabilized, return True.  Always return True for uncooled camera.
* Camera.SetCooler() - Set target cooling for camera and turn on cooler.
* Camera.StartExposure() - Starts exposure in given filter and with given exposure time.  
    * The exposure should execute on it's own, either in the camera or in a separate thread, so that this operation thread is free to do other tasks.  I think this should work fine for DSLRs and for SBIG cameras.  Not sure yet if other cameras will work within this strategy.
    * For the DSLR, I think the command should be sent to the Arduino which tells it which of the 4 cameras to trigger and how long to trigger them for.  The Arduino will hold the shutter button down for that length of time then release.
* Camera.IsExposing() - Checks to see if an exposure is active.
    * For the DSLRs this just asks the Arduino if the output trigger is active.
* Camera.StopExposure() - Halts exposure.  Used to cancel an exposure.

### Image

I'm not going to go in to detail here, but we will want to do some image analysis actively throughout the night.  I think the IQMon package I've written will be useful here.  We can use it to quickly get FWHM values if we ever want to implement focusing (I have ideas for that which I think will integrate smoothly with this software).  IQMon can also report the image background levels which can be used to modify the exposure time as Oli did in skycam.c.  I've left these analysis off of the pseudocode below for simplicity.

### Weather Station

The weather station runs on an independantly operating arduino board.  In addition, I am assuming that there is a loop running elsewhere on the control computer which queries the arduino and records the values to a log.

* WeatherStation.IsSafe() - Examines recent weather station logs, if data is not stale and if safe conditions are met, then return True.  This method only examines the logs, it does not interact with the actual weather station hardware.  This value should go False (unsafe) as soon as any unsafe conditions are met.  It should go True (safe) only if all values have been safe for a minimum length of time to avoid safe/unsafe oscillations.


### Scheduler

The scheduler object contains whatever algorithm selects the next target and the target information.  Scheduler can also be used for manual control.  For example, if scheduler is reading possible targets from a text file, we can just make a simple command line program which makes a targets file with a single target.  Then the next time through the operation loop, that target will get observed.  Similar to manual operation.

* Scheduler.target - Object with properties such as the target's name, coordinates, filters to observe in, number of exposures to take, exposure time, etc.
* Scheduler.ChooseTarget() - Given curent status and target database.  Loads the next target in to Scheduler.target.  This can vary from very simple to very complex depending on what we want it to do.


## Pseudocode Describing Main Operation Loop

```
## Define Mount and Cameras
Mount = Panoptes.OrionAtlasEQG()
Cameras = [Panoptes.CanonEOS500D(), Panoptes.CanonEOS550D()]

## Connect to mount and cameras
Mount.Connect()
for Camera in Cameras:
    Camera.Connect()
    if not Camera.IsCool():
        Camera.TurnOnCooler()
Cooled = numpy.zeros(len(Cameras))  ## This just holds all the T/F values on whether each camera has reached cooling target.
while not Cooled.all():
    time.sleep(60)
    for i in range(0, len(Cameras)): Cooled[i] = Cameras[i].IsCool()
    ## Need to have an escape clause in this loop to handle case where target temp is not reachable

## Wait for it to get dark
while not Observatory.Dark():
    time.sleep(60)
    ## Add some code here to take twilight flats if desired

## This is the nighttime loop, we stay in this regardless of whether it is safe.
while Observatory.Dark():

    ## Check the weather to see if it is safe to operate
    if WeatherStation.IsSafe(): Observatory.operate = True

    ## This is the operation loop.  If conditions are safe, we stay in this loop.
    while Observatory.operate:
        Observatory.Heartbeat()
        if not WeatherStation.IsSafe():    ## This block of code escapes
            Observatory.operate = False    ## the operation loop if the
            break                          ## weather becomes unsafe.

        Scheduler.ChooseTarget()

        Observatory.Heartbeat()
        if not WeatherStation.IsSafe():    ## This block of code escapes
            Observatory.operate = False    ## the operation loop if the
            break                          ## weather becomes unsafe.

        Mount.StartSlewToTarget(Scheduler.target)
        while Mount.QuerySlewingState() = True:
            sleep(1)  ## or do other small, quick tasks
            Observatory.Heartbeat()
            if not WeatherStation.IsSafe():    ## This block of code escapes
                Observatory.operate = False    ## the slewing loop if the
                break                          ## weather becomes unsafe.

        if not WeatherStation.IsSafe():    ## This block of code escapes
            Observatory.operate = False    ## the operation loop if the
            break                          ## weather becomes unsafe.

        Mount.SyncWithImage()

        Mount.SlewTo(Scheduler.target)     ## Slew again after sync to recenter.
        while Mount.QuerySlewingState() = True:
            sleep(1)  ## or do other small, quick tasks
            Observatory.Heartbeat()
            if not WeatherStation.IsSafe():    ## This block of code escapes
                Observatory.operate = False    ## the slewing loop if the
                break                          ## weather becomes unsafe.

        if not WeatherStation.IsSafe():    ## This block of code escapes
            Observatory.operate = False    ## the operation loop if the
            break                          ## weather becomes unsafe.

        ## Loop through filters (not used by DSLRs)
        for filter in Scheduler.target.filters:
            ## Loop through multiple exposures.
            for i in range(0,Scheduler.target.nExposures):
                Observatory.Heartbeat()

                for Camera in Cameras:
                    Camera.StartExposure(filter)
                ExposuresDone = np.zeroes(nCameras)
                while not ExposuresDone.all():
                    wait(0.1)
                    for Camera in Cameras:
                        Observatory.Heartbeat()
                        ExposuresDone[i] = Cameras[i].IsExposing()
                    if not WeatherStation.IsSafe():    ## This block of code escapes
                        Observatory.operate = False    ## the exposure loop if the
                        break                          ## weather becomes unsafe

                if not WeatherStation.IsSafe():    ## This block of code escapes
                    Observatory.operate = False    ## the nExposures loop if the
                    break                          ## weather becomes unsafe

            if not WeatherStation.IsSafe():    ## This block of code escapes
                Observatory.operate = False    ## the filters loop if the
                break                          ## weather becomes unsafe.

        if not WeatherStation.IsSafe():    ## This block of code escapes
            Observatory.operate = False    ## the operation loop if the
            break                          ## weather becomes unsafe.

        Observatory.Heartbeat()

    Mount.Park()
    Observatory.Heartbeat()
    time.sleep(600)
```

Each method should have a timeout to lessen the chances of getting frozen, but heartbeat will help recover from frozen software.
