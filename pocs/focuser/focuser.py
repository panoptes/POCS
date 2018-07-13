import matplotlib.colors as colours
import matplotlib.pyplot as plt

from astropy.modeling import models, fitting
from scipy.ndimage import binary_dilation

import numpy as np

from copy import copy
from threading import Event
from threading import Thread


from pocs.base import PanBase
from pocs.utils import current_time
from pocs.utils.images import focus as focus_utils

palette = copy(plt.cm.inferno)
palette.set_over('w', 1.0)
palette.set_under('k', 1.0)
palette.set_bad('g', 1.0)


class AbstractFocuser(PanBase):
    """
    Base class for all focusers

    Args:
        name (str, optional): name of the focuser
        model (str, optional): model of the focuser
        port (str, optional): port the focuser is connected to, e.g. a device node
        camera (pocs.camera.Camera, optional): camera that this focuser is associated with.
        initial_position (int, optional): if given the focuser will move to this position
            following initialisation.
        autofocus_range ((int, int) optional): Coarse & fine focus sweep range, in encoder units
        autofocus_step ((int, int), optional): Coarse & fine focus sweep steps, in encoder units
        autofocus_seconds (scalar, optional): Exposure time for focus exposures
        autofocus_size (int, optional): Size of square central region of image to use, default
            500 x 500 pixels.
        autofocus_keep_files (bool, optional): If True will keep all images taken during focusing.
            If False (default) will delete all except the first and last images from each focus run.
        autofocus_take_dark (bool, optional): If True will attempt to take a dark frame before the
            focus run, and use it for dark subtraction and hot pixel masking, default True.
        autofocus_merit_function (str/callable, optional): Merit function to use as a focus metric,
            default vollath_F4
        autofocus_merit_function_kwargs (dict, optional): Dictionary of additional keyword arguments
            for the merit function.
        autofocus_mask_dilations (int, optional): Number of iterations of dilation to perform on the
            saturated pixel mask (determine size of masked regions), default 10
        autofocus_spline_smoothing (float, optional): smoothing parameter for the spline fitting to
            the autofocus data, 0.0 to 1.0, smaller values mean *less* smoothing, default 0.4
    """
    def __init__(self,
                 name='Generic Focuser',
                 model='simulator',
                 port=None,
                 camera=None,
                 initial_position=None,
                 autofocus_range=None,
                 autofocus_step=None,
                 autofocus_seconds=None,
                 autofocus_size=None,
                 autofocus_keep_files=None,
                 autofocus_take_dark=None,
                 autofocus_merit_function=None,
                 autofocus_merit_function_kwargs=None,
                 autofocus_mask_dilations=None,
                 autofocus_spline_smoothing=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.model = model
        self.port = port
        self.name = name

        self._connected = False
        self._serial_number = 'XXXXXX'

        if initial_position is None:
            self._position = None
        else:
            self._position = int(initial_position)

        if autofocus_range:
            self.autofocus_range = (int(autofocus_range[0]), int(autofocus_range[1]))
        else:
            self.autofocus_range = None

        if autofocus_step:
            self.autofocus_step = (int(autofocus_step[0]), int(autofocus_step[1]))
        else:
            self.autofocus_step = None

        self.autofocus_seconds = autofocus_seconds
        self.autofocus_size = autofocus_size
        self.autofocus_keep_files = autofocus_keep_files
        self.autofocus_take_dark = autofocus_take_dark
        self.autofocus_merit_function = autofocus_merit_function
        self.autofocus_merit_function_kwargs = autofocus_merit_function_kwargs
        self.autofocus_mask_dilations = autofocus_mask_dilations
        self.autofocus_spline_smoothing = autofocus_spline_smoothing

        self._camera = camera

        self.logger.debug('Focuser created: {} on {}'.format(self.name, self.port))

##################################################################################################
# Properties
##################################################################################################

    @property
    def uid(self):
        """ A serial number for the focuser """
        return self._serial_number

    @property
    def is_connected(self):
        """ Is the focuser available """
        return self._connected

    @property
    def position(self):
        """ Current encoder position of the focuser """
        return self._position

    @position.setter
    def position(self, position):
        """ Move focusser to new encoder position """
        self.move_to(position)

    @property
    def camera(self):
        """
        Reference to the Camera object that the Focuser is assigned to, if any. A Focuser
        should only ever be assigned to one or zero Cameras!
        """
        return self._camera

    @camera.setter
    def camera(self, camera):
        if self._camera:
            self.logger.warning("{} assigned to {}, skipping attempted assignment to {}!",
                                self, self.camera, camera)
        else:
            self._camera = camera

    @property
    def min_position(self):
        """ Get position of close limit of focus travel, in encoder units """
        raise NotImplementedError

    @property
    def max_position(self):
        """ Get position of far limit of focus travel, in encoder units """
        raise NotImplementedError

##################################################################################################
# Methods
##################################################################################################

    def move_to(self, position):
        """ Move focusser to new encoder position """
        raise NotImplementedError

    def move_by(self, increment):
        """ Move focusser by a given amount """
        return self.move_to(self.position + increment)

    def autofocus(self,
                  seconds=None,
                  focus_range=None,
                  focus_step=None,
                  thumbnail_size=None,
                  keep_files=None,
                  take_dark=None,
                  merit_function=None,
                  merit_function_kwargs=None,
                  mask_dilations=None,
                  spline_smoothing=None,
                  coarse=False,
                  plots=True,
                  blocking=False,
                  *args, **kwargs):
        """
        Focuses the camera using the specified merit function. Optionally performs
        a coarse focus first before performing the default fine focus. The
        expectation is that coarse focus will only be required for first use
        of a optic to establish the approximate position of infinity focus and
        after updating the intial focus position in the config only fine focus will
        be required.

        Args:
            seconds (scalar, optional): Exposure time for focus exposures, if not
                specified will use value from config.
            focus_range (2-tuple, optional): Coarse & fine focus sweep range, in
                encoder units. Specify to override values from config.
            focus_step (2-tuple, optional): Coarse & fine focus sweep steps, in
                encoder units. Specify to override values from config.
            thumbnail_size (int, optional): Size of square central region of image
                to use, default 500 x 500 pixels.
            keep_files (bool, optional): If True will keep all images taken
                during focusing. If False (default) will delete all except the
                first and last images from each focus run.
            take_dark (bool, optional): If True will attempt to take a dark frame
                before the focus run, and use it for dark subtraction and hot
                pixel masking, default True.
            merit_function (str/callable, optional): Merit function to use as a
                focus metric, default vollath_F4.
            merit_function_kwargs (dict, optional): Dictionary of additional
                keyword arguments for the merit function.
            mask_dilations (int, optional): Number of iterations of dilation to perform on the
                saturated pixel mask (determine size of masked regions), default 10
            spline_smoothing (float, optional): smoothing parameter for the spline fitting to
                the autofocus data, 0.0 to 1.0, smaller values mean *less* smoothing, default 0.4
            coarse (bool, optional): Whether to begin with coarse focusing, default False.
            plots (bool, optional: Whether to write focus plots to images folder, default True.
            blocking (bool, optional): Whether to block until autofocus complete, default False.

        Returns:
            threading.Event: Event that will be set when autofocusing is complete
        """
        assert self._camera.is_connected, self.logger.error(
            "Camera must be connected for autofocus!")

        assert self.is_connected, self.logger.error("Focuser must be connected for autofocus!")

        if not focus_range:
            if self.autofocus_range:
                focus_range = self.autofocus_range
            else:
                raise ValueError(
                    "No focus_range specified, aborting autofocus of {}!".format(self._camera))

        if not focus_step:
            if self.autofocus_step:
                focus_step = self.autofocus_step
            else:
                raise ValueError(
                    "No focus_step specified, aborting autofocus of {}!".format(self._camera))

        if not seconds:
            if self.autofocus_seconds:
                seconds = self.autofocus_seconds
            else:
                raise ValueError(
                    "No focus exposure time specified, aborting autofocus of {}!", self._camera)

        if not thumbnail_size:
            if self.autofocus_size:
                thumbnail_size = self.autofocus_size
            else:
                raise ValueError(
                    "No focus thumbnail size specified, aborting autofocus of {}!", self._camera)

        if keep_files is None:
            if self.autofocus_keep_files:
                keep_files = True
            else:
                keep_files = False

        if take_dark is None:
            if self.autofocus_take_dark is not None:
                take_dark = self.autofocus_take_dark
            else:
                take_dark = True

        if not merit_function:
            if self.autofocus_merit_function:
                merit_function = self.autofocus_merit_function
            else:
                merit_function = 'vollath_F4'

        if not merit_function_kwargs:
            if self.autofocus_merit_function_kwargs:
                merit_function_kwargs = self.autofocus_merit_function_kwargs
            else:
                merit_function_kwargs = {}

        if mask_dilations is None:
            if self.autofocus_mask_dilations is not None:
                mask_dilations = self.autofocus_mask_dilations
            else:
                mask_dilations = 10

        if spline_smoothing is None:
            if self.autofocus_spline_smoothing is not None:
                spline_smoothing = self.autofocus_spline_smoothing
            else:
                spline_smoothing = 0.4

        if take_dark:
            image_dir = self.config['directories']['images']
            start_time = current_time(flatten=True)
            file_path = "{}/{}/{}/{}/{}.{}".format(image_dir,
                                                   'focus',
                                                   self._camera.uid,
                                                   start_time,
                                                   "dark",
                                                   self._camera.file_extension)
            self.logger.debug('Taking dark frame {} on camera {}'.format(file_path, self._camera))
            try:
                dark_thumb = self._camera.get_thumbnail(seconds,
                                                        file_path,
                                                        thumbnail_size,
                                                        keep_file=True,
                                                        dark=True)
                # Mask 'saturated' with a low threshold to remove hot pixels
                dark_thumb = focus_utils.mask_saturated(dark_thumb, threshold=0.3)
            except TypeError:
                self.logger.warning("Camera {} does not support dark frames!".format(self._camera))
        else:
            dark_thumb = None

        if coarse:
            coarse_event = Event()
            coarse_thread = Thread(target=self._autofocus,
                                   args=args,
                                   kwargs={'seconds': seconds,
                                           'focus_range': focus_range,
                                           'focus_step': focus_step,
                                           'thumbnail_size': thumbnail_size,
                                           'keep_files': keep_files,
                                           'dark_thumb': dark_thumb,
                                           'merit_function': merit_function,
                                           'merit_function_kwargs': merit_function_kwargs,
                                           'mask_dilations': mask_dilations,
                                           'spline_smoothing': spline_smoothing,
                                           'coarse': True,
                                           'plots': plots,
                                           'start_event': None,
                                           'finished_event': coarse_event,
                                           **kwargs})
            coarse_thread.start()
        else:
            coarse_event = None

        fine_event = Event()
        fine_thread = Thread(target=self._autofocus,
                             args=args,
                             kwargs={'seconds': seconds,
                                     'focus_range': focus_range,
                                     'focus_step': focus_step,
                                     'thumbnail_size': thumbnail_size,
                                     'keep_files': keep_files,
                                     'dark_thumb': dark_thumb,
                                     'merit_function': merit_function,
                                     'merit_function_kwargs': merit_function_kwargs,
                                     'mask_dilations': mask_dilations,
                                     'spline_smoothing': spline_smoothing,
                                     'coarse': False,
                                     'plots': plots,
                                     'start_event': coarse_event,
                                     'finished_event': fine_event,
                                     **kwargs})
        fine_thread.start()

        if blocking:
            fine_event.wait()

        return fine_event

    def _autofocus(self,
                   seconds,
                   focus_range,
                   focus_step,
                   thumbnail_size,
                   keep_files,
                   dark_thumb,
                   merit_function,
                   merit_function_kwargs,
                   coarse,
                   plots,
                   start_event,
                   finished_event,
                   mask_dilations,
                   spline_smoothing,
                   *args,
                   **kwargs):
        # If passed a start_event wait until Event is set before proceeding
        # (e.g. wait for coarse focus to finish before starting fine focus).
        if start_event:
            start_event.wait()

        initial_focus = self.position
        if coarse:
            self.logger.debug(
                "Beginning coarse autofocus of {} - initial position: {}",
                self._camera, initial_focus)
        else:
            self.logger.debug(
                "Beginning autofocus of {} - initial position: {}", self._camera, initial_focus)

        # Set up paths for temporary focus files, and plots if requested.
        image_dir = self.config['directories']['images']
        start_time = current_time(flatten=True)
        file_path_root = "{}/{}/{}/{}".format(image_dir,
                                              'focus',
                                              self._camera.uid,
                                              start_time)

        # Take an image before focusing, grab a thumbnail from the centre and add it to the plot
        file_path = "{}/{}_{}.{}".format(file_path_root, initial_focus,
                                         "initial", self._camera.file_extension)
        thumbnail = self._camera.get_thumbnail(seconds, file_path, thumbnail_size, keep_file=True)

        if plots:
            thumbnail = focus_utils.mask_saturated(thumbnail)
            if dark_thumb is not None:
                thumbnail = thumbnail - dark_thumb
            fig = plt.figure(figsize=(9, 18), tight_layout=True)
            ax1 = fig.add_subplot(3, 1, 1)
            im1 = ax1.imshow(thumbnail, interpolation='none', cmap=palette, norm=colours.LogNorm())
            fig.colorbar(im1)
            ax1.set_title('Initial focus position: {}'.format(initial_focus))

        # Set up encoder positions for autofocus sweep, truncating at focus travel
        # limits if required.
        if coarse:
            focus_range = focus_range[1]
            focus_step = focus_step[1]
        else:
            focus_range = focus_range[0]
            focus_step = focus_step[0]

        focus_positions = np.arange(max(initial_focus - focus_range / 2, self.min_position),
                                    min(initial_focus + focus_range / 2, self.max_position) + 1,
                                    focus_step, dtype=np.int)
        n_positions = len(focus_positions)
        thumbnails = np.zeros((n_positions, thumbnail_size, thumbnail_size), dtype=thumbnail.dtype)
        masks = np.empty((n_positions, thumbnail_size, thumbnail_size), dtype=np.bool)
        metric = np.empty(n_positions)

        for i, position in enumerate(focus_positions):
            # Move focus, updating focus_positions with actual encoder position after move.
            focus_positions[i] = self.move_to(position)

            # Take exposure
            file_path = "{}/{}_{}.{}".format(file_path_root,
                                             focus_positions[i], i, self._camera.file_extension)
            thumbnail = self._camera.get_thumbnail(
                seconds, file_path, thumbnail_size, keep_file=keep_files)
            masks[i] = focus_utils.mask_saturated(thumbnail).mask
            if dark_thumb is not None:
                thumbnail = thumbnail - dark_thumb
            thumbnails[i] = thumbnail

        master_mask = masks.any(axis=0)
        master_mask = binary_dilation(master_mask, iterations=mask_dilations)

        for i, position in enumerate(focus_positions):
            thumbnail = np.ma.array(thumbnails[i], mask=master_mask)
            metric[i] = focus_utils.focus_metric(thumbnail, merit_function, **merit_function_kwargs)

        fitted = False

        # Find maximum values
        imax = metric.argmax()

        if imax == 0 or imax == (n_positions - 1):
            # TODO: have this automatically switch to coarse focus mode if this happens
            self.logger.warning(
                "Best focus outside sweep range, aborting autofocus on {}!".format(self._camera))
            best_focus = focus_positions[imax]

        elif not coarse:
            # Fit data around the maximum value to determine best focus position.
            # Initialise models
            shift = models.Shift(offset=-focus_positions[imax])
            poly = models.Polynomial1D(degree=4, c0=1, c1=0, c2=-1e-2, c3=0, c4=-1e-4,
                                       fixed={'c0': True, 'c1': True, 'c3': True})
            scale = models.Scale(factor=metric[imax])
            reparameterised_polynomial = shift | poly | scale

            # Initialise fitter
            fitter = fitting.LevMarLSQFitter()

            # Select data range for fitting. Tries to use 2 points either side of max, if in range.
            fitting_indices = (max(imax - 2, 0), min(imax + 2, n_positions - 1))

            # Fit models to data
            fit = fitter(reparameterised_polynomial,
                         focus_positions[fitting_indices[0]:fitting_indices[1] + 1],
                         metric[fitting_indices[0]:fitting_indices[1] + 1])

            best_focus = -fit.offset_0
            fitted = True

            # Guard against fitting failures, force best focus to stay within sweep range
            if best_focus < focus_positions[0]:
                self.logger.warning("Fitting failure: best focus {} below sweep limit {}".format(best_focus,
                                                                                                 focus_positions[0]))
                best_focus = focus_positions[1]

            if best_focus > focus_positions[-1]:
                self.logger.warning("Fitting failure: best focus {} above sweep limit {}".format(best_focus,
                                                                                                 focus_positions[-1]))
                best_focus = focus_positions[-2]

        else:
            # Coarse focus, just use max value.
            best_focus = focus_positions[imax]

        if plots:
            ax2 = fig.add_subplot(3, 1, 2)
            ax2.plot(focus_positions, metric, 'bo', label='{}'.format(merit_function))
            if fitted:
                fs = np.arange(focus_positions[fitting_indices[0]],
                               focus_positions[fitting_indices[1]] + 1)
                ax2.plot(fs, fit(fs), 'b-', label='Polynomial fit')

            ax2.set_xlim(focus_positions[0] - focus_step / 2, focus_positions[-1] + focus_step / 2)
            u_limit = 1.10 * metric.max()
            l_limit = min(0.95 * metric.min(), 1.05 * metric.min())
            ax2.set_ylim(l_limit, u_limit)
            ax2.vlines(initial_focus, l_limit, u_limit, colors='k', linestyles=':',
                       label='Initial focus')
            ax2.vlines(best_focus, l_limit, u_limit, colors='k', linestyles='--',
                       label='Best focus')
            ax2.set_xlabel('Focus position')
            ax2.set_ylabel('Focus metric')
            if coarse:
                ax2.set_title('{} coarse focus at {}'.format(self._camera, start_time))
            else:
                ax2.set_title('{} fine focus at {}'.format(self._camera, start_time))
            ax2.legend(loc='best')

        final_focus = self.move_to(best_focus)

        file_path = "{}/{}_{}.{}".format(file_path_root, final_focus,
                                         "final", self._camera.file_extension)
        thumbnail = self._camera.get_thumbnail(seconds, file_path, thumbnail_size, keep_file=True)

        if plots:
            thumbnail = focus_utils.mask_saturated(thumbnail)
            if dark_thumb is not None:
                thumbnail = thumbnail - dark_thumb
            ax3 = fig.add_subplot(3, 1, 3)
            im3 = ax3.imshow(thumbnail, interpolation='none', cmap=palette, norm=colours.LogNorm())
            fig.colorbar(im3)
            ax3.set_title('Final focus position: {}'.format(final_focus))
            if coarse:
                plot_path = file_path_root + '_coarse.png'
            else:
                plot_path = file_path_root + '_fine.png'

            fig.savefig(plot_path)
            plt.close(fig)
            if coarse:
                self.logger.info('Coarse focus plot for camera {} written to {}'.format(
                    self._camera, plot_path))
            else:
                self.logger.info('Fine focus plot for camera {} written to {}'.format(
                    self._camera, plot_path))

        self.logger.debug(
            'Autofocus of {} complete - final focus position: {}', self._camera, final_focus)

        if finished_event:
            finished_event.set()

        return initial_focus, final_focus

    def _fits_header(self, header):
        header.set('FOC-NAME', self.name, 'Focuser name')
        header.set('FOC-MOD', self.model, 'Focuser model')
        header.set('FOC-ID', self.uid, 'Focuser serial number')
        header.set('FOC-POS', self.position, 'Focuser position')
        return header

    def __str__(self):
        return "{} ({}) on {}".format(self.name, self.uid, self.port)
