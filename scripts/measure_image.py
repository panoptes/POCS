import os

from IQMon import Image
from IQMon import Telescope


def measure_image(file,
                  clobber_logs=False,
                  graphics=False,
                  analyze_image=True,
                  record=True,
                  zero_point=False,
                  verbose=False,
                  ):

    # -------------------------------------------------------------------------
    # Create Telescope Object
    # -------------------------------------------------------------------------
    config_file = os.path.join(os.getenv('POCS'), 'conf_files', 'IQMon_config.yaml')
    tel = Telescope(config_file)

    # -------------------------------------------------------------------------
    # Perform Actual Image Analysis
    # -------------------------------------------------------------------------
    with Image(file, tel) as im:
        im.make_logger(verbose=verbose, clobber=clobber_logs)
        im.read_image()
        im.read_header()

        if analyze_image:
            if im.tel.ROI:
                im.crop()
            im.run_SExtractor()
            im.determine_FWHM()
            im.FWHM = im.FWHM_median  # Use median for Panoptes

            is_blank = (im.n_stars_SExtracted < 100)
            if is_blank:
                im.logger.warning('Only {} stars found.  Image may be blank.'.format(
                    im.n_stars_SExtracted))

            if not im.image_WCS and not is_blank:
                im.solve_astrometry()
            if im.astrometry_solved:
                im.determine_pointing_error()

            if graphics and im.FWHM:
                try:
                    im.make_PSF_plot()
                except Exception:
                    im.logger.warning('Failed to make PSF plot')

        if graphics:
            p1, p2 = (1.50, 0.50)
            small_JPEG = im.raw_file_basename + "_fullframe.jpg"
            im.make_JPEG(small_JPEG, binning=2,
                         p1=p1, p2=p2,
                         make_hist=False,
                         mark_pointing=True,
                         mark_detected_stars=True,
                         mark_catalog_stars=True,
                         mark_saturated=False,
                         quality=70,
                         )
            cropped_JPEG = im.raw_file_basename + "_crop.jpg"
            im.make_JPEG(cropped_JPEG,
                         p1=p1, p2=p2,
                         make_hist=False,
                         mark_pointing=True,
                         mark_detected_stars=True,
                         mark_catalog_stars=False,
                         mark_saturated=False,
                         crop=(int(im.nXPix / 2) - 512,
                               int(im.nYPix / 2) - 512,
                               int(im.nXPix / 2) + 512,
                               int(im.nYPix / 2) + 512),
                         quality=70,
                         )

        im.clean_up()
        im.calculate_process_time()

        if record:
            im.add_mongo_entry()

        im.logger.info('Done.')


def main():
    from argparse import ArgumentParser

    # create a parser object for understanding command-line arguments
    parser = ArgumentParser(description="Describe the script")
    # add flags
    parser.add_argument("-v", "--verbose",
                        action="store_true", dest="verbose",
                        default=False, help="Be verbose! (default = False)")

    parser.add_argument("--graphics",
                        action="store_true", dest="graphics",
                        default=False, help="Turn off generation of graphics")

    parser.add_argument("-z", "--zp",
                        action="store_true", dest="zero_point",
                        default=False, help="Calculate zero point")

    parser.add_argument("-r", "--record",
                        action="store_true", dest="record",
                        default=True, help="Store the record results")
    # add arguments
    parser.add_argument("filename",
                        type=str,
                        help="File Name of Input Image File")
    args = parser.parse_args()

    print(args)

    measure_image(args.filename,
                  graphics=args.graphics,
                  zero_point=args.zero_point,
                  record=args.record,
                  verbose=args.verbose)


if __name__ == '__main__':
    main()
