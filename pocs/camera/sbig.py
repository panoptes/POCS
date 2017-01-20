from threading import Thread, Event
import os

import numpy as np

from astropy import units as u
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from astropy.modeling import models, fitting

import matplotlib.pyplot as plt

from .camera import AbstractCamera
from .sbigudrv import SBIGDriver, INVALID_HANDLE_VALUE
from ..utils import error, current_time, images


class Camera(AbstractCamera):

    # Class variable to store reference to the one and only one instance of SBIGDriver
    _SBIGDriver = None

    def __new__(cls, *args, **kwargs):
        if Camera._SBIGDriver is None:
            # Creating a camera but there's no SBIGDriver instance yet. Create one.
            Camera._SBIGDriver = SBIGDriver(*args, **kwargs)
        return super().__new__(cls)

    def __init__(self,
                 name='SBIG Camera',
                 set_point=None,
                 *args, **kwargs):
        kwargs['readout_time'] = 1.0
        kwargs['file_extension'] = 'fits'
        super().__init__(name, *args, **kwargs)
        self.connect()
        # Set cooling (if set_point=None this will turn off cooling)
        if self.is_connected:
            self.CCD_set_point = set_point
            self.logger.info('\t\t\t {} initialised'.format(self))

# Properties

    @AbstractCamera.uid.getter
    def uid(self):
        # Unlike Canon DSLRs 1st 6 characters of serial number is *not* a unique identifier.
        # Need to use the whole thing.
        return self._serial_number

    @property
    def CCD_temp(self):
        return self._SBIGDriver.query_temp_status(self._handle).imagingCCDTemperature * u.Celsius

    @property
    def CCD_set_point(self):
        return self._SBIGDriver.query_temp_status(self._handle).ccdSetpoint * u.Celsius

    @CCD_set_point.setter
    def CCD_set_point(self, set_point):
        self.logger.debug("Setting {} cooling set point to {}".format(self.name, set_point))
        self._SBIGDriver.set_temp_regulation(self._handle, set_point)

    @property
    def CCD_cooling_enabled(self):
        return bool(self._SBIGDriver.query_temp_status(self._handle).coolingEnabled)

    @property
    def CCD_cooling_power(self):
        return self._SBIGDriver.query_temp_status(self._handle).imagingCCDPower

# Methods

    def __str__(self):
        # For SBIG cameras uid and port are both aliases for serial number so shouldn't include both
        return "{} ({})".format(self.name, self.uid)

    def connect(self, set_point=None):
        """
        Connect to SBIG camera.

        Gets a 'handle', serial number and specs/capabilities from the driver

        Args:
            set_point (u.Celsius, optional): CCD cooling set point. If not given cooling will be disabled.
        """
        self.logger.debug('Connecting to camera {}'.format(self.uid))

        # Claim handle from the SBIGDriver, store camera info.
        self._handle, self._info = self._SBIGDriver.assign_handle(serial=self.port)

        if self._handle == INVALID_HANDLE_VALUE:
            self.logger.error('Could not connect to {}!'.format(self.name))
            self._connected = False
            return

        self.logger.debug("{} connected".format(self.name))
        self._connected = True
        self._serial_number = self._info['serial_number']

        if self._info['colour']:
            if self._info['Truesense']:
                self.filter_type = 'CRGB'
            else:
                self.filter_type = 'RGGB'
        else:
            self.filter_type = 'M'

    def take_observation(self, observation, headers, **kwargs):
        """Take an observation

        Gathers various header information, sets the file path, and calls `take_exposure`. Also creates a
        `threading.Event` object and a `threading.Thread` object. The Thread calls `process_exposure` after the
        exposure had completed and the Event is set once `process_exposure` finishes.

        Args:
            observation (~pocs.scheduler.observation.Observation): Object describing the observation
            headers (dict): Header data to be saved along with the file
            **kwargs (dict): Optional keyword arguments (`exp_time`, dark)

        Returns:
            threading.Event: An event to be set when the image is done processing
        """
        # To be used for marking when exposure is complete (see `process_exposure`)
        camera_event = Event()

        image_dir = self.config['directories']['images']
        start_time = headers.get('start_time', current_time(flatten=True))

        filename = "{}/{}/{}/{}.{}".format(
            observation.field.field_name,
            self.uid,
            observation.seq_time,
            start_time,
            self.file_extension)

        file_path = "{}/fields/{}".format(image_dir, filename)

        image_id = '{}_{}_{}'.format(
            self.config['name'],
            self.uid,
            start_time
        )
        self.logger.debug("image_id: {}".format(image_id))

        sequence_id = '{}_{}_{}'.format(
            self.config['name'],
            self.uid,
            observation.seq_time
        )

        # Camera metadata
        metadata = {
            'camera_name': self.name,
            'camera_uid': self.uid,
            'field_name': observation.field.field_name,
            'file_path': file_path,
            'filter': self.filter_type,
            'image_id': image_id,
            'is_primary': self.is_primary,
            'sequence_id': sequence_id,
            'start_time': start_time,
        }
        metadata.update(headers)
        exp_time = kwargs.get('exp_time', observation.exp_time)

        exposure_event = self.take_exposure(seconds=exp_time, filename=file_path)

        # Process the exposure once readout is complete
        t = Thread(target=self.process_exposure, args=(metadata, camera_event, exposure_event))
        t.name = '{}Thread'.format(self.name)
        t.start()

        return camera_event

    def take_exposure(self, seconds=1.0 * u.second, filename=None, dark=False, blocking=False):
        """
        Take an exposure for given number of seconds and saves to provided filename.

        Args:
            seconds (u.second, optional): Length of exposure
            filename (str, optional): Image is saved to this filename
            dark (bool, optional): Exposure is a dark frame (don't open shutter), default False

        Returns:
            threading.Event: Event that will be set when exposure is complete

        """
        assert self.is_connected, self.logger.error("Camera must be connected for take_exposure!")

        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        self.logger.debug('Taking {} second exposure on {}: {}'.format(seconds, self.name, filename))
        exposure_event = Event()
        self._SBIGDriver.take_exposure(self._handle, seconds, filename, exposure_event, dark)

        if blocking:
            exposure_event.wait()

        return exposure_event

    def process_exposure(self, info, signal_event, exposure_event=None):
        """
        Processes the exposure

        Args:
            info (dict): Header metadata saved for the image
            signal_event (threading.Event): An event that is set signifying that the
                camera is done with this exposure
            exposure_event (threading.Event, optional): An event that should be set
                when the exposure is complete, triggering the processing.
        """
        # If passed an Event that signals the end of the exposure wait for it to be set
        if exposure_event:
            exposure_event.wait()

        image_id = info['image_id']
        file_path = info['file_path']
        self.logger.debug("Processing {}".format(image_id))

        # Add FITS headers from info the same as images.cr2_to_fits()
        self.logger.debug("Updating FITS headers: {}".format(file_path))
        with fits.open(file_path, 'update') as f:
            hdu = f[0]
            hdu.header.set('IMAGEID', info.get('image_id', ''))
            hdu.header.set('SEQID', info.get('sequence_id', ''))
            hdu.header.set('FIELD', info.get('field_name', ''))
            hdu.header.set('RA-MNT', info.get('ra_mnt', ''), 'Degrees')
            hdu.header.set('HA-MNT', info.get('ha_mnt', ''), 'Degrees')
            hdu.header.set('DEC-MNT', info.get('dec_mnt', ''), 'Degrees')
            hdu.header.set('EQUINOX', info.get('equinox', ''))
            hdu.header.set('AIRMASS', info.get('airmass', ''), 'Sec(z)')
            hdu.header.set('FILTER', info.get('filter', ''))
            hdu.header.set('LAT-OBS', info.get('latitude', ''), 'Degrees')
            hdu.header.set('LONG-OBS', info.get('longitude', ''), 'Degrees')
            hdu.header.set('ELEV-OBS', info.get('elevation', ''), 'Meters')
            hdu.header.set('MOONSEP', info.get('moon_separation', ''), 'Degrees')
            hdu.header.set('MOONFRAC', info.get('moon_fraction', ''))
            hdu.header.set('CREATOR', info.get('creator', ''), 'POCS Software version')
            hdu.header.set('INSTRUME', info.get('camera_uid', ''), 'Camera ID')
            hdu.header.set('OBSERVER', info.get('observer', ''), 'PANOPTES Unit ID')
            hdu.header.set('ORIGIN', info.get('origin', ''))
            hdu.header.set('RA-RATE', info.get('tracking_rate_ra', ''), 'RA Tracking Rate')

        if info['is_primary']:
            self.logger.debug("Extracting pretty image")
            images.make_pretty_image(file_path, title=info['field_name'], primary=True)

            self.logger.debug("Adding current observation to db: {}".format(image_id))
            self.db.insert_current('observations', info, include_collection=False)
        else:
            self.logger.debug('Compressing {}'.format(file_path))
            images.fpack(file_path)

        self.logger.debug("Adding image metadata to db: {}".format(image_id))
        self.db.observations.insert_one({
            'data': info,
            'date': current_time(datetime=True),
            'type': 'observations',
            'image_id': image_id,
        })

        # Mark the event as done
        signal_event.set()

    def autofocus(self, seconds, focus_range, focus_step, thumbnail_size=500, plots=False):
        """
        
        """
        if not self.focuser:
            self.logger.error('Attempted to autofocus but camera {} has no focuser!'.format(self))
            return

        if not focus_range:
            if not self.focuser.autofocus_range:
                self.logger.error("No focus_range specified, aborting autofocus of {}!".format(self))
                return
            else:
                focus_range = self.focuser.autofocus_range

        if not focus_step:
            if not self.focuser.autofocus_step:
                self.logger.error("No focus_step specified, aborting autofocus of {}!".format(self))
                return
            else:
                focus_step = self.focuser.autofocus_step

        if not seconds:
            if not self.focuser.autofocus_seconds:
                self.logger.error("No focus exposure time specified, aborting autofocus of {}!".format(self))
                return
            else:
                seconds = self.focuser.autofocus_seconds

        initial_focus = self.focuser.position
        self.logger.debug("Beginning autofocus of {}, initial focus position: {}".format(self, initial_focus))

        # Set up paths for temporary focus files, and plots if requested.
        image_dir = self.config['directories']['images']
        start_time = current_time(flatten=True)
        file_path = "{}/{}/{}/{}.{}".format(
            image_dir,
            'focus',
            self.uid,
            start_time,
            self.file_extension)

        if plots:
            # Take an image before focusing, grab a thumbnail from the centre and add it to the plot
            thumbnail = self._get_thumbnail(seconds, file_path, thumbnail_size)
            plt.subplot(3,1,1)
            plt.imshow(thumbnail, interpolation='none', cmap='cubehelix')
            plt.colorbar()
            plt.title('Intial focus position: {}'.format(initial_focus))

        focus_positions = np.arange(initial_focus - focus_range/2,
                                    initial_focus + focus_range/2 + 1,
                                    focus_step, dtype=np.int)
        n_positions = len(focus_positions)

        f4_y = np.empty((n_positions))
        f4_x = np.empty((n_positions))

        for i, position in enumerate(focus_positions):
            # Move focus
            self.focuser.position = position
            
            # Take exposure
            thumbnail = self._get_thumbnail(seconds, file_path, thumbnail_size)

            # Very simple background subtraction, uses sigma clipped median pixel value as background estimate
            thumbnail = thumbnail - sigma_clipped_stats(thumbnail)[1]

            # Calculate Vollath F4 focus metric for both y and x axes directions
            f4_y[i], f4_x[i] = images.vollath_F4(thumbnail)
            self.logger.debug("F4 at position {}: {}, {}".format(position, f4_y[i], f4_x[i]))

        # Find maximum values
        ymax = f4_y.argmax()
        xmax = f4_x.argmax()

        if ymax == 0 or ymax == (n_positions - 1) or xmax == 0 or xmax == (n_positions - 1):
            # TODO: have this automatically switch to coarse focus mode if this happens
            self.logger.warning("Best focus outside sweep range, aborting autofocus on {}!".format(self))
            final_focus = self.focuser.move_to(focus_positions[ymax])
            return initial_focus, final_focus

        # Fit to data around the max value to determine best focus position. Lorentz function seems to fit OK
        # provided you only fit in the immediate vicinity of the max value.

        # Initialise models
        fit_y = models.Lorentz1D(x_0=focus_positions[ymax], amplitude=f4_y.max())
        fit_x = models.Lorentz1D(x_0=focus_positions[xmax], amplitude=f4_x.max())

        # Initialise fitter
        fitter = fitting.LevMarLSQFitter()

        # Select data range for fitting. Tries to use 2 points either side of max, if in range.
        fitting_indices_y = (ymax - 2 if ymax - 2 >= 0 else 0,
                             ymax + 2 if ymax + 3 <= n_positions else n_positions - 1)
        fitting_indices_x = (xmax - 2 if xmax - 2 >= 0 else 0,
                             xmax + 2 if xmax + 3 <= n_positions else n_positions - 1)

        # Fit models to data
        fit_y = fitter(fit_y,
                       focus_positions[fitting_indices_y[0]:fitting_indices_y[1] + 1],
                       f4_y[fitting_indices_y[0]:fitting_indices_y[1] + 1])
        fit_x = fitter(fit_x,
                       focus_positions[fitting_indices_x[0]:fitting_indices_x[1] + 1],
                       f4_x[fitting_indices_x[0]:fitting_indices_x[1] + 1])

        best_y = fit_y.x_0.value
        best_x = fit_x.x_0.value

        best_focus = (best_y + best_x) / 2

        if plots:
            fys = np.arange(focus_positions[fitting_indices_y[0]], focus_positions[fitting_indices_y[1]] + 1)
            fxs = np.arange(focus_positions[fitting_indices_x[0]], focus_positions[fitting_indices_y[1]] + 1)
            plt.subplot(3,1,2)
            plt.plot(focus_positions, f4_y, 'bo', label='$F_4$ $y$')
            plt.plot(focus_positions, f4_x, 'go', label='$F_4$ $x$')
            plt.plot(fys, fit_y(fys), 'b-', label='$y$ fit')
            plt.plot(fxs, fit_x(fxs), 'g-', label='$x$ fit')
            plt.xlim(focus_positions[0] - focus_step/2, focus_positions[-1] + focus_step/2)
            plt.ylim(0, 1.1 * f4_y.max())  
            plt.vlines(initial_focus, 0, 1.1 * f4_y.max(), colors='k', linestyles=':', 
                       label='Initial focus')
            plt.vlines(best_focus, 0, 1.1 * f4_y.max(), colors='k', linestyles='--', 
                       label='Best focus')
            plt.xlabel('Focus position')
            plt.ylabel('$F_4$')
            plt.title('Vollath $F_4$')
            plt.legend(loc='best')

        final_focus = self.focuser.move_to(best_focus)

        if plots:
            thumbnail = self._get_thumbnail(seconds, file_path, thumbnail_size)
            plt.subplot(3,1,3)
            plt.imshow(thumbnail, interpolation='none', cmap='cubehelix')
            plt.colorbar()
            plt.title('Final focus position: {}'.format(final_focus))
            plt.gcf().set_size_inches(7,15)
            plot_path = os.path.splitext(file_path)[0] + '.png'
            plt.savefig(plot_path)
            self.logger.debug('Autofocus plot written to {}'.format(plot_path))
            
        return initial_focus, final_focus


    def _get_thumbnail(self, seconds, file_path, thumbnail_size):
        """
        Takes an image, grabs the data, deletes the FITS file and 
        returns a thumbnail from the centre of the iamge.
        """
        self.take_exposure(seconds, filename=file_path, blocking=True)
        image = fits.getdata(file_path)
        os.unlink(file_path)
        thumbnail = images.crop_data(image, box_width=thumbnail_size)
        return thumbnail
