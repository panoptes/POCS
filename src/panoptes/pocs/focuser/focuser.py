import os
from abc import ABCMeta
from abc import abstractmethod
from threading import Event
from threading import Thread

import numpy as np
from scipy.ndimage import binary_dilation
from astropy.modeling import models
from astropy.modeling import fitting
from panoptes.pocs.base import PanBase
from panoptes.utils.time import current_time
from panoptes.utils.images import focus as focus_utils
from panoptes.utils.images import mask_saturated
from panoptes.pocs.utils.plotting import make_autofocus_plot


class AbstractFocuser(PanBase, metaclass=ABCMeta):
    """Base class for all focusers.

    Args:
        name (str, optional): name of the focuser
        model (str, optional): model of the focuser
        port (str, optional): port the focuser is connected to, e.g. a device node
        camera (pocs.camera.Camera, optional): camera that this focuser is associated with.
        timeout (int, optional): time to wait for response from focuser.
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
        autofocus_make_plots (bool, optional: Whether to write focus plots to images folder,
            default False.
    """

    def __init__(self,
                 name='Generic Focuser',
                 model='simulator',
                 port=None,
                 camera=None,
                 timeout=5,
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
                 autofocus_make_plots=False,
                 *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.model = model
        self.port = port
        self.name = name

        self._connected = False
        self._serial_number = 'XXXXXX'

        self.timeout = timeout

        if initial_position is None:
            self._position = None
        else:
            self._position = int(initial_position)

        self._set_autofocus_parameters(autofocus_range,
                                       autofocus_step,
                                       autofocus_seconds,
                                       autofocus_size,
                                       autofocus_keep_files,
                                       autofocus_take_dark,
                                       autofocus_merit_function,
                                       autofocus_merit_function_kwargs,
                                       autofocus_mask_dilations,
                                       autofocus_make_plots)
        self._autofocus_error = None

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
            if self._camera != camera:
                self.logger.warning(f"{self} already assigned to {self._camera}, "
                                    f"skipping attempted assignment to {camera}!")
        else:
            self._camera = camera

    @abstractmethod
    def min_position(self):
        """ Get position of close limit of focus travel, in encoder units """
        raise NotImplementedError

    @abstractmethod
    def max_position(self):
        """ Get position of far limit of focus travel, in encoder units """
        raise NotImplementedError

    @abstractmethod
    def is_moving(self):
        """ True if the focuser is currently moving. """
        raise NotImplementedError

    @property
    def is_ready(self):
        # A focuser is 'ready' if it is not currently moving.
        return not self.is_moving

    @property
    def autofocus_error(self):
        """ Error message from the most recent autofocus or None, if there was no error."""
        return self._autofocus_error

    ##################################################################################################
    # Methods
    ##################################################################################################

    @abstractmethod
    def move_to(self, position):
        """ Move focuser to new encoder position.

        Args:
            position (int): new focuser position, in encoder units.

        Returns:
            int: focuser position following the move, in encoder units.
        """
        raise NotImplementedError

    def move_by(self, increment):
        """ Move focuser by a given amount.

        Args:
            increment (int): distance to move the focuser, in encoder units.

        Returns:
            int: focuser position following the move, in encoder units.
        """
        return self.move_to(self.position + increment)

    def autofocus(self,
                  seconds=None,
                  focus_range=None,
                  focus_step=None,
                  cutout_size=None,
                  keep_files=None,
                  take_dark=None,
                  merit_function=None,
                  merit_function_kwargs=None,
                  mask_dilations=None,
                  coarse=False,
                  make_plots=None,
                  filter_name=None,
                  blocking=False):
        """
        Focuses the camera using the specified merit function. Optionally performs
        a coarse focus to find the approximate position of infinity focus, which
        should be followed by a fine focus before observing.

        Args:
            seconds (scalar, optional): Exposure time for focus exposures, if not
                specified will use value from config.
            focus_range (2-tuple, optional): Coarse & fine focus sweep range, in
                encoder units. Specify to override values from config.
            focus_step (2-tuple, optional): Coarse & fine focus sweep steps, in
                encoder units. Specify to override values from config.
            cutout_size (int, optional): Size of square central region of image
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
            coarse (bool, optional): Whether to perform a coarse focus, otherwise will perform
                a fine focus. Default False.
            make_plots (bool, optional): Whether to write focus plots to images folder. If not
                given will fall back on value of `autofocus_make_plots` set on initialisation,
                and if it wasn't set then will default to False.
            filter_name (str, optional): The filter to use for focusing. If not provided, will use
                last light position.
            blocking (bool, optional): Whether to block until autofocus complete, default False.

        Returns:
            threading.Event: Event that will be set when autofocusing is complete

        Raises:
            ValueError: If invalid values are passed for any of the focus parameters.
        """
        self.logger.debug('Starting autofocus')
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

        if not cutout_size:
            if self.autofocus_size:
                cutout_size = self.autofocus_size
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

        if make_plots is None:
            make_plots = self.autofocus_make_plots

        # Move filterwheel to the correct position
        if self.camera is not None:
            if self.camera.has_filterwheel:

                if filter_name is None:
                    # NOTE: The camera will move the FW to the last light position automatically
                    self.logger.warning(f"Filter name not provided for autofocus on {self}. Using"
                                        " last light position.")
                else:
                    self.logger.info(f"Moving filterwheel to {filter_name} for autofocusing on"
                                     f" {self}.")
                    self.camera.filterwheel.move_to(filter_name, blocking=True)

            elif filter_name is None:
                self.logger.warning(f"Filter {filter_name} requiested for autofocus but"
                                    f" {self.camera} has no filterwheel.")

        # Set up the focus parameters
        focus_event = Event()
        focus_params = {
            'seconds': seconds,
            'focus_range': focus_range,
            'focus_step': focus_step,
            'cutout_size': cutout_size,
            'keep_files': keep_files,
            'take_dark': take_dark,
            'merit_function': merit_function,
            'merit_function_kwargs': merit_function_kwargs,
            'mask_dilations': mask_dilations,
            'coarse': coarse,
            'make_plots': make_plots,
            'focus_event': focus_event,
        }

        focus_thread = Thread(target=self._autofocus, kwargs=focus_params)
        focus_thread.start()

        if blocking:
            focus_event.wait()

        return focus_event

    def _autofocus(self,
                   seconds,
                   focus_range,
                   focus_step,
                   cutout_size,
                   keep_files,
                   take_dark,
                   merit_function,
                   merit_function_kwargs,
                   mask_dilations,
                   make_plots,
                   coarse,
                   focus_event,
                   *args,
                   **kwargs):
        """Private helper method for calling autofocus in a Thread.

        See public `autofocus` for information about the parameters.
        """
        focus_type = 'fine'
        if coarse:
            focus_type = 'coarse'

        initial_focus = self.position
        self.logger.debug(f"Beginning {focus_type} autofocus of {self._camera} - "
                          f"initial position: {initial_focus}")

        # Set up paths for temporary focus files, and plots if requested.
        image_dir = self.get_config('directories.images')
        start_time = current_time(flatten=True)
        file_path_root = os.path.join(image_dir, 'focus', self._camera.uid, start_time)

        self._autofocus_error = None

        dark_cutout = None
        if take_dark:
            dark_path = os.path.join(file_path_root, f'dark.{self._camera.file_extension}')
            self.logger.debug(f'Taking dark frame {dark_path} on camera {self._camera}')
            try:
                dark_cutout = self._camera.get_cutout(seconds,
                                                      dark_path,
                                                      cutout_size,
                                                      keep_file=True,
                                                      dark=True)
                # Mask 'saturated' with a low threshold to remove hot pixels
                dark_cutout = mask_saturated(dark_cutout,
                                             threshold=0.3,
                                             bit_depth=self.camera.bit_depth)
            except Exception as err:
                self.logger.error(f"Error taking dark frame: {err!r}")
                self._autofocus_error = repr(err)
                focus_event.set()
                raise err

        # Take an image before focusing, grab a cutout from the centre and add it to the plot
        initial_fn = f"{initial_focus}-{focus_type}-initial.{self._camera.file_extension}"
        initial_path = os.path.join(file_path_root, initial_fn)

        try:
            initial_cutout = self._camera.get_cutout(seconds, initial_path, cutout_size,
                                                     keep_file=True)
            initial_cutout = mask_saturated(initial_cutout, bit_depth=self.camera.bit_depth)
            if dark_cutout is not None:
                initial_cutout = initial_cutout.astype(np.int32) - dark_cutout
        except Exception as err:
            self.logger.error(f"Error taking initial image: {err!r}")
            self._autofocus_error = repr(err)
            focus_event.set()
            raise err

        # Set up encoder positions for autofocus sweep, truncating at focus travel
        # limits if required.
        if coarse:
            focus_range = focus_range[1]
            focus_step = focus_step[1]
        else:
            focus_range = focus_range[0]
            focus_step = focus_step[0]

        # Get focus steps.
        focus_positions = np.arange(max(initial_focus - focus_range / 2, self.min_position),
                                    min(initial_focus + focus_range / 2, self.max_position) + 1,
                                    focus_step, dtype=int)
        n_positions = len(focus_positions)

        # Set up empty array holders
        cutouts = np.zeros((n_positions, cutout_size, cutout_size), dtype=initial_cutout.dtype)
        masks = np.empty((n_positions, cutout_size, cutout_size), dtype=bool)
        metrics = np.empty(n_positions)

        # Take and store an exposure for each focus position.
        for i, position in enumerate(focus_positions):
            # Move focus, updating focus_positions with actual encoder position after move.
            focus_positions[i] = self.move_to(position)

            focus_fn = f"{focus_positions[i]}-{i:02d}.{self._camera.file_extension}"
            file_path = os.path.join(file_path_root, focus_fn)

            # Take exposure.
            try:
                cutouts[i] = self._camera.get_cutout(seconds, file_path, cutout_size,
                                                     keep_file=keep_files)
            except Exception as err:
                self.logger.error(f"Error taking image {i + 1}: {err!r}")
                self._autofocus_error = repr(err)
                focus_event.set()
                raise err

            masks[i] = mask_saturated(cutouts[i], bit_depth=self.camera.bit_depth).mask

        self.logger.debug(f'Making master mask with binary dilation for {self._camera}')
        master_mask = masks.any(axis=0)
        master_mask = binary_dilation(master_mask, iterations=mask_dilations)

        # Apply the master mask and then get metrics for each frame.
        for i, cutout in enumerate(cutouts):
            self.logger.debug(f'Applying focus metric to cutout {i:02d}')
            if dark_cutout is not None:
                cutout = cutout.astype(np.float32) - dark_cutout
            cutout = np.ma.array(cutout, mask=np.ma.mask_or(master_mask, np.ma.getmask(cutout)))
            metrics[i] = focus_utils.focus_metric(cutout, merit_function, **merit_function_kwargs)
            self.logger.debug(f'Focus metric for cutout {i:02d}: {metrics[i]}')

        # Only fit a fine focus.
        fitted = False
        fitting_indices = [None, None]

        # Find maximum metric values.
        imax = metrics.argmax()

        if imax == 0 or imax == (n_positions - 1):
            # TODO: have this automatically switch to coarse focus mode if this happens
            self.logger.warning(f"Best focus outside sweep range, stopping focus and using"
                                f" {focus_positions[imax]}")
            best_focus = focus_positions[imax]

        elif not coarse:
            # Fit data around the maximum value to determine best focus position.
            # Initialise models
            shift = models.Shift(offset=-focus_positions[imax])
            # Small initial coeffs with expected sign. Helps fitting start in the right direction.
            poly = models.Polynomial1D(degree=4, c0=1, c1=0, c2=-1e-2, c3=0, c4=-1e-4,
                                       fixed={'c0': True, 'c1': True, 'c3': True})
            scale = models.Scale(factor=metrics[imax])
            # https://docs.astropy.org/en/stable/modeling/compound-models.html?#model-composition
            reparameterised_polynomial = shift | poly | scale

            # Initialise fitter
            fitter = fitting.LevMarLSQFitter()

            # Select data range for fitting. Tries to use 2 points either side of max, if in range.
            fitting_indices = (max(imax - 2, 0), min(imax + 2, n_positions - 1))

            # Fit models to data
            fit = fitter(reparameterised_polynomial,
                         focus_positions[fitting_indices[0]:fitting_indices[1] + 1],
                         metrics[fitting_indices[0]:fitting_indices[1] + 1])

            # Get the encoder position of the best focus.
            best_focus = np.abs(fit.offset_0)
            fitted = True

            # Guard against fitting failures, force best focus to stay within sweep range.
            min_focus = focus_positions[0]
            max_focus = focus_positions[-1]
            if best_focus < min_focus:
                self.logger.warning(f"Fitting failure: best focus {best_focus} below sweep limit"
                                    f" {min_focus}")
                best_focus = focus_positions[1]

            if best_focus > max_focus:
                self.logger.warning(f"Fitting failure: best focus {best_focus} above sweep limit"
                                    f" {max_focus}")
                best_focus = focus_positions[-2]

        else:
            # Coarse focus, just use max value.
            best_focus = focus_positions[imax]

        # Move the focuser to best focus position.
        final_focus = self.move_to(best_focus)

        # Get final cutout.
        final_fn = f"{final_focus}-{focus_type}-final.{self._camera.file_extension}"
        file_path = os.path.join(file_path_root, final_fn)
        try:
            final_cutout = self._camera.get_cutout(seconds, file_path, cutout_size,
                                                   keep_file=True)
            final_cutout = mask_saturated(final_cutout, bit_depth=self.camera.bit_depth)
            if dark_cutout is not None:
                final_cutout = final_cutout.astype(np.int32) - dark_cutout
        except Exception as err:
            self.logger.error(f"Error taking final image: {err!r}")
            self._autofocus_error = repr(err)
            focus_event.set()
            raise err

        if make_plots:
            line_fit = None
            if fitted:
                focus_range = np.arange(focus_positions[fitting_indices[0]],
                                        focus_positions[fitting_indices[1]] + 1)
                fit_line = fit(focus_range)
                line_fit = [focus_range, fit_line]

            plot_title = f'{self._camera} {focus_type} focus at {start_time}'

            # Make the plots
            plot_path = os.path.join(file_path_root, f'{focus_type}-focus.png')
            plot_path = make_autofocus_plot(plot_path,
                                            initial_cutout,
                                            final_cutout,
                                            initial_focus,
                                            final_focus,
                                            focus_positions,
                                            metrics,
                                            merit_function,
                                            plot_title=plot_title,
                                            line_fit=line_fit
                                            )

            self.logger.info(f"{focus_type.capitalize()} focus plot for {self._camera} written to "
                             f" {plot_path}")

        self.logger.debug(f"Autofocus of {self._camera} complete - final focus"
                          f" position: {final_focus}")

        if focus_event:
            focus_event.set()

        return initial_focus, final_focus

    def _set_autofocus_parameters(self,
                                  autofocus_range,
                                  autofocus_step,
                                  autofocus_seconds,
                                  autofocus_size,
                                  autofocus_keep_files,
                                  autofocus_take_dark,
                                  autofocus_merit_function,
                                  autofocus_merit_function_kwargs,
                                  autofocus_mask_dilations,
                                  autofocus_make_plots):
        # Moved to a separate private method to make it possible to override.
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
        self.autofocus_make_plots = bool(autofocus_make_plots)

    def _add_fits_keywords(self, header):
        header.set('FOC-NAME', self.name, 'Focuser name')
        header.set('FOC-MOD', self.model, 'Focuser model')
        header.set('FOC-ID', self.uid, 'Focuser serial number')
        header.set('FOC-POS', self.position, 'Focuser position')
        return header

    def __str__(self):
        try:
            s = "{} ({}) on {}".format(self.name, self.uid, self.port)
        except Exception:
            s = str(__class__)

        return s
