Please see the
[code of conduct](https://github.com/panoptes/POCS/blob/develop/CODE_OF_CONDUCT.md) 
for our playground rules and follow them during all your contributions.

# Getting Started

We prefer that all changes to POCS have an associated
[GitHub Issue in the project](https://github.com/panoptes/POCS/issues)
that explains why it is needed. This allows us to debate the best
approach to address the issue before folks spend a lot of time
writing code. If you are unsure about a possible contribution to
the project, please contact the project owners about your idea;
of course, an [issue](https://github.com/panoptes/POCS/issues) is a
good way to do this.

# Pull Request Process
_This is a summary of the process. See
[the POCS wiki](https://github.com/panoptes/POCS/wiki/PANOPTES-Feature-Development-Process)
for more info._

* Pre-requisites
   - Ensure you have a [github account.](https://github.com/join)
   - If the change you wish to make is not already an
     [Issue in the project](https://github.com/panoptes/POCS/issues),
     please create one specifying the need.
* Process
   - Create a fork of the repository and use a topic branch within your fork to make changes.
      - All of our repositories have a default branch of `develop` when you first clone them, but 
      your work should be in a separate branch.
      - Create a branch with a descriptive name, e.g.:
         - `git checkout -b new-camera-simulator`
         - `git checkout -b issue-28`
   - Ensure that your code meets this project's standards (see Testing and Code Formatting below).
         - Run `python setup.py test` from the `$POCS` directory before pushing to github
   - Squash your commits so they only reflect meaningful changes.
   - Submit a pull request to the repository, be sure to reference the issue number it 
      addresses.


# Setting up Local Environment
  - Follow instructions in the [README](https://github.com/panoptes/POCS/blob/develop/README.md) 
    as well as the [Coding in PANOPTES](https://github.com/panoptes/POCS/wiki/Coding-in-PANOPTES) 
    document.


# Testing
 - All changes should have corresponding tests and existing tests should pass after 
    your changes.
 - For more on testing see the 
 [Coding in PANOPTES](https://github.com/panoptes/POCS/wiki/Coding-in-PANOPTES) page.

# Code Formatting

- All Python should use [PEP 8 Standards](https://www.python.org/dev/peps/pep-0008/)
   - Line length is set at 100 characters instead of 80.
   - It is recommended to have your editor auto-format code whenever you save a file 
      rather than attempt to go back and change an entire file all at once.
   - You can also use
     [yapf (Yet Another Python Formatter)](https://github.com/google/yapf)
     for which POCS includes a style file (.style.yapf). For example:
     ```bash
     # cd to the root of your workspace.
     cd $(git rev-parse --show-toplevel)
     # Format the modified python files in your workspace.
     yapf -i $(git diff --name-only | egrep '\.py$')
     ```
- Do not leave in commented-out code or unnecessary whitespace.
- Variable/function/class and file names should be meaningful and descriptive.
- File names should be lower case and underscored, not contain spaces. For example, `my_file.py` 
instead of `My File.py`.
- Define any project specific terminology or abbreviations you use in the file you use them.
- Use root-relative imports (i.e. relative to the POCS directory). This means that rather
  than using a directory relative imports such as:
  ```python
  from ..base import PanBase
  from ..utils import current_time
  ```
  Import from the top-down instead:
  ```python
  from pocs.base import PanBase
  from pocs.utils import current_time
  ```
  The same applies to code inside of `peas`.
- Test imports are slightly different because `pocs/tests` and `peas/tests` are not Python
  packages (those directories don't contain an `__init__.py` file). For imports of `pocs` or
  `peas` code, use root-relative imports as described above. For importing test packages and
  modules, assume the test doing the imports is in the root directory.

# Log Messages

Use appropriate logging:
- Log level:
   - DEBUG (i.e. `self.logger.debug()`) should attempt to capture all run-time 
      information.
   - INFO (i.e. `self.logger.info()`) should be used sparingly and meant to convey 
      information to a person actively watching a running unit.
   - WARNING (i.e. `self.logger.warning()`) should alert when something does not
      go as expected but operation of unit can continue.
   - ERROR (i.e. `self.logger.error()`) should be used at critical levels when 
      operation cannot continue.
- The logger supports variable information without the use of the `format` method.
- There is a `say` method available on the main `POCS` class that is meant to be
used in friendly manner to convey information to a user. This should be used only 
for personable output and is typically displayed in the "chat box"of the PAWS 
website. These messages are also sent to the INFO level logger.

#### Logging examples:

_Note: These are meant to illustrate the logging calls and are not necessarily indicative of real 
operation_

```
self.logger.info("PANOPTES unit initialized: {}", self.config['name'])

self.say("I'm all ready to go, first checking the weather")

self.logger.debug("Setting up weather station")

self.logger.warning('Problem getting wind safety: {}'.format(e))

self.logger.debug("Rain: {} Clouds: {} Dark: {} Temp: {:.02f}",
   is_raining,
   is_cloudy,
   is_dark,
   temp_celsius
)

self.logger.error('Unable to connect to AAG Cloud Sensor, cannot continue')
```

#### Viewing log files

- You typically want to follow an active log file by using `tail -F` on the command line.
- The [`grc`](https://github.com/garabik/grc) (generic colouriser) can be used with 
`tail` to get pretty log files.

```
(panoptes-env) $ grc tail -F $PANDIR/logs/pocs_shell.log
```

The following screenshot shows commands entered into a `jupyter-console` in the top 
panel and the log file in the bottom panel.

<p align="center">
   <img src="http://www.projectpanoptes.org/images/log-example.png" width="600">
</p>
