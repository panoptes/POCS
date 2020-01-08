#!/usr/bin/env python3
import os
import readline
import time
import zmq

from cmd import Cmd
from pprint import pprint

from astropy import units as u
from astropy.coordinates import AltAz
from astropy.coordinates import ICRS
from astropy.utils import console

from pocs import hardware
from pocs.core import POCS
from pocs.observatory import Observatory
from pocs.scheduler.field import Field
from pocs.scheduler.observation import Observation
from panoptes.utils import current_time
from panoptes.utils import string_to_params
from panoptes.utils import error
from panoptes.utils import images as img_utils
from panoptes.utils.images import fits as fits_utils
from panoptes.utils.images import polar_alignment as polar_alignment_utils
from panoptes.utils.database import PanDB
from panoptes.utils.messaging import PanMessaging
from panoptes.utils.config import client
from panoptes.utils.data import Downloader

from pocs.mount import create_mount_from_config
from pocs.camera import create_cameras_from_config
from pocs.scheduler import create_scheduler_from_config


# Download IERS data and astrometry index files
Downloader().download_all_files()


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

    def do_drift_align(self, *arg):
        """Enter the drift alignment shell."""
        self.do_reset_pocs()
        print_info('*' * 80)
        i = DriftShell()
        i.cmdloop()

    def do_start_messaging(self, *arg):
        """Starts the messaging system for the POCS ecosystem.

        This starts both a command forwarder and a message forwarder as separate
        processes.

        The command forwarder has the pocs_shell and PAWS as PUBlishers and POCS
        itself as a SUBscriber to those commands

        The message forwarder has POCS as a PUBlisher and the pocs_shell and PAWS
        as SUBscribers to those messages

        Arguments:
            *arg {str} -- Unused
        """
        print_info("Starting messaging")

        # Send commands to POCS via this publisher
        try:
            self.cmd_publisher = PanMessaging.create_publisher(
                self.cmd_pub_port)
            print_info("Command publisher started on port {}".format(
                self.cmd_pub_port))
        except Exception as e:
            print_warning("Can't start command publisher: {}".format(e))

        try:
            self.cmd_subscriber = PanMessaging.create_subscriber(
                self.cmd_sub_port)
            print_info("Command subscriber started on port {}".format(
                self.cmd_sub_port))
        except Exception as e:
            print_warning("Can't start command subscriber: {}".format(e))

        # Receive messages from POCS via this subscriber
        try:
            self.msg_subscriber = PanMessaging.create_subscriber(
                self.msg_sub_port)
            print_info("Message subscriber started on port {}".format(
                self.msg_sub_port))
        except Exception as e:
            print_warning("Can't start message subscriber: {}".format(e))

        # Send messages to PAWS
        try:
            self.msg_publisher = PanMessaging.create_publisher(
                self.msg_pub_port)
            print_info("Message publisher started on port {}".format(
                self.msg_pub_port))
        except Exception as e:
            print_warning("Can't start message publisher: {}".format(e))

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
            self.pocs = POCS(observatory, messaging=True)
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
        if self.pocs.observatory.mount.is_parked is False:
            print_warning("ATTENTION: The mount is not in the parked position and reset_pocs will not move the mount to park position!")
            response = input("The unit could be damaged if it is not parked before sunrise. Execute reset_pocs anyway?[y/n]")
            if response.lower().startswith('y'):
                self.pocs = None
                print_info("POCS instance discarded. Remember to park the mount later.")
            elif response.lower().startswith('n'):
                print("Keeping POCS instance.")
            else:
                print("A 'yes' or 'no' response is required")
                self.do_reset_pocs()

    def do_run_pocs(self, *arg):
        """Make POCS `run` the state machine.

        Continues until the user presses Ctrl-C or the state machine
        exits, such as due to an error."""
        if self.pocs is not None:
            if self.msg_subscriber is None:
                self.do_start_messaging()

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
        if self.msg_subscriber is None:
            self.do_start_messaging()
        status = self.pocs.status()
        print()
        pprint(status)
        print()

    def do_pocs_command(self, cmd):
        """Send a command to POCS instance.

        Arguments:
            cmd {str} -- Command to be sent
        """
        try:
            self.cmd_publisher.send_message('POCS-CMD', cmd)
        except AttributeError:
            print_info('Messaging not started')

    def do_pocs_message(self, cmd):
        """Send a message to PAWS and other listeners.

        Arguments:
            cmd {str} -- Command to be sent
        """
        try:
            self.msg_publisher.send_message('POCS-SHELL', cmd)
        except AttributeError:
            print_info('Messaging not started')

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

        print_info("Solving celestial pole image")
        self.pocs.say("Solving celestial pole image")
        try:
            pole_center = polar_alignment_utils.analyze_polar_rotation(pole_fn)
        except Exception as e:
            print_warning(f'Unable to solve pole image: {e!r}')
            print_warning("Will proceeed with rotation image but analysis not possible")
            pole_center = None
        else:
            pole_center = (float(pole_center[0]), float(pole_center[1]))

        print_info("Starting analysis of rotation image")
        self.pocs.say("Starting analysis of rotation image")
        try:
            rotate_center = polar_alignment_utils.analyze_ra_rotation(rotate_fn)
        except Exception as e:
            print_warning(f'nable to process rotation image: {e}')
            rotate_center = None

        if pole_center is not None and rotate_center is not None:
            print_info("Plotting centers")
            self.pocs.say("Plotting centers")

            print_info("Pole: {} {}".format(pole_center, pole_fn))
            self.pocs.say("Pole  : {:0.2f} x {:0.2f}".format(
                pole_center[0], pole_center[1]))

            print_info("Rotate: {} {}".format(rotate_center, rotate_fn))
            self.pocs.say("Rotate: {:0.2f} x {:0.2f}".format(
                rotate_center[0], rotate_center[1]))

            d_x = pole_center[0] - rotate_center[0]
            d_y = pole_center[1] - rotate_center[1]

            self.pocs.say("d_x: {:0.2f}".format(d_x))
            self.pocs.say("d_y: {:0.2f}".format(d_y))

            fig = polar_alignment_utils.plot_center(
                pole_fn, rotate_fn, pole_center, rotate_center)

            print_info("Plot image: {}".format(plot_fn))
            fig.tight_layout()
            fig.savefig(plot_fn)

            try:
                os.unlink('/var/panoptes/images/latest.jpg')
            except Exception:
                pass
            try:
                os.symlink(plot_fn, '/var/panoptes/images/latest.jpg')
            except Exception:
                print_warning("Can't link latest image")

            with open('/var/panoptes/images/drift_align/center.txt'.format(base_dir), 'a') as f:
                f.write('{}.{},{},{},{},{},{}\n'.format(start_time, pole_center[0], pole_center[
                        1], rotate_center[0], rotate_center[1], d_x, d_y))

        print_info("Done with polar alignment test")
        self.pocs.say("Done with polar alignment test")

    def do_web_listen(self, *arg):
        """Goes into a loop listening for commands from PAWS."""

        if not hasattr(self, 'cmd_subscriber'):
            self.do_start_messaging()

        self.pocs.say("Now listening for commands from PAWS")

        poller = zmq.Poller()
        poller.register(self.cmd_subscriber.socket, zmq.POLLIN)

        command_lookup = {
            'polar_alignment': self.do_polar_alignment_test,
            'park': self.do_park,
            'unpark': self.do_unpark,
            'home': self.do_go_home,
        }

        try:
            while True:
                # Poll for messages
                sockets = dict(poller.poll(500))  # 500 ms timeout

                if self.cmd_subscriber.socket in sockets and \
                        sockets[self.cmd_subscriber.socket] == zmq.POLLIN:

                    topic, msg_obj = self.cmd_subscriber.receive_message(
                        flags=zmq.NOBLOCK)
                    print_info("{} {}".format(topic, msg_obj))

                    # Put the message in a queue to be processed
                    if topic == 'PAWS-CMD':
                        try:
                            print_info("Command received: {}".format(
                                msg_obj['message']))
                            cmd = command_lookup[msg_obj['message']]
                            cmd()
                        except KeyError:
                            pass
                        except Exception as e:
                            print_warning(
                                "Can't perform command: {}".format(e))

                time.sleep(1)
        except KeyboardInterrupt:
            self.pocs.say("No longer listening to PAWS")
            pass


##########################################################################
# Private Methods
##########################################################################

##########################################################################
# Utility Methods
##########################################################################

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
                                    link_latest=True,
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

        print_info("Rotating to {}".format(direction))
        pocs.say("Rotating to {}".format(direction))

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
                                        link_latest=True,
                                        primary=True)
        except AssertionError:
            print_warning(f"Can't make image for {rotate_fn}")
            pocs.say(f"Can't make image for {rotate_fn}")

    return rotate_fn


class DriftShell(Cmd):
    intro = 'Drift alignment shell! Type ? for help or `exit` to leave drift alignment.'
    prompt = 'POCS:DriftAlign > '

    pocs = None
    base_dir = '{}/images/drift_align'.format(os.getenv('PANDIR'))

    num_pics = 40
    exptime = 30

    # Coordinates for different tests
    coords = {
        'alt_east': (30, 102),
        'alt_west': (20, 262.5),
        'az_east': (70.47, 170),
        'az_west': (70.47, 180),
    }

    @property
    def ready(self):
        if self.pocs is None:
            print_warning('POCS has not been setup. Please run `setup_pocs`')
            return False

        if self.pocs.observatory.mount.is_parked:
            print_warning('Mount is parked. To unpark run `unpark`')
            return False

        return self.pocs.is_safe()

    def do_setup_pocs(self, *arg):
        """Setup and initialize a POCS instance."""
        args, kwargs = string_to_params(*arg)
        simulator = kwargs.get('simulator', [])
        print_info("Simulator: {}".format(simulator))

        try:
            self.pocs = POCS(simulator=simulator)
            self.pocs.initialize()
        except error.PanError:
            pass

    def do_drift_test(self, *arg):
        if self.ready is False:
            return

        args, kwargs = string_to_params(*arg)

        try:
            direction = kwargs['direction']
            num_pics = int(kwargs['num_pics'])
            exptime = float(kwargs['exptime'])
        except Exception:
            print_warning(
                'Drift test requires three arguments: direction, num_pics, exptime')
            return

        start_time = kwargs.get('start_time', current_time(flatten=True))

        print_info('{} drift test with {}x {}sec exposures'.format(
            direction.capitalize(), num_pics, exptime))

        if direction:
            try:
                alt, az = self.coords.get(direction)
            except KeyError:
                print_error('Invalid direction given')
            else:
                location = self.pocs.observatory.observer.location
                obs = get_observation(
                    alt=alt,
                    az=az,
                    loc=location,
                    num_exp=num_pics,
                    exptime=exptime,
                    name=direction
                )

                self.perform_test(obs, start_time=start_time)
                print_info('Test complete, slewing to home')
                self.do_go_home()
        else:
            print_warning('Must pass direction to test: alt_east, alt_west, az_east, az_west')

    def do_full_drift_test(self, *arg):
        if not self.ready:
            return

        args, kwargs = string_to_params(*arg)

        num_pics = int(kwargs.get('num_pics', self.num_pics))
        exptime = float(kwargs.get('exptime', self.exptime))

        print_info('Full drift test. Press Ctrl-c to interrupt')

        start_time = current_time(flatten=True)

        for direction in ['alt_east', 'az_east', 'alt_west', 'az_west']:
            if not self.ready:
                break

            print_info('Performing drift test: {}'.format(direction))
            try:
                self.do_drift_test('direction={} num_pics={} exptime={} start_time={}'.format(
                    direction, num_pics, exptime, start_time))
            except KeyboardInterrupt:
                print_warning('Drift test interrupted')
                break

        print_info('Slewing to home')
        self.do_go_home()

    def do_unpark(self, *arg):
        try:
            self.pocs.observatory.mount.unpark()
        except Exception as e:
            print_warning('Problem unparking: {}'.format(e))

    def do_go_home(self, *arg):
        """Move the mount to home."""
        if self.ready is False:
            if self.pocs.is_weather_safe() is False:
                self.do_power_down()

            return

        try:
            self.pocs.observatory.mount.slew_to_home(blocking=True)
        except Exception as e:
            print_warning('Problem slewing to home: {}'.format(e))

    def do_power_down(self, *arg):
        print_info("Shutting down POCS instance, please wait")
        self.pocs.power_down()

        while self.pocs.observatory.mount.is_parked is False:
            print_info('.')
            time.sleep(5)

        self.pocs = None

    def do_exit(self, *arg):
        if self.pocs is not None:
            self.do_power_down()

        print_info('Leaving drift alignment')
        return True

    def emptyline(self):
        if self.ready:
            print_info(self.pocs.status())

    def perform_test(self, observation, start_time=None):
        if start_time is None:
            start_time = current_time(flatten=True)

        mount = self.pocs.observatory.mount

        mount.set_target_coordinates(observation.field.coord)
        # print_info("Slewing to {}".format(coord))
        mount.slew_to_target()

        while mount.is_slewing:
            time.sleep(3)

        print_info('At destination, taking pics')

        for i in range(observation.min_nexp):

            if not self.ready:
                break

            headers = self.pocs.observatory.get_standard_headers(
                observation=observation)

            # All camera images share a similar start time
            headers['start_time'] = start_time

            print_info('\t{} of {}'.format(i, observation.min_nexp))

            events = []
            files = []
            for name, cam in self.pocs.observatory.cameras.items():
                fn = '{}/{}_{}_{}_{:02d}.cr2'.format(
                    self.base_dir, start_time, observation.field.field_name, name, i)
                cam_event = cam.take_observation(
                    observation, headers=headers, filename=fn)
                events.append(cam_event)
                files.append(fn.replace('.cr2', '.fits'))

            for e in events:
                while not e.is_set():
                    time.sleep(5)

            # while files:
            #     file = files.pop(0)
            #     process_img(file, start_time)


def process_img(fn, start_time, remove_after=True):
    # Unpack if already packed
    if fn.endswith('.fz'):
        fn = fits_utils.fpack(fn, unpack=True)

    if os.path.exists('{}.fz'.format(fn)):
        fn = fits_utils.fpack(fn.replace('.fits', '.fits.fz'), unpack=True)

    # Solve the field
    try:
        fits_utils.get_solve_field(fn)

        # Get header info
        header = fits_utils.getheader(fn)

        try:
            del header['COMMENT']
            del header['HISTORY']
        except Exception:
            pass

        db = PanDB()

        # Add to DB
        db.drift_align.insert_one({
            'data': header,
            'type': 'drift_align',
            'date': current_time(datetime=True),
            'start_time': start_time,
        })

        # Remove file
        if remove_after:
            try:
                os.remove(fn)
            except Exception as e:
                print_warning('Problem removing file: {}'.format(e))
    except Exception as e:
        print_warning('Problem with adding to mongo: {}'.format(e))


def get_observation(alt=None, az=None, loc=None, num_exp=25, exptime=30 * u.second, name=None):
    assert alt is not None
    assert az is not None
    assert loc is not None

    coord = AltAz(az=az * u.deg, alt=alt * u.deg,
                  obstime=current_time(), location=loc).transform_to(ICRS)

    field = Field(name, coord)

    if not isinstance(exptime, u.Quantity):
        exptime *= u.second

    obs = Observation(field, exptime=exptime,
                      min_nexp=num_exp, exp_set_size=1)

    return obs


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
