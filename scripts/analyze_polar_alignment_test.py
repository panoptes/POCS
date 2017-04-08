import os
import time

from argparse import ArgumentParser
from multiprocessing import Process
from multiprocessing import Queue
from subprocess import TimeoutExpired

from matplotlib import pyplot as plt

from skimage.feature import canny
from skimage.transform import hough_circle
from skimage.transform import hough_circle_peaks

from astropy.io import fits
from astropy.utils import console
from astropy.visualization import SqrtStretch
from astropy.visualization.mpl_normalize import ImageNormalize

import numpy as np

from pocs import POCS
from pocs.utils import current_time
from pocs.utils import images as img_utils

norm = ImageNormalize(stretch=SqrtStretch())

pocs = None
mount = None

verbose = False


def polar_rotation(exp_time=300, base_dir=None, **kwargs):
    assert base_dir is not None, print_warning("base_dir cannot be empty")

    mount.unpark()
    print_info('Performing polar rotation test, slewing to home')
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
            img_utils.make_pretty_image(fn, title='Alignment Test - Polaris', primary=True)
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


def analyze_polar_rotation(pole_fn, return_queue):
    d1 = fits.getdata(pole_fn)
    d1 = d1 / d1.max()
    d2 = d1.copy()

    pole_edges = canny(d2, sigma=2.0)

    pole_hough_radii = np.arange(1000, 4500, 100)
    pole_hough_res = hough_circle(pole_edges, pole_hough_radii)
    pole_accums, pole_cx, pole_cy, pole_radii = hough_circle_peaks(pole_hough_res, pole_hough_radii, total_num_peaks=3)

    return_queue.put(['polar', pole_cx[-1], pole_cy[-1]])


def analyze_ra_rotation(rotate_fn, return_queue):
    d0 = fits.getdata(rotate_fn)
    d0 = d0 / d0.max()

    # Get edges for rotation
    rotate_edges = canny(d0, sigma=2.0, low_threshold=.1, high_threshold=.6)

    rotate_hough_radii = np.arange(200, 800, 50)
    rotate_hough_res = hough_circle(rotate_edges, rotate_hough_radii)
    rotate_accums, rotate_cx, rotate_cy, rotate_radii = \
        hough_circle_peaks(rotate_hough_res, rotate_hough_radii, total_num_peaks=3)

    return_queue.put(['rotate', rotate_cx[-1], rotate_cy[-1]])


def plot_center(pole_fn, rotate_fn, pole_center, rotate_center, plot_fn=None):
    assert plot_fn is not None, print_warning("Output plot name required")

    data = fits.getdata(pole_fn) + fits.getdata(rotate_fn)

    pole_cx, pole_cy = pole_center
    rotate_cx, rotate_cy = rotate_center

    fig, ax = plt.subplots(ncols=1, nrows=1, figsize=(30, 25))

    ax.scatter(pole_cx, pole_cy, color='r', marker='x', lw=5)
    ax.scatter(rotate_cx, rotate_cy, color='r', marker='x', lw=5)

    ax.imshow(data, cmap='Greys_r', norm=norm)
    ax.arrow(rotate_cx, rotate_cy, pole_cx - rotate_cx, pole_cy - rotate_cy, fc='r', ec='r')
    fig.savefig(plot_fn)


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


if __name__ == '__main__':
    parser = ArgumentParser(description='Perform a polar alignment test')
    parser.add_argument('--exp-time', default=300, help='Exposure time for polar rotation')
    parser.add_argument('--base-dir', default='{}/images/drift_align'.format(os.getenv('PANDIR')),
                        help='Directory to store images')
    parser.add_argument('--verbose', action="store_true", default='False', help='Verbose')

    args = parser.parse_args()

    if args.verbose:
        verbose = True

    pocs = POCS(messaging=True)
    pocs.initialize()
    mount = pocs.observatory.mount

    start_time = current_time(flatten=True)

    return_queue = Queue()

    base_dir = '{}/{}/'.format(args.base_dir, start_time)
    plot_fn = '{}/{}_center_overlay.png'.format(base_dir, start_time)

    # Polar Rotation
    pole_fn = polar_rotation(exp_time=args.exp_time, base_dir=base_dir)
    pole_fn = pole_fn.replace('.cr2', '.fits')

    print_info("Starting analysis of polar image")
    polar_process = Process(target=analyze_polar_rotation, args=(pole_fn, return_queue,))
    polar_process.start()

    # Mount Rotation
    rotate_fn = mount_rotation(base_dir=base_dir)
    rotate_fn = pole_fn.replace('.cr2', '.fits')

    print_info("Parking mount")
    mount.park()

    print_info("Waiting for polar analysis to finish")
    polar_process.join()

    print_info("Starting analysis of rotation image")
    rotate_process = Process(target=analyze_ra_rotation, args=(rotate_fn, return_queue,))
    rotate_process.start()

    # Wait for analyzing processes to be done
    print_info("Waiting for rotate analysis to finish")
    rotate_process.join()

    pole_center = None
    rotate_center = None

    while return_queue.empty() is False:
        items = return_queue.get()
        print_info(items)
        if items[0] == 'polar':
            pole_center = (items[1], items[2])
        elif items[0] == 'rotate':
            rotate_center = (items[1], items[2])

    if pole_center is not None and rotate_center is not None:
        print_info("Plotting centers")
        plot_center(pole_fn, rotate_fn, pole_center, rotate_center, plot_fn)

    pocs.power_down()
