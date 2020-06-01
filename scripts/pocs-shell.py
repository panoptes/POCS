#!/usr/bin/env python3
import readline
import time

from cmd import Cmd
from pprint import pprint

from astropy.utils import console

from panoptes.pocs import hardware
from panoptes.pocs.core import POCS
from panoptes.pocs.observatory import Observatory
from panoptes.utils import current_time
from panoptes.utils import string_to_params
from panoptes.utils import error
from panoptes.utils import images as img_utils
from panoptes.utils.config import client

from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.camera import create_cameras_from_config
from panoptes.pocs.scheduler import create_scheduler_from_config


class PocsShell(Cmd):
    """A simple command loop for running the PANOPTES Observatory Control System."""

    intro = 'Welcome to POCS Shell! Type ? for help'
    prompt = 'POCS > '
    procs = dict()
    pocs = None

    _running = False

    msg_subscriber = None
    msg_publisher = None
    cmd_publisher = None

    cmd_pub_port = 6500
    cmd_sub_port = 6501
    msg_pub_port = 6510
    msg_sub_port = 6511

    @property
    def is_setup(self):
        """True if POCS is setup, False otherwise."""
        if self.pocs is None:
            print_warning('POCS has not been setup. Please run `setup_pocs`')
            return False
        return True

    @property
    def is_safe(self):
        """True if POCS is setup and weather conditions are safe, False otherwise."""
        return self.is_setup and self.pocs.is_safe()

    @property
    def ready(self):
        """True if POCS is ready to observe, False otherwise."""
        if not self.is_setup:
            print_info(f'Mount not setup, system not ready.')
            return False

        if self.pocs.observatory.mount.is_parked:
            print_warning('Mount is parked. To unpark run `unpark`')
            return False

        return self.pocs.is_safe()

    def do_setup_pocs(self, *arg):
        """Setup and initialize a POCS instance."""
        args, kwargs = string_to_params(*arg)

        simulator = kwargs.get('simulator', list())
        if isinstance(simulator, str):
            simulator = [simulator]

        # Set whatever simulators were passed during setup
        client.set_config('simulator', simulator)
        # Retrieve what was set
        simulators = client.get_config('simulator', default=list())
        if len(simulators):
            print_warning(f'Using simulators: {simulators}')

        if 'POCSTIME' in os.environ:
            print_warning("Clearing POCSTIME variable")
            del os.environ['POCSTIME']

        try:
            mount = create_mount_from_config()
            cameras = create_cameras_from_config()
            scheduler = create_scheduler_from_config()

            observatory = Observatory(mount=mount, cameras=cameras, scheduler=scheduler)
            self.pocs = POCS(observatory)
            self.pocs.initialize()
        except error.PanError as e:
            print_warning('Problem setting up POCS: {}'.format(e))

    def help_setup_pocs(self):
        print('''Setup and initialize a POCS instance.

    setup_pocs [simulate]

simulate is a space-separated list of hardware to simulate.
Hardware names: {}   (or all for all hardware)'''.format(
            ','.join(hardware.get_all_names())))

    def complete_setup_pocs(self, text, line, begidx, endidx):
        """Provide completions for simulator names."""
        names = ['all'] + hardware.get_all_names()
        return [name for name in names if name.startswith(text)]

    def do_reset_pocs(self, *arg):
        """Discards the POCS instance.

        Does NOT park the mount, nor execute power_down.
        """
        if self.pocs is None:
            print_info("POCS does not have an instance. Create one using 'setup_pocs'.")
            return
        elif self.pocs.observatory.mount and not self.pocs.observatory.mount.is_parked:
            print_warning("ATTENTION: The mount is not in the parked position!")
            print_warning("ATTENTION: reset_pocs will not move the mount to park position!")
            print_warning("ATTENTION: The unit could be damaged if not parked before sunrise.")
            while True:
                response = input("Execute reset_pocs anyway [y/n]?")
                if response.lower().startswith('y'):
                    self.pocs = None
                    print_info("POCS instance discarded. Remember to park the mount later.")
                    break
                elif response.lower().startswith('n'):
                    print_info("Keeping POCS instance.")
                    break
                else:
                    print("A 'yes' or 'no' response is required")

        self.pocs = None

    def do_run_pocs(self, *arg):
        """Make POCS `run` the state machine.

        Continues until the user presses Ctrl-C or the state machine
        exits, such as due to an error."""
        if self.pocs is not None:
            print_info("Starting POCS - Press Ctrl-c to interrupt")

            try:
                self.pocs.run()
            except KeyboardInterrupt:
                print_warning('POCS interrupted, parking')
                if self.pocs.state not in ['sleeping', 'housekeeping', 'parked', 'parking']:
                    self.pocs.park()
                else:
                    self.pocs.observatory.mount.home_and_park()
                self._obs_run_retries = 0  # Don't retry
            finally:
                print_info('POCS stopped.')
        else:
            print_warning('Please run `setup_pocs` before trying to run')

    def do_status(self, *arg):
        """Print the `status` for pocs."""
        if self.pocs is None:
            print_warning('Please run `setup_pocs` before trying to run')
            return
        status = self.pocs.status
        print()
        pprint(status)
        print()

    def do_exit(self, *arg):
        """Exits PocsShell."""
        if self.pocs is not None:
            self.do_power_down()

        print_info("Bye! Thanks!")
        return True

    def emptyline(self):
        """Do nothing.

        Without this, Cmd would repeat the last command."""
        pass

    def do_unpark(self, *arg):
        """Release the mount so that it can be moved."""
        try:
            self.pocs.observatory.mount.unpark()
            self.pocs.say("Unparking mount")
        except Exception as e:
            print_warning('Problem unparking: {}'.format(e))

    def do_park(self, *arg):
        """Park the mount."""
        try:
            self.pocs.observatory.mount.park()
            self.pocs.say("Mount parked")
        except Exception as e:
            print_warning('Problem parking: {}'.format(e))

    def do_go_home(self, *arg):
        """Move the mount to home."""
        if self.ready is False:
            print_info(f"POCS not ready, can't go home. Checking weather")
            if self.pocs.is_weather_safe() is False:
                print_info(f'Weather is not safe, powering down.')
                self.do_power_down()

            print_info(f'Unable to go to home.')
            return

        try:
            self.pocs.observatory.mount.slew_to_home(blocking=True)
        except Exception as e:
            print_warning('Problem slewing to home: {}'.format(e))

    def do_open_dome(self, *arg):
        """Open the dome, if there is one."""
        if not self.is_setup:
            return
        if not self.pocs.observatory.has_dome:
            print_warning('There is no dome.')
            return
        if not self.pocs.is_weather_safe():
            print_warning('Weather conditions are not good, not opening dome.')
            return
        try:
            if self.pocs.observatory.open_dome():
                print_info('Opened the dome.')
            else:
                print_warning('Failed to open the dome.')
        except Exception as e:
            print_warning('Problem opening the dome: {}'.format(e))

    def do_close_dome(self, *arg):
        """Close the dome, if there is one."""
        if not self.is_setup:
            return
        if not self.pocs.observatory.has_dome:
            print_warning('There is no dome.')
            return
        try:
            if self.pocs.observatory.close_dome():
                print_info('Closed the dome.')
            else:
                print_warning('Failed to close the dome.')
        except Exception as e:
            print_warning('Problem closing the dome: {}'.format(e))

    def do_power_down(self, *arg):
        """Power down the mount; waits until the mount is parked."""
        print_info("Shutting down POCS instance, please wait")
        self.pocs.power_down()

        while self.pocs.observatory.mount.is_parked is False:
            print_info('.')
            time.sleep(5)

        self.pocs = None

    def do_polar_alignment_test(self, *arg):
        """Capture images of the pole and compute alignment of mount."""
        if self.ready is False:
            return

        args, kwargs = string_to_params(*arg)

        # Default to 30 seconds
        exptime = kwargs.get('exptime', 30)

        start_time = current_time(flatten=True)

        base_dir = '{}/images/drift_align/{}'.format(
            os.getenv('PANDIR'), start_time)
        plot_fn = '{}/{}_center_overlay.jpg'.format(base_dir, start_time)

        mount = self.pocs.observatory.mount

        print_info("Moving to home position")
        self.pocs.say("Moving to home position")
        mount.slew_to_home(blocking=True)

        # Polar Rotation
        pole_fn = polar_rotation(self.pocs, exptime=exptime, base_dir=base_dir)
        pole_fn = pole_fn.replace('.cr2', '.fits')

        # Mount Rotation
        rotate_fn = mount_rotation(self.pocs, base_dir=base_dir)
        rotate_fn = rotate_fn.replace('.cr2', '.fits')

        print_info("Moving back to home")
        self.pocs.say("Moving back to home")
        mount.slew_to_home(blocking=True)

        print_error(f'NO POLAR UTILS RIGHT NOW')
        return

        print_info("Done with polar alignment test")
        self.pocs.say("Done with polar alignment test")


def polar_rotation(pocs, exptime=30, base_dir=None, **kwargs):
    assert base_dir is not None, print_warning("base_dir cannot be empty")

    mount = pocs.observatory.mount

    print_info('Performing polar rotation test')
    pocs.say('Performing polar rotation test')
    mount.slew_to_home(blocking=True)

    print_info('At home position, taking {} sec exposure'.format(exptime))
    pocs.say('At home position, taking {} sec exposure'.format(exptime))

    cam = pocs.observatory.primary_camera
    analyze_fn = f'{base_dir}/pole_{cam.name.lower()}.cr2'
    cam_event = cam.take_exposure(seconds=exptime, filename=analyze_fn)

    while cam_event.is_set() is False:
        time.sleep(2)

    try:
        img_utils.make_pretty_image(analyze_fn,
                                    title='Alignment Test - Celestial Pole',
                                    link_path=os.path.expandvars('$PANDIR/images/latest.jpg'),
                                    primary=True)
    except AssertionError:
        print_warning(f"Can't make image for {analyze_fn}")
        pocs.say(f"Can't make image for {analyze_fn}")

    return analyze_fn


def mount_rotation(pocs, base_dir=None, include_west=False, **kwargs):
    mount = pocs.observatory.mount

    print_info("Doing rotation test")
    pocs.say("Doing rotation test")
    mount.slew_to_home(blocking=True)
    exptime = 25
    mount.move_direction(direction='west', seconds=11)

    # Start exposing on cameras
    for direction in ['east', 'west']:
        if include_west is False and direction == 'west':
            continue

        print_info(f"Rotating to {direction}")
        pocs.say(f"Rotating to {direction}")

        cam = pocs.observatory.primary_camera
        rotate_fn = f'{base_dir}/rotation_{direction}_{cam.name.lower()}.cr2'
        cam_event = cam.take_exposure(seconds=exptime, filename=rotate_fn)

        # Move mount
        mount.move_direction(direction=direction, seconds=21)

        while cam_event.is_set() is False:
            time.sleep(2)

        # Get exposures
        try:
            img_utils.make_pretty_image(rotate_fn,
                                        title=f'Alignment Test - Rotate {direction}',
                                        link_path=os.path.expandvars('$PANDIR/images/latest.jpg'),
                                        primary=True)
        except AssertionError:
            print_warning(f"Can't make image for {rotate_fn}")
            pocs.say(f"Can't make image for {rotate_fn}")

    return rotate_fn


def print_info(msg):
    console.color_print(msg, 'lightgreen')


def print_warning(msg):
    console.color_print(msg, 'yellow')


def print_error(msg):
    console.color_print(msg, 'red')


if __name__ == '__main__':
    import os
    import sys

    if not os.getenv('POCS'):
        sys.exit("Please set the POCS environment variable.")

    invoked_script = os.path.basename(sys.argv[0])
    histfile = os.path.expanduser('~/.{}_history'.format(invoked_script))
    histfile_size = 1000
    if os.path.exists(histfile):
        readline.read_history_file(histfile)

    PocsShell().cmdloop()

    readline.set_history_length(histfile_size)
    readline.write_history_file(histfile)
