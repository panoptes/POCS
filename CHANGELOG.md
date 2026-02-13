# Changelog

# Unreleased

## Added

- Beginner documentation: conceptual overview, architecture guide, glossary, and CLI examples
- Beginner Resources section in main README (top-level)
- Tags support for observations: observations can now be tagged with arbitrary string labels for metadata searching and filtering. Tags are specified in field YAML files under the `observation` key and are included in observation status, serialization, and FITS headers.

## Changed

- `examples/beginner_simulation.py`: use local config, display devices, fix simulators parameter
- Documentation: clickable links, CLI-first approach, plain language

# 0.7.8

## Generic

- **Breaking changes** #1074
    - Python 3.8

    - Default service install does not include `focuser` dependencies.

    - Default service is running a public jupyter lab.

    - Default Docker command is a `ipython` console with the
      simulators loaded.

    - Docker image only contains limited set of files.

    - Directories inside the service image have been simplified for
      easier mapping onto desired targets on the host. The main
      top-level directory (i.e. `$PANDIR`) is now `/POCS` with other
      folders nested underneath.

    - Removing `peas` scripts.

    - New Power Board and arduino sketch for controlling power and
      reading currents. #1038

    - Serial Mount: clarify the `driver`, `brand`, and `model`
      options. #1085

        - `brand` and `model` determine the directory/file to use for
          looking up the mount commands. `brand` should be a subdir of
          the `directories.mounts` config entry (which is set to
          `resources/mounts` by default) and `model` should be the
          name of the yaml file (without the extension).
        - `driver` should be the fully qualified namespace to the
          python file. Fixes #1081

      Example:

          # This will look for `resources/mounts/ioptron/cem40.yaml`
          # for the command file and will load the `driver` via `load_module`
          mount:
            brand: ioptron
            model: cem40
            driver: panoptes.pocs.mount.ioptron.cem40

## Added

- Simple example script for creating a `POCS` instance with all
  simulators. #1074
- Using `threading.excepthook` to log errors in camera exposure
  threads. #1074
- Adding `cem40.py` mount driver and commands file. #1085

## Changed

- Updated install script (includes ZSH again). #1074
- Pointing state is skipped if `num_pointing_images==0`. #1074
- The default `radius` for solving images is 15°.
- Don't parse mount commands with new serializers, which was turning
  the `0040` mount version into a date for some reason. #1085
- Organized the mount command files better. #1085
- Don't update config server when creating simulator. Fixes #1080

## Docker

- `PANUSER` owns `conda`. #1068
- Dockerfile cleanup for better builds. #1068
- Docker image does not contain `focuser` extras by default. #1068
- Images use `gcr.io/panoptes-exp/panoptes-utils` as base. #1074
- Docker files are all contained within `docker` folder. #1074
- Docker image has tycho2 10-19 index files for plate-solving. #1074
- Docker services (`config-server` and `pocs-control`) are started in
  `global` mode so tehre can be only one. # 1074
- Config changed to run with simulators out of the box. #1074

## Removing

- Old scripts and config files. #1074

## Testing

- Fix the log level in conftest. #1068
- Move all tests into `tests` subdir from project root. #1068
- Cleanup of testing setup, especially for GHA. #1068
- Simplify testing service by removing `tests/env` file. #1074

# 0.7.7 - 2021-01-19

## Added

- Conda environment file. (@wtgee #1066)
- Add the [gsutil]{.title-ref} to [google]{.title-ref} install
  options. Required for uploading data. (@wtgee #1036, #1037)
- Ability to specify autofocus plots in config file. (@wtgee #1029)
- A "developer" version of the `panoptes-pocs` docker image is
  cloudbuilt automatically on merge with `develop`. (@wtgee #1010)
- Better error checking in cameras, including ability to store error.
  (@AnthonyHorton #1007)
- Added `error.InvalidConfig` exception. (@wtgee #1007)
- Config options to control camera processing options and allow for
  [defaults]{.title-ref} in the config that applies to all cameras:
  (@wtgee #1007)
    - `cameras.defaults.compress_fits` if FITS files should be
      fpacked. Default True.
    - `cameras.defaults.record_observations` if observation metadata
      should be recorded. Default True.
    - `cameras.defaults.make_pretty_images` to make jpgs from images.
      Default True.

## Breaking

- The `model` parameter for the camera and subcomponents needs a fully
  resolved namespace for either the module or class. (@wtgee #1007)
- The `take_exposure` method returns an event to indicate that
  exposure is in progress, **not** to indicate when exposure has
  completed. The event is stored in the camera object and accessible
  via `camera.is_exposing`. (@wtgee #1007)
- Removed camera temperature stability checking for now. (@wtgee
  #1007)
- Moved the `AbstractGphotoCamera` class into it's own namespace and
  file. (@wtgee #1007)
- Python moved back to 3.7. (#1021)

## Bug fixes

- Fix incorrect import of autofocus plots. (@wtgee #1034)
- DSLR simulator cameras properly override the cooling defaults.
  (@wtgee #1001)
- Stability checks for cooled cameras so they are only marked `ready`
  when cooled condition has stabilized. (@danjampro #990)
- Properly closed the autofocus matplotlib figures. (@wtgee #1029)
- Prevent thumbnails from being larger than image. (@wtgee #1029)

## Changed

- Clean up dependencies and offer extras install options. (@wtgee
  #1066)
    - Split some hardware options, such as `focuser`, which has extra
      dependencies.
- Consolidate config files into `conf_files` dir. This includes
  targets and state machine files. (@wtgee #1066)
- Change `thumbnail_size` to `cutout_size` consistently. (@wtgee
  #1040.)
- Camera observation updates:
    - TheSkyX utilities added (from `panoptes-utils`). (@wtgee #1066)
    - headers param fixed so truly optional. The POINTING keyword is
      checked in the metadata, not original headers. Closes #1002.
      (@wtgee #1009)
    - Passing approved headers will actually write them to file.
      (@wtgee #1009)
    - `blocking=False` param added. If True, will wait on
      observation_event. (@wtgee #1009)
    - Renamed metadata variables to be consistent. (@wtgee #1009)
    - `_process_fits` is responsible for writing the headers rather
      than calling out to panoptes-utils. Allows for easier overrides.
      (@wtgee #1009)
    - dslr simulator readout time improved. (@wtgee #1009)
    - `process_exposure` doesn't require the exposure_event to be
      passed because that is the cameras is_exposing property. (@wtgee
      #1009)
    - The autofocus plotting has been moved to an external file.
      (@wtgee #1029)
- Changelog cleanup. (@wtgee #1008)
- `panoptes-utils` updates:
    - Updated `panoptes-utils` to `v0.2.30`. (@wtgee #1066)
    - Updated `panoptes-utils` to `v0.2.29`. (@wtgee #1021)
    - Updated `panoptes-utils` to `v0.2.28`. (@wtgee #1007)
    - Updated `panoptes-utils` to `v0.2.27` to support the envvars for
      starting config server. (@wtgee #1001)
- Move the `wait-for-it.sh` script into `scripts`. (@wtgee #1001)
- Camera:
    - Changed how subcomponents for camera are created. (@wtgee #1007)
    - Camera and subcomponent stringification changed for clarity.
      (@wtgee #1007)
    - Can reassign SDK camera if same UID is presented with flag to
      `create_cameras_from_config`. (@wtgee #1007)
    - Add support for taking "dark" frames for cameras with
      mechanical shutters or opaque filters in the filterwheel.
      (@AnthonyHorton #989)
    - `_poll_exposure` was needlessly being called in a
      `threading.Timer` rather than a simple `threading.Event`.
      (@wtgee @1007)
    - Slight improvements to the timeout and readout for exposures
      with the simulators. (@wtgee #1007)
- Docker:
    - Default `$PANUSER` is now `pocs-user` instead of `panoptes`.
      (@wtgee #1066)
    - Docker images default to `latest` instead of `develop`. (@wtgee
      #1066)
    - Removed `developer` docker image. (@wtgee #1066)
    - Updated to match `panoptes-utils` Docker updates: removal of
      `source-extractor` and more. (@wtgee #1008)
    - `gphoto2` comes from apt. (@wtgee #1007)
    - Local setup script doesn't build `panoptes-utils` but assumes
      done otherwise or uses `gcr.io`. (@wtgee #1007)
- Testing:
    - Added `tests/env` file for setting up testing. (@wtgee #1066)
    - Config server is started as part of pytest again (reverting
      below). (@wtgee #1066)
    - Testing is run from a locally built Docker image for both local
      and CI testing. (@wtgee #1001)
    - Config file for testing is moved to
      `$PANDIR/tests/testing.yaml`. (@wtgee #1001)
    - Config server for testing is started external to `pytest`, which
      is currently lowering coverage. (@wtgee #1001)
    - Coverage reports are generated inside the Docker container.
      (@wtgee #1001)
    - Default log level set to TRACE. (@wtgee #1007)
    - Less hard-coding of fixtures and answers, more config server.
      (@wtgee #1007)
    - Renamed the cameras in testing fixtures. (@wtgee #1007)
    - Cooled cameras have temperature stability check in conftest.
      (@wtgee #1007)

## Removed

- Removed testing and local setup scripts. (@wtgee #1066)
- Removed manuals from `resources` directory. (@wtgee #1066)
- Removed all arduino files, to be replaced by Firmata. See
  instructions on gitbook docs. (@wtgee #1035)
- Remove `create_camera_simulator` helper function. (@wtgee #1007)

# 0.7.6 - 2020-08-21

## Changed

- Dependency updates:

    - `panoptes-utils` to `0.2.26`. (#995)
    - `panoptes-utils` to `0.2.21`. (#979)
    - `panoptes-utils` to `0.2.20`. (#974)

- Install script. (#974)

    - Env var file is sourced for zshrc and bashrc.
    - Fix the clone of the repos in install script. (#978)
    - Adding a date version to script. (#979)
    - `docker-compose` version bumped to `1.26.2`. (#979)
    - Better testing for ssh access. (#984)
    - Using [linuxserver.io docker-compose](https://hub.docker.com/r/linuxserver/docker-compose)
      so we also have `arm` version without work. (#986)
    - Fixing conditional so script can proceed without restart. (#986)
    - Generalizing install script in sections. (#986)

- Development Environment (#974)

    - Many cleanups to environment and launch. See docs.
    - Config server started along with development environment.
    - Docker images and python packages are now automated via GitHub
      Actions and Google Cloud Build. (#995)

- Docker image updates (#972)

    - Updated `install-pocs.sh` script.
    - `latest` installs the `panoptes-pocs` module from pip
    - `develop` installs via `pip install -e[google.testing]` and is
      used for running the CI tests.
    - `developer-env` installs locally but with all options, i.e.
      `pip install -e[google,testing,plotting,developer]`. Also builds
      `jupyterlab` and other developer tools. Starts a `jupyterlab`
      instance by default.
    - Use new `arduino-cli` installer.
    - Add `bin/panoptes-develop` and `bin/wait-for-it.sh` to installed
      scripts.
    - Add `docker/setup-local-environment.sh`, a convenience script
      for building local images.
    - Python moved to 3.8. (#974)
    - Docker images are now built with buildx to get an arm version
      running. (#978)
    - Removing readline and pendulum dependencies. (#978)
    - Fully automated build and release of packages with GitHub
      Actions. (#995)

- Testing (#974)

    - Removing all the dynamic config server info, making things a lot
      simpler.
    - `docker-compose` files for running tests.
    - Misc documentation updates.
    - Code coverage no longer ignores test.
    - Testing is run via `panoptes-develop test`.
    - Log files are rotated during each run.

- POCS (#974)

    - POCS instance cannot `initialize` unless it's
      `observatory.can_observe`.
    - Set `simulator` config item at start of `POCS` init method if
      `simulators` (note plural) is passed.
    - Simplification of the `run` method and the various predicates
      used to control it. Now just use the computed `keep_running`.
    - Adding some action flags to the `pocs.yaml` file.
    - Remove `POCS.check_environment` class method.
    - Add a `console_log_level` and `stderr_log_level`. The former is
      written to the log file in `$PANLOG` and is meant to be tailed
      in the console. The `stderr_log_level` is what would be
      displayed, e.g. in a jupyter notebook. (#977)
    - Mount simulator better name and stringify. (#977)
    - Global db object for `PanBase` (#977)
    - Allow for custom folder for metadata. (#979)
        - Default changed to `metadata`.

- Camera simulator cleanup. (#974)

- Scheduler (#974)

  > - The `fields_file` is read when scheduler is created.

# 0.7.4 - 2020-05-31

Note that we skipped `0.7.2` and `0.7.3`.

## Bug fixes

- Package name is `panoptes-pocs` for namespace consistency. (#971)
- README changed to rst. (#971)

# 0.7.1 - 2020-05-31

If you thought 9 months between releases was a long time, how about 18
months! :) This version has a lot of breaking changes and is not
backwards compatible with previous versions. The release is a (big)
stepping stone on the way to `0.8.0` and (eventually!) a `1.0.0`.

The entire repo has been redesigned to support docker images. This comes
with a number of changes, including the refactoring of many items into
the [panoptes-utils](https://github.com/panoptes/panoptes-utils.git)
repo.

There are a lot of changes included in this release, highlights below:

    This changelog is likely missing some things. The release was large. Too large. 
    If you think something might be working different that just might be true. Check the forums.

## Added

- Storing an explicit `safety` collection in the database.
- Configuration file specific for testing rather than relying on
  `pocs.yaml`.
- Convenience scripts for running tests inside docker container:

> `scripts/testing/test-software.sh`

- GitHub Actions for testing and coverage upload.

## Changed

- Docker as default. (#951).
- Weather items have moved to [aag-weather](https://github.com/panoptes/aag-weather).
    - Two docker containers run from the `aag-weather` image and have
      a `docker/docker-compose-aag.yaml` file to start.
- Config items related to the configuration system have been moved to
  the [Config Server](https://panoptes-utils.readthedocs.io/en/latest/#config-server)
  in `panoptes-utils` repo.
    - The main interface for POCS related items is through
      `self.get_config`, which can take a key and a default, e.g.
      `self.get_config('mount.horizon', default='30 deg')`.
    - Test writing is affected and is currently more difficult than
      would be ideal. An updated test writing document will be
      following this release.
- Logging has changed to [loguru](https://github.com/Delgan/loguru)
  and has been greatly simplified:
    - `get_root_logger` has been replaced by `get_logger`.
- The `per-run` logs have been removed and have been replaced by two
  logs files:

    - `$PANDIR/logs/panoptes.log`: Log file meant for watching on the command line (via `tail`) or for otherwise
      human-readable logs. Rotated daily at 11:30 am. Only the previous days' log is retained.
    - `$PANDIR/logs/panoptes_YYYYMMDD.log`: Log file meant for archive or information gathering. Stored in JSON format
      for ingestion into log analysis service. Rotated daily at 11:30 and stored in a compressed file for 7 days. Future
      updates will add option to upload to google servers.

- `loguru` provides two new log levels
    - `trace`: one level below `debug`.
    - `success`: one level above `info`.

**Breaking**

- Mount: unparking has been moved from the `ready` to the `slewing` state. This fixes a problem where after
  waiting 10 minutes for observation check, the mount would move from park to home to park without checking weather
  safety.
- Documentation updates.
- Lots of conversions to `f-strings`.
- Renamed codecov configuration file to be compliant.
- Switch to pyscaffold for package maintenance.
- "Waiting" method changes:
    - `sleep` has been renamed to `wait`.
- All `status()` methods have been converted to properties that return a useful dict.
- Making proper abstractmethods.
- Documentation updates where found.
- Many log and f-string fixes.
- `pocs.config_port` property available publicly.
- horizon check for state happens directly in `run`.

## Removed

- Cleanup of any stale or unused code.
- All `mongo` related code.
- Consolidate configration files: `.pycodestyle.cfg`, `.coveragerc` into `setup.cfg`.
- Weather related items. These have been moved to [aag-weather](https://github.com/panoptes/aag-weather).
- All notebook tutorials in favor of [panoptes-tutorials](https://github.com/panoptes/panoptes-tutorials)
- Remove all old install and startup scripts.

# 0.6.2 - 2018-09-27

One week between releases is a lot better than 9 months! ;) Some small
but important changes mark this release including faster testing times
on local machines. Also a quick release to remove some of the CloudSQL
features (but see the shiny new Cloud Functions over in the
[panoptes-network](https://github.com/panoptes/panoptes-network) repo!).

## Fixed

- Use unit_id for sequence and image ids. Important for processing consistency #613.
- State Machine

## Changed

- Remove camera creation from Observatory #612.
- Smarter event waiting #625.
- More cleanup, especially path names and pretty images #610, #613, #614, #620.
- Caching some of the build dirs #611.
- Only use Mongo DB type during local testing - Local testing with 1/3rd the wait! #616.
- Google Cloud #599
- Storage improvements #601.

## Added

- CountdownTimer utility #625.

## Removed

- Google Cloud #599
- Reverted some of the CloudSQL connectivity #652
- Remove spline smoothing focus #621.

# 0.6.1 - 2018-09-20

- Lots of changes in this release. In particular we've pushed through a lot of changes
- (especially with the help of @jamessynge) to make the development process a lot
- smoother. This has in turn contribute to the quality of the codebase.

Too long between releases but even more exciting improvements to come! Next up is tackling the events notification
system, which will let us start having some vastly improved UI features.

Below is a list of some of the changes.

Thanks to first-time contributors: @jermainegug @jeremylan as well as contributions from many folks over at
<https://github.com/AstroHuntsman/huntsman-pocs>.

## Fixed

- Fix for DATE-OBS fits header #589.
- Better property settings for DSLRs #589.
- Pretty image improvements #589.
- Autofocus improvements for SBIG/Focuser #535.
- Primary camera updates #614, 620.
- Many bug fixes #457, #589.
- Many fixes #509, #518.

## Changed

- POCS Shell: Hitting `Ctrl-c` will complete movement through states #590.
- Pointing updates, including `auto_correct` #580.
- Tracking mode updates (**fixes for Northern Hemisphere only!**) #549.
- Serial interaction improvements #388, #403.
- Shutdown improvements #407, #421.
- Changes from May Huntsman commissioning run #535
- Better and consistent topic terminology #593, #605.
- Anticipation of coming events.
- Default to rereading the fields file for targets #488.
- Timelapse updates #523, #591.

## Added

- Basic scripts for bias and dark frames.
- Add support for Optec FocusLynx based focus controllers #512.
- Pretty images from FITS files. Thanks @jermainegug! #538.
- pyflakes testing support for bug squashing! #596.
- pycodestyle for better code! #594.
- Threads instead of process #468.
- Fix coverage & Travis config for concurrency #566.
- Google Cloud #599
- Added instructions for authentication #600.
- Add a `pan_id` to units for GCE interaction#595.
- Adding Google CloudDB interaction #602.
- Much work on arduinos and sensors #422.
- Startup scripts for easier setup #475.
- Install scripts for Ubuntu 18.04 #585.
- New database type: mongo, file, memory #414.
- Twitter! Slack! Social median interactions. Hooray! Thanks @jeremylan! #522

# 0.6.0 - 2017-12-30

## Changed

- Enforce 100 character limit for code #159.
- Using root-relative module imports #252.
- `Observatory` is now a parameter for a POCS instance #195.
- Better handling of simulator types #200.
- Log improvements:
    - Separate files for each level and new naming scheme
    - Reduced log format
    - Better reusing of logger
    - Single shared MongoClient connection
    - Improvements to build process
- State machine location more flexible
- Testing improvements
- Updates to many wiki pages.
- Misc bug fixes and improvements.

## Added

- Merge PEAS into POCS
- Merge PACE into POCS
- Support added for testing of serial devices
- Basic dome support
- Polar alignment helper functions moved from PIAA

## Removed

- Remove threading support from rs232.SerialData.

# 0.5.1 - 2017-12-02

## Added

- First real release!
- Working POCS features:
    - mount (iOptron)
    - cameras (DSLR, SBIG)
    - focuser (Birger)
    - scheduler (simple)
    - Relies on separate repositories PEAS and PACE
    - Automated testing with travis-ci.org
    - Code coverage via codecov.io
    - Basic install scripts
