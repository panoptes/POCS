# CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2020-04-07

If you thought 9 months between releases was a long time, how about 18 months! :) This version has a lot of breaking changes and is not backwards compatible with previous versions. The release is a stepping stone on the way to `0.8.0` and (eventually!) a `1.0.0`.

The entire repo has been redesigned to support docker images. This comes with a number of changes, including the refactoring of many items into the [`panoptes-utils`](https://github.com/panoptes/panoptes-utils.git) repo.

There are a lot of changes included in this release, highlights below:

### Added

* Docker :whale: :grinning: :tada: (#951).
* Storing an explicit `safety` collection in the database.
* Configuration file specific for testing rather than relying on `pocs.yaml`.
* Convenience scripts for running tests inside docker container: `scripts/testing/test-software.sh`

### Changed

* :warning: **breaking** Config: Items related to the configuration system have been moved to the [Config Server](https://panoptes-utils.readthedocs.io/en/latest/#config-server) in `panoptes-utils` repo.
  * The main interface for POCS related items is through `self.get_config`, which can take a key and a default, e.g. `self.get_config('mount.horizon', default='30 deg')`.
  * Test writing is affected and is currently more difficult than would be ideal. An updated test writing document will be following this release.
* :warning: **breaking** Logging: Logging has changed to [`loguru`](https://github.com/Delgan/loguru) and has been greatly simplified:
  * `get_root_logger` has been replaced by `get_logger`.
  * The `per-run` logs have been removed and have been replaced by two logs files:
    * `$PANDIR/logs/panoptes.log`: Log file meant for watching on the command line (via `tail`) or for otherwise human-readable logs. Rotated daily at 11:30 am. Only the previous days' log is retained.
    * `$PANDIR/logs/panoptes_YYYYMMDD.log`: Log file meant for archive or information gathering. Stored in JSON format for ingestion into log analysis service. Rotated daily at 11:30 and stored in a compressed file for 7 days. Future updates will add option to upload to google servers.
  * `loguru` provides two new log levels:
    * `trace`: one level below `debug`.
    * `success`: one level above `info`.
* Lots of conversions to `f-strings`.

### Removed

* Cleanup of any stale or unused code.
* All `mongo` related code.
* Weather related items. These have been moved to [`aag-weather`](https://github.com/panoptes/aag-weather).
* All notebook tutorials in favor of [`panoptes-tutorials`](https://github.com/panoptes/panoptes-tutorials).

## [0.6.2] - 2018-09-27

One week between releases is a lot better than 9 months! ;) Some small but important changes mark this release including faster testing times on local machines.  Also a quick release to remove some of the CloudSQL features (but see the shiny new Cloud Functions over in the [panoptes-network](https://github.com/panoptes/panoptes-network) repo!).

### Fixed

* Cameras
  * Use unit_id for sequence and image ids. Important for processing consistency [#613].
* State Machine

### Changed

* Camera
  * Remove camera creation from Observatory [#612].
  * Smarter event waiting [#625].
  * More cleanup, especially path names and pretty images [#610, #613, #614, #620].
* Mount
* Testing
  * Caching some of the build dirs [#611].
  * Only use Mongo DB type during local testing - Local testing with 1/3rd the wait! [#616].
* Google Cloud [#599]
  * Storage improvements [#601].

### Added

* Misc
  * CountdownTimer utility [#625].

### Removed

* Google Cloud [#599]
  * Reverted some of the CloudSQL connectivity [#652]
* Cameras
  * Remove spline smoothing focus [#621].

## [0.6.1] - 2018-09-20

Lots of changes in this release. In particular we've pushed through a lot of changes
(especially with the help of @jamessynge) to make the development process a lot
smoother. This has in turn contribute to the quality of the codebase.

Too long between releases but even more exciting improvements to come! Next up is tackling the events notification system, which will let us start having some vastly improved UI features.

Below is a list of some of the changes.

Thanks to first-time contributors: @jermainegug @jeremylan as well as contributions from many folks over at <https://github.com/AstroHuntsman/huntsman-pocs.>

### Fixed

* Cameras
  * Fix for DATE-OBS fits header [#589].
  * Better property settings for DSLRs [#589].
  * Pretty image improvements [#589].
  * Autofocus improvements for SBIG/Focuser [#535].
  * Primary camera updates [#614, 620].
  * Many bug fixes [#457, #589].
* State Machine
  * Many fixes [#509, #518].

### Changed

* Mount
  * POCS Shell: Hitting `Ctrl-c` will complete movement through states [#590].
  * Pointing updates, including `auto_correct` [#580].
  * Tracking mode updates (**fixes for Northern Hemisphere only!**) [#549].
  * Serial interaction improvements [#388, #403].
  * Shutdown improvements [#407, #421].
* Dome
  * Changes from May Huntsman commissioning run [#535]
* Messaging
  * Better and consistent topic terminology [#593, #605].
  * Anticipation of coming events.
* Misc
  * Default to rereading the fields file for targets [#488].
  * Timelapse updates [#523, #591].

### Added

* Cameras
  * Basic scripts for bias and dark frames.
  * Add support for Optec FocusLynx based focus controllers [#512].
  * Pretty images from FITS files. Thanks @jermainegug! [#538].
* Testing
  * pyflakes testing support for bug squashing! :bettle: [#596].
  * pycodestyle for better code! [#594].
  * Threads instead of process [#468].
  * Fix coverage & Travis config for concurrency [#566].
* Google Cloud [#599]
  * Added instructions for authentication [#600].
  * Add a `pan_id` to units for GCE interaction[#595].
  * Adding Google CloudDB interaction [#602].
* Sensors
  * Much work on arduinos and sensors [#422].
* Misc
  * Startup scripts for easier setup [#475].
  * Install scripts for Ubuntu 18.04 [#585].
  * New database type: mongo, file, memory [#414].
  * Twitter! Slack! Social median interactions. Hooray! Thanks @jeremylan! [#522]

## [0.6.0] - 2017-12-30

### Changed

- Enforce 100 character limit for code [159](https://github.com/panoptes/POCS/pull/159).
- Using root-relative module imports [252](https://github.com/panoptes/POCS/pull/252).
- `Observatory` is now a parameter for a POCS instance [195](https://github.com/panoptes/POCS/pull/195).
- Better handling of simulator types [200](https://github.com/panoptes/POCS/pull/200).
- Log improvements:
  - Separate files for each level and new naming scheme [165](https://github.com/panoptes/POCS/pull/165).
  - Reduced log format [254](https://github.com/panoptes/POCS/pull/254).
  - Better reusing of logger [192](https://github.com/panoptes/POCS/pull/192).
- Single shared MongoClient connection [228](https://github.com/panoptes/POCS/pull/228).
- Improvements to build process [176](https://github.com/panoptes/POCS/pull/176), [166](https://github.com/panoptes/POCS/pull/166).
- State machine location more flexible [209](https://github.com/panoptes/POCS/pull/209), [219](https://github.com/panoptes/POCS/pull/219)
- Testing improvments [249](https://github.com/panoptes/POCS/pull/249).
- Updates to many wiki pages.
- Misc bug fixes and improvements.

### Added

- Merge PEAS into POCS [169](https://github.com/panoptes/POCS/pull/169).
- Merge PACE into POCS [167](https://github.com/panoptes/POCS/pull/167).
- Support added for testing of serial devices [164](https://github.com/panoptes/POCS/pull/164), [180](https://github.com/panoptes/POCS/pull/180).
- Basic dome support [231](https://github.com/panoptes/POCS/pull/231), [248](https://github.com/panoptes/POCS/pull/248).
- Polar alignment helper functions moved from PIAA [265](https://github.com/panoptes/POCS/pull/265).

### Removed

- Remove threading support from rs232.SerialData [148](https://github.com/panoptes/POCS/pull/148).

## [0.5.1] - 2017-12-02

### Added

- First real release!
- Working POCS features:
  + mount (iOptron)
  + cameras (DSLR, SBIG)
  + focuer (Birger)
  + scheduler (simple)
- Relies on separate repositories PEAS and PACE
- Automated testing with travis-ci.org
- Code coverage via codecov.io
- Basic install scripts