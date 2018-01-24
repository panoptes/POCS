## [Unreleased]
## [0.6.0] - 2018-01-24
### Fixed
- Mount
    - Fix tracking adjustments [332](https://github.com/panoptes/POCS/pull/332), [355](https://github.com/panoptes/POCS/pull/355)
- Misc bug fixes and improvements [329](https://github.com/panoptes/POCS/pull/329), [330](https://github.com/panoptes/POCS/pull/330), [333](https://github.com/panoptes/POCS/pull/333), [334](https://github.com/panoptes/POCS/pull/334), [346](https://github.com/panoptes/POCS/pull/346), [380](https://github.com/panoptes/POCS/pull/380), [398](https://github.com/panoptes/POCS/pull/398)

### Changed
- Dome improvements [352](https://github.com/panoptes/POCS/pull/352)
- Image utils split into sub-folders [279](https://github.com/panoptes/POCS/pull/279) 
- Mongo db namespace changes to allow customization [325](https://github.com/panoptes/POCS/pull/325)
- Google storage utils updates (and code removal) [386](https://github.com/panoptes/POCS/pull/386), [401](https://github.com/panoptes/POCS/pull/401)
- Mount serial fixes [388](https://github.com/panoptes/POCS/pull/388), [403](https://github.com/panoptes/POCS/pull/403)
- Log files stored in `per-run` directory with one symlink to main dir [396](https://github.com/panoptes/POCS/pull/396)
- Find gphoto2 consistently [406](https://github.com/panoptes/POCS/pull/406)
- DB access consistency [408](https://github.com/panoptes/POCS/pull/408)
- Sort our your requirements! [411](https://github.com/panoptes/POCS/pull/411)

### Added
- Lots of work done with the arduinos:
    - Separate collecting and reporting of values [291](https://github.com/panoptes/POCS/pull/291)
    - Auto detect arduino port and type [280](https://github.com/panoptes/POCS/pull/280)    
    - New arduino sketch for power board ("trucker board") [278](https://github.com/panoptes/POCS/pull/278)
    - Shared arduino libraries made easier [282](https://github.com/panoptes/POCS/pull/282),[290](https://github.com/panoptes/POCS/pull/290), [301](https://github.com/panoptes/POCS/pull/301), [302](https://github.com/panoptes/POCS/pull/302), [303](https://github.com/panoptes/POCS/pull/303), [338](https://github.com/panoptes/POCS/pull/338)
    - Verify arduino sketches as part of travis testing [288](https://github.com/panoptes/POCS/pull/288)
    - Much better testing of serial connections [320](https://github.com/panoptes/POCS/pull/320)
    - Arduino simulator work [358](https://github.com/panoptes/POCS/pull/358), [360](https://github.com/panoptes/POCS/pull/360)
- POCS and PEAS Shell improvements:
    - Auto completion of command options [306](https://github.com/panoptes/POCS/pull/306)
    - Power-cycling of computer fixed [308](https://github.com/panoptes/POCS/pull/308)
    - Better handling of commands sent from PEAS shell [300](https://github.com/panoptes/POCS/pull/300), [375](https://github.com/panoptes/POCS/pull/375)
- Testing updates:
    + Mock TheSkyX [287](https://github.com/panoptes/POCS/pull/287)
- Pretty images from FITS files [319](https://github.com/panoptes/POCS/pull/319)
- Constraints:
    - Basic custom Horizon constraint [368](https://github.com/panoptes/POCS/pull/368), [413](https://github.com/panoptes/POCS/pull/413)
    - AlreadyVisited costraint [378](https://github.com/panoptes/POCS/pull/378)
- Codestyle checks for PEAS code [359](https://github.com/panoptes/POCS/pull/359), [370](https://github.com/panoptes/POCS/pull/370)
- More documentation!
- More tests!
- Better taste!

### Removed
- Unused code:
    - image utils [274](https://github.com/panoptes/POCS/pull/274)
    - jupyter widgets [286](https://github.com/panoptes/POCS/pull/286)

Thanks @jamessynge, @jermainegug, @brendan-o, @wtgee

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
