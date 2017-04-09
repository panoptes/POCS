import os
import time

from argparse import ArgumentParser
from subprocess import TimeoutExpired

from astropy.utils import console

from pocs import POCS
from pocs.utils import current_time
from pocs.utils import images as img_utils

from piaa.utils.polar_alignment import analyze_polar_rotation
from piaa.utils.polar_alignment import analyze_ra_rotation
from piaa.utils.polar_alignment import plot_center

pocs = None
mount = None

verbose = False


def polar_rotation(exp_time=30, base_dir=None, **kwargs):
    assert base_dir is not None, print_warning("base_dir cannot be empty")

    print_info('Performing polar rotation test')
    mount.slew_to_home()

    while not mount.is_home:
        time.sleep(2)

    analyze_fn = None

    print_info('At home position, taking {} sec exposure'.format(exp_time))
    procs = dict()
    for cam_name, cam in pocs.observatory.cameras.items():
        fn = '{}/pole_{}.cr2'.format(base_dir, cam_name.lower())
        proc = cam.take_exposure(seconds=exp_time, filename=fn)
        procs[fn] = proc
        if cam.is_primary:
            analyze_fn = fn

    for fn, proc in procs.items():
        try:
            outs, errs = proc.communicate(timeout=(exp_time + 15))
        except AttributeError:
            continue
        except KeyboardInterrupt:
            print_warning('Pole test interrupted')
            proc.kill()
            outs, errs = proc.communicate()
            break
        except TimeoutExpired:
            proc.kill()
            outs, errs = proc.communicate()
            break

        time.sleep(2)
        try:
            img_utils.make_pretty_image(fn, title='Alignment Test - Celestial Pole', primary=True)
            img_utils.cr2_to_fits(fn, remove_cr2=True)
        except AssertionError:
            print_warning("Can't make image for {}".format(fn))

    return analyze_fn


def mount_rotation(base_dir=None, **kwargs):
    print_info("Doing rotation test")
    mount.slew_to_home()
    exp_time = 25
    mount.move_direction(direction='west', seconds=11)

    rotate_fn = None

    # Start exposing on cameras
    for direction in ['east', 'west']:
        print_info("Rotating to {}".format(direction))
        procs = dict()
        for cam_name, cam in pocs.observatory.cameras.items():
            fn = '{}/rotation_{}_{}.cr2'.format(base_dir, direction, cam_name.lower())
            proc = cam.take_exposure(seconds=exp_time, filename=fn)
            procs[fn] = proc
            if cam.is_primary:
                rotate_fn = fn

        # Move mount
        mount.move_direction(direction=direction, seconds=21)

        # Get exposures
        for fn, proc in procs.items():
            try:
                outs, errs = proc.communicate(timeout=(exp_time + 15))
            except AttributeError:
                continue
            except KeyboardInterrupt:
                print_warning('Pole test interrupted')
                proc.kill()
                outs, errs = proc.communicate()
                break
            except TimeoutExpired:
                proc.kill()
                outs, errs = proc.communicate()
                break

            time.sleep(2)
            try:
                img_utils.make_pretty_image(
                    fn, title='Alignment Test - Rotate {}'.format(direction), primary=True)
                img_utils.cr2_to_fits(fn, remove_cr2=True)
            except AssertionError:
                print_warning("Can't make image for {}".format(fn))

    return rotate_fn


def print_info(msg):
    if verbose:
        console.color_print(msg, 'lightgreen')
        try:
            pocs.say(msg)
        except Exception:
            pass


def print_warning(msg):
    if verbose:
        console.color_print(msg, 'yellow')
        try:
            pocs.say(msg)
        except Exception:
            pass


def print_error(msg):
    if verbose:
        console.color_print(msg, 'red')
        try:
            pocs.say(msg)
        except Exception:
            pass


def perform_tests(base_dir):
    start_time = current_time(flatten=True)

    base_dir = '{}/{}/'.format(base_dir, start_time)
    plot_fn = '{}/{}_center_overlay.png'.format(base_dir, start_time)

    print_info("Moving to home position")
    mount.slew_to_home()

    # Polar Rotation
    pole_fn = polar_rotation(base_dir=base_dir)
    pole_fn = pole_fn.replace('.cr2', '.fits')

    # Mount Rotation
    rotate_fn = mount_rotation(base_dir=base_dir)
    rotate_fn = pole_fn.replace('.cr2', '.fits')

    print_info("Moving back to home")
    mount.slew_to_home()

    print_info("Solving celestial pole image")
    pole_center = analyze_polar_rotation(pole_fn)

    print_info("Starting analysis of rotation image")
    rotate_center = analyze_ra_rotation(rotate_fn)

    if pole_center is not None and rotate_center is not None:
        print_info("Plotting centers")
        fig = plot_center(pole_fn, rotate_fn, pole_center, rotate_center, plot_fn)
        print_info("Plot image: {}".format(plot_fn))
        fig.savefig(plot_fn)


if __name__ == '__main__':
    parser = ArgumentParser(description='Perform a polar alignment test')
    parser.add_argument('--base-dir', default='{}/images/drift_align'.format(os.getenv('PANDIR')),
                        help='Directory to store images')
    parser.add_argument('--verbose', action="store_true", default='False', help='Verbose')

    args = parser.parse_args()

    if args.verbose:
        verbose = True

    pocs = POCS(messaging=True)
    pocs.initialize()
    mount = pocs.observatory.mount

    mount.unpark()

    while True:
        perform_tests(args.base_dir)

        pocs.sleep()

        if mount.is_parked:
            break

    if pocs.connected:
        pocs.power_down()
