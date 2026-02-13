"""Core orchestration for running a PANOPTES unit.

Defines the POCS state machine class, which coordinates an Observatory instance
and manages the high-level observing loop, safety checks, and lifecycle.
"""

import os
from contextlib import suppress
from multiprocessing import Process
from zoneinfo import ZoneInfo

from astropy import units as u
from astropy.time import Time
from panoptes.utils.time import CountdownTimer, current_time
from panoptes.utils.utils import get_free_space

from panoptes.pocs.base import PanBase
from panoptes.pocs.hardware import get_simulator_names
from panoptes.pocs.observatory import Observatory
from panoptes.pocs.scheduler.observation.base import Observation
from panoptes.pocs.state.machine import PanStateMachine
from panoptes.pocs.utils import error


class POCS(PanStateMachine, PanBase):
    """The main class representing the Panoptes Observatory Control Software (POCS).

    Interaction with a PANOPTES unit is done through instances of this class. An instance consists
    primarily of an `Observatory` object, which contains the mount, cameras, scheduler, etc.
    See `pocs.Observatory`. The observatory should create all attached hardware
    but leave the initialization up to POCS (i.e. this class will call the observatory
    `initialize` method).

    The POCS instance itself is designed to be run as a state machine via
    the `run` method.

    Args:
        observatory(Observatory): An instance of a `pocs.observatory.Observatory`
            class. POCS will call the `initialize` method of the observatory.
        state_machine_file(str): Filename of the state machine to use, defaults to
            'panoptes'.
        simulators(list): A list of the different modules that can run in simulator mode. Possible
            modules include: all, mount, camera, weather, night. Defaults to an empty list.

    Attributes:
        name (str): Name of PANOPTES unit
        observatory (`pocs.observatory.Observatory`): The `~pocs.observatory.Observatory` object

    """

    def __init__(self, observatory, state_machine_file=None, simulators=None, *args, **kwargs):
        # Explicitly call the base class.
        PanBase.__init__(self, *args, **kwargs)

        simulators = self.set_config("simulator", simulators)["simulator"]
        if simulators and len(simulators) > 0:
            print(f"Running POCS with simulators: {simulators=}")
            self.logger.warning(f"Using {simulators=}")

        assert isinstance(observatory, Observatory)

        self.name = self.get_config("name", default="Generic PANOPTES Unit")
        self.unit_id = self.get_config("pan_id", default="PAN000")
        location = self.get_config("location.name", default="Unknown location")
        self.logger.info(f"Initializing PANOPTES unit - {self.name} {self.unit_id} - {location}")

        if state_machine_file is None:
            state_machine_file = self.get_config("state_machine", default="panoptes")

        self.logger.info(f"Making a POCS state machine from {state_machine_file}")
        PanStateMachine.__init__(self, state_machine_file, **kwargs)

        # Add observatory object, which does the bulk of the work.
        self.observatory = observatory

        self.is_initialized = False
        self._free_space = None

        self.run_once = kwargs.get("run_once", False)
        self._obs_run_retries = self.get_config("pocs.RETRY_ATTEMPTS", default=3)
        self.connected = True
        self.interrupted = False

        self.say("Hi there!")

    @property
    def is_initialized(self):
        """Indicates if POCS has been initialized or not"""
        return self.get_config("pocs.INITIALIZED", default=False)

    @is_initialized.setter
    def is_initialized(self, new_value):
        """Set initialization flag.

        Args:
            new_value (bool): True if POCS has finished initialization.
        """
        self.set_config("pocs.INITIALIZED", new_value)

    @property
    def interrupted(self):
        """If POCS has been interrupted.

        Returns:
            bool: If an interrupt signal has been received
        """
        return self.get_config("pocs.INTERRUPTED", default=False)

    @interrupted.setter
    def interrupted(self, new_value):
        """Mark POCS as interrupted.

        Args:
            new_value (bool): True if an interrupt signal has been received.
        """
        self.set_config("pocs.INTERRUPTED", new_value)
        if new_value:
            self.logger.critical("POCS has been interrupted")

    @property
    def connected(self):
        """Indicates if POCS is connected"""
        return self.get_config("pocs.CONNECTED", default=False)

    @connected.setter
    def connected(self, new_value):
        """Set connection status flag.

        Args:
            new_value (bool): True if POCS is connected to required services.
        """
        self.set_config("pocs.CONNECTED", new_value)

    @property
    def do_states(self):
        """Whether the state machine should currently process states.

        Returns:
            bool: True if state transitions should be executed.
        """
        return self.get_config("pocs.DO_STATES", default=True)

    @do_states.setter
    def do_states(self, new_value):
        """Enable or disable state-machine processing.

        Args:
            new_value (bool): True to process state transitions; False to pause.
        """
        self.set_config("pocs.DO_STATES", new_value)

    @property
    def keep_running(self):
        """If POCS should keep running.

        Currently reads:

        * `connected`
        * `do_states`
        * `observatory.can_observe`

        Returns:
            bool: If POCS should keep running.
        """
        return self.connected and self.do_states and self.observatory.can_observe

    @property
    def run_once(self):
        """If POCS should exit the run loop after a single iteration.

        This value reads the `pocs.RUN_ONCE` config value.

        Returns:
            bool: if machine should stop after single iteration, default False.
        """
        return self.get_config("pocs.RUN_ONCE", default=False)

    @run_once.setter
    def run_once(self, new_value):
        """Set whether to exit the run loop after a single iteration.

        Args:
            new_value (bool): True to perform only one run loop iteration.
        """
        self.set_config("pocs.RUN_ONCE", new_value)

    @property
    def should_retry(self):
        """Whether the observing loop should attempt another iteration.

        Returns:
            bool: True if remaining retry attempts are available; otherwise False.
        """
        return self._obs_run_retries >= 0

    @property
    def status(self) -> dict:
        """Assemble a nested status dictionary for the running system.

        Returns:
            dict: A JSON-serializable mapping containing current state, next state,
                coarse system metrics (e.g., free space), and the observatory status.
        """
        try:
            status = {
                "state": self.state,
                "next_state": self.next_state,
                "system": {
                    "free_space": str(self._free_space),
                },
                "observatory": self.observatory.status,
            }
            self.db.insert_current("status", status, store_permanently=False)
            return status
        except Exception as e:  # pragma: no cover
            self.logger.warning(f"Can't get status: {e!r}")
            return {}

    def update_status(self) -> dict:
        """Thin-wrapper around status property.

        This method will update the status of the system in the database.
        """
        return self.status

    ################################################################################################
    # Methods
    ################################################################################################

    def initialize(self):
        """Initialize POCS.

        Calls the Observatory `initialize` method.

        Returns:
            bool: True if all initialization succeeded, False otherwise.
        """

        if not self.observatory.can_observe:
            self.say("Looks like we're missing some required hardware.")
            return False

        if not self.is_initialized:
            self.logger.info("*" * 80)
            self.say("Initializing the system! Woohoo!")

            try:
                self.logger.debug("Initializing observatory")
                self.observatory.initialize()

            except Exception as e:
                self.say(f"Oh wait. There was a problem initializing: {e!r}")
                self.say("Since we didn't initialize, I'm going to exit.")
                self.power_down()
            else:
                self.is_initialized = True
                self.do_states = True

        return self.is_initialized

    def say(self, msg):
        """PANOPTES Units like to talk!

        Send a message.

        Args:
            msg(str): Message to be sent to logs.
        """
        self.logger.success(f"{self.unit_id} says: {msg}")

    def power_down(self):
        """Actions to be performed upon shutdown

        Note:
            This method is automatically called from the interrupt handler. The definition should
            include what you want to happen upon shutdown but you don't need to worry about calling
            it manually.
        """
        if self.connected:
            self.say("I'm powering down")
            self.logger.info(f"Shutting down {self.name}, please be patient and allow for exit.")

            if not self.observatory.close_dome():
                self.logger.critical("Unable to close dome!")

            # Park if needed
            if self.state not in ["parking", "parked", "sleeping", "housekeeping"]:
                # TODO(jamessynge): Figure out how to handle the situation where we have both
                # mount and dome, but this code is only checking for a mount.
                if self.observatory.mount.is_connected:
                    if not self.observatory.mount.is_parked:
                        self.logger.info("Parking mount")
                        self.park()

            if self.state == "parking":
                if self.observatory.mount.is_connected:
                    if self.observatory.mount.is_parked:
                        self.logger.info("Mount is parked, setting state to 'parked'")
                        self.set_park()

            if self.observatory.mount and self.observatory.mount.is_parked is False:
                self.logger.info("Mount not parked, parking")
                self.observatory.mount.park()

            # Observatory shut down; will wait for cameras to finish exposing.
            self.observatory.power_down()

            self.connected = False

            # Clear all the config items.
            self.logger.success("Power down complete")

    def reset_observing_run(self):
        """Reset an observing run loop."""
        self.logger.debug("Resetting observing run attempts")
        self._obs_run_retries = self.get_config("pocs.RETRY_ATTEMPTS", default=3)

    def observe_target(self, observation: Observation | None = None, park_if_unsafe: bool = True):
        """Observe something! 🔭🌠

        Note: This is a long-running blocking method.

        This is a high-level method to call the various `observation` methods that
        allow for observing.
        """
        current_observation = observation or self.observatory.current_observation
        self.say(f"Observing {current_observation}")

        for pic_num in range(current_observation.min_nexp):
            self.logger.debug(f"Starting observation {pic_num} of {current_observation.min_nexp}")
            if self.is_safe() is False:
                self.say(f"Safety warning! Stopping {current_observation}.")
                if park_if_unsafe:
                    self.say("Parking the mount!")
                    self.observatory.mount.park()
                break

            if not self.observatory.mount.is_tracking:
                self.say("Mount is not tracking, stopping observations.")
                break

            # Do the observing, once per exptime (usually only one unless a compound observation).
            for exptime in current_observation.exptimes:
                self.logger.info(
                    f"Starting {pic_num:03d} of {current_observation.min_nexp:03d} with {exptime=}"
                )

                status = self.status
                self.logger.debug(f"Status before starting observation: {status}")

                try:
                    self.observatory.take_observation(blocking=True)
                except error.CameraNotFound:
                    self.logger.error("No cameras available, stopping observation")
                    break

                # Do processing in background.
                process_proc = Process(target=self.observatory.process_observation)
                process_proc.start()
                self.logger.debug(f"Processing {current_observation} on {process_proc.pid=}")

            pic_num += 1

    ################################################################################################
    # Safety Methods
    ################################################################################################

    def is_safe(self, no_warning=False, horizon="observe", ignore=None, park_if_not_safe=True):
        """Checks the safety flag of the system to determine if safe.

        This will check the weather station as well as various other environmental
        aspects of the system in order to determine if conditions are safe for operation.

        Note:
            This condition is called by the state machine during each transition.

        Args:
            no_warning (bool, optional): If a warning message should show in logs,
                defaults to False.
            horizon (str, optional): For nighttime check use given horizon,
                default 'observe'.
            ignore (abc.Iterable, optional): A list of safety checks to ignore when deciding
                whether it is safe or not. Valid list entries are: 'ac_power', 'is_dark',
                'good_weather', 'free_space_root' and 'free_space_images'. Useful e.g. when
                the state machine needs to wait for dark to enter the next state.
            park_if_not_safe (bool, optional): If True (default), will go to park if safety check
                fails. Set to False if you want to check the safety without sending the state
                machine to parking.
        Returns:
            bool: Latest safety flag.
        """
        if not self.connected:
            return False
        if ignore is None:
            ignore = list()

        is_safe_values = dict()

        # Check if AC power connected and return immediately if not.
        has_power = self.has_ac_power()
        if not has_power:
            return False

        is_safe_values["ac_power"] = has_power

        # Check if nighttime
        is_safe_values["is_dark"] = self.is_dark(horizon=horizon)

        # Check weather
        is_safe_values["good_weather"] = self.is_weather_safe()

        # Hard-drive space in root
        is_safe_values["free_space_root"] = self.has_free_space("/")

        # Hard-drive space in images directory.
        images_dir = self.get_config("directories.images")
        is_safe_values["free_space_images"] = self.has_free_space(images_dir)

        # Check overall safety, ignoring some checks if necessary
        missing_keys = [k for k in ignore if k not in is_safe_values.keys()]
        if missing_keys:
            self.logger.warning(
                "Found the following invalid checks to ignore in "
                f"is_safe: {missing_keys}. Valid keys are: "
                f"{list(is_safe_values.keys())}."
            )
        safe = all([v for k, v in is_safe_values.items() if k not in ignore])

        # Insert safety reading
        self.db.insert_current("safety", is_safe_values, store_permanently=False)

        if not safe:
            if no_warning is False:
                self.logger.warning(f"Unsafe conditions: {is_safe_values}")

            # These states are already "parked" so don't send to parking.
            state_always_safe = self.get_state(self.state).is_always_safe
            if not state_always_safe and park_if_not_safe:
                self.logger.warning(f'Safety failed, setting {self.next_state=} to "parking"')
                self.next_state = "parking"

        self.update_status()
        return safe

    def _in_simulator(self, key):
        """Checks the config server for the given simulator key value."""
        with suppress(KeyError):
            if key in self.get_config("simulator", default=list()):
                self.logger.debug(f"Using {key} simulator")
                return True

        return False

    def is_dark(self, horizon="observe"):
        """Is it dark

        Checks whether it is dark at the location provided. This checks for the config
        entry `location.flat_horizon` by default.

        Args:
            horizon (str, optional): Which horizon to use, 'flat', 'focus', or
                'observe' (default).

        Returns:
            bool: Is sun below horizon at location
        """
        # See if dark - we check this first because we want to know
        # the sun position even if using a simulator.
        is_dark = self.observatory.is_dark(horizon=horizon)
        self.logger.debug(f"Observatory is_dark: {is_dark}")

        if self._in_simulator("night"):
            return True

        self.logger.debug(f"Dark Check: {is_dark}")
        return is_dark

    def is_weather_safe(self, stale=180):
        """Determines whether current weather conditions are safe or not.

        Args:
            stale (int, optional): Number of seconds before record is stale, defaults to 180

        Returns:
            bool: Conditions are safe (True) or unsafe (False)

        """

        # Always assume False
        self.logger.debug("Checking weather safety")

        if self._in_simulator("weather"):
            return True

        # Get current weather readings from database
        is_safe = False
        try:
            record = self.db.get_current("weather")
            if record is None:
                return False

            is_safe = False
            for key in ["safe", "is_safe"]:
                with suppress(KeyError):
                    is_safe = bool(record["data"][key])

            tz = ZoneInfo(self.get_config("location.timezone", default="UTC"))

            timestamp = Time(record["data"]["timestamp"].replace(tzinfo=tz))
            age = (current_time().datetime - timestamp.datetime).total_seconds()

            self.logger.debug(f"Weather Safety: {is_safe=} {age=:.0f}s [{timestamp}]")

        except Exception as e:  # pragma: no cover
            self.logger.error(f"No weather record in database: {e!r}")
        else:
            if age >= stale:
                self.logger.warning("Weather record looks stale, marking unsafe.")
                is_safe = False

        return is_safe

    def has_free_space(
        self, directory=None, required_space=0.25 * u.gigabyte, low_space_percent=1.5
    ):
        """Does hard drive have disk space (>= 0.5 GB).

        Args:
            directory (str, optional): The path to check free space on, the default
                `None` will check `$PANDIR`.
            required_space (u.gigabyte, optional): Amount of free space required
                for operation
            low_space_percent (float, optional): Give warning if space is less
                than this times the required space, default 1.5, i.e.,
                the logs will show a warning at `.25 GB * 1.5 = 0.375 GB`.

        Returns:
            bool: True if enough space
        """
        directory = directory or os.getenv("PANDIR")
        req_space = required_space.to(u.gigabyte)
        self._free_space = get_free_space(directory=directory)

        space_is_low = self._free_space.value <= (req_space.value * low_space_percent)

        # Explicitly cast to bool (instead of numpy.bool)
        has_space = bool(self._free_space.value >= req_space.value)

        if not has_space:
            self.logger.error(
                f"No disk space for directory={directory!r}: "
                f"Free {self._free_space:.02f}\t req_space={req_space:.02f}"
            )
        elif space_is_low:  # pragma: no cover
            self.logger.warning(
                f"Low disk space for directory={directory!r}: "
                f"Free {self._free_space:.02f}\t req_space={req_space:.02f}"
            )

        return has_space

    def has_ac_power(self, stale=90):
        """Check for system AC power.

        Power readings are done by the arduino and are placed in the metadata
        database. This method looks for entries saved with type `power` and key
        `main` the `current` collection. The method will also return False if
        the record is older than `stale` seconds.

        Args:
            stale (int, optional): Number of seconds before record is stale,
                defaults to 90 seconds.

        Returns:
            bool: True if system AC power is present.
        """
        # Always assume False
        self.logger.debug("Checking for AC power")
        has_power = False

        if self._in_simulator("power"):
            return True

        # Get current power readings from database
        try:
            record = self.db.get_current("power")
            if record is None:
                self.logger.warning('No mains "power" reading found in database.')

            has_power = False  # Assume not.
            for power_key in ["main", "mains", "ac_ok"]:  # Legacy support.
                with suppress(KeyError):
                    has_power = bool(record["data"][power_key])

            date = record["date"].replace(tzinfo=None)  # current_time is timezone naive
            age = (current_time().datetime - date).total_seconds()

            self.logger.debug(f"Power Safety: {has_power} [{age:.0f}s old - {date:%m-%d %H:%M:%S}]")

        except (TypeError, KeyError) as e:
            self.logger.warning(f"No record found in DB: {e!r}")
        except Exception as e:  # pragma: no cover
            self.logger.error(f"Error checking weather: {e!r}")
        else:
            if age > stale:
                self.logger.warning("Power record looks stale, marking unsafe.")
                has_power = False

        if not has_power:
            self.logger.critical("AC power not detected.")

        return has_power

    ################################################################################################
    # Convenience Methods
    ################################################################################################

    def wait(self, delay=None):
        """Send POCS to wait.

        Loops for `delay` number of seconds. If `delay` is more than 30.0 seconds,
        then check for status signals (which are updated every 60 seconds by default).

        Keyword Arguments:
            delay {float|None} -- Number of seconds to wait. If default `None`, look up value in
                config, otherwise 2.5 seconds.
        """
        if delay is None:  # pragma: no cover
            delay = self.get_config("wait_delay", default=2.5)

        timer_name = "POCSWait"
        sleep_timer = CountdownTimer(delay, name=timer_name)
        self.logger.info(f"Starting {timer_name} timer of {delay} seconds")
        while not sleep_timer.expired() and not self.interrupted:
            self.logger.debug(f"POCS status: {self.status}")
            self.logger.debug(f"{timer_name}: {sleep_timer.time_left():.02f} / {delay:.02f}")
            sleep_timer.sleep(max_sleep=30)

        is_expired = sleep_timer.expired()
        self.logger.debug(f"Leaving wait timer: {is_expired}")
        return is_expired

    ################################################################################################
    # Class Methods
    ################################################################################################

    @classmethod
    def from_config(cls, simulators: list[str] = None):
        """Create a new POCS instance using the config system.

        Args:
            simulators (List[str], optional): A list of the different modules that can run in
                simulator mode. Possible modules include: all, mount, camera, weather, night.
                Defaults to an empty list.
        """
        if simulators is None:
            simulators = list()

        if simulators == "all":
            simulators = get_simulator_names("all")

        try:
            from panoptes.pocs.camera import create_cameras_from_config
            from panoptes.pocs.camera.simulator.dslr import Camera as SimCamera
            from panoptes.pocs.mount import create_mount_from_config, create_mount_simulator
            from panoptes.pocs.scheduler import (
                create_location_from_config,
                create_scheduler_from_config,
            )
        except ImportError:
            print("Cannot import helper modules.")
        else:
            try:
                scheduler = create_scheduler_from_config()
                location = create_location_from_config()

                if "mount" in simulators:
                    mount = create_mount_simulator(earth_location=location.earth_location)
                else:
                    mount = create_mount_from_config()

                if "camera" in simulators:
                    # Make two DSLR cameras in simulator mode.
                    cameras = {f"Cam{i:02d}": SimCamera(name=f"Cam{i:02d}") for i in range(2)}
                else:
                    cameras = create_cameras_from_config()

                observatory = Observatory(cameras=cameras, mount=mount, scheduler=scheduler)
                pocs = cls(observatory, simulators=simulators or list())
                return pocs
            except Exception as e:
                raise error.PanError(f"Problem creating POCS: {e!r}")
