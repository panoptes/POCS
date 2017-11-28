# Getting Started
If you are unsure about a possible contribution to the project contact the project owners about your idea.

Please see the [code of conduct](https://github.com/panoptes/POCS/blob/develop/CODE_OF_CONDUCT.md) for our
playground rules and follow them during all your contributions.


# Pull Request Process
* Pre-requisites
   - Ensure you have [github account](https://github.com/join)
   - If the change you wish to make is not already an Issue in the project please create one specifying the need.
* Process
   - Create a fork of the repository and use a topic branch within your fork to make changes.
      - All of our repositories have a default branch of `develop` when you first clone them, but your work should be in a separate branch.
      - Create a branch with a descriptive name, e.g.:
         - `git checkout -b new-camera-simulator`
         - `git checkout -b issue-28`
   - Ensure that your code meets this project's standards (see Testing and Code Formatting below).
         - Run `python setup.py test` from the `$POCS` directory before pushing to github
   - Squash your commits so they only reflect meaningful changes.
   - Submit a pull request to the repository, be sure to reference the issue number it addresses.


# Setting up Local Environment
  - Follow instructions on the [Coding in PANOPTES](https://github.com/panoptes/POCS/wiki/Coding-in-PANOPTES).


# Testing
 - All changes should have corresponding tests and existing tests should pass after your changes.
 - For more on testing see the [Coding in PANOPTES](https://github.com/panoptes/POCS/wiki/Coding-in-PANOPTES) page.


# Code Formatting

- All Python should use [PEP 8 Standards](https://www.python.org/dev/peps/pep-0008/)
   - Line length is set at 120 characters instead of 80
   - It is recommended to have your editor auto-format code whenever you save a file rather than attempt to go back and change an entire file all at once. 
- Do not leave in commented-out code or unnecessary whitespace.
- Variable/function/class and file names should be meaningful and descriptive.
- File names should be underscored, not contain spaces ex. my_file.py.
- Define any project specific terminology or abbreviations you use in the file you use them.
- Use appropriate logging:
   + Log level:
      + INFO (i.e. `self.logger.info()`) should be used sparingly and meant to convey information to a person actively watching a running unit.
      + DEBUG (i.e. `self.logger.debug()`) should attempt to capture all run-time information.
      + WARNING (i.e. `self.logger.warning()`) should alert when something does not go as expected but operation of unit can continue.
      + ERROR (i.e. `self.logger.error()`) should be used at critical levels when operation cannot continue.
   + The logger support variable information without the use of the `format` method. Examples:
      * `self.logger.info("Welcome {}", self.config['name'])`
      * `self.logger.debug("Connection to camera {} on {}", cam_num, cam_port)`
