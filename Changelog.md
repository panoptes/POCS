## [Unreleased]

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
