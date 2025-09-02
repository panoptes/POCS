# CONTRIBUTING GUIDE

Please see the [code of conduct](https://github.com/panoptes/POCS/blob/develop/CODE_OF_CONDUCT.md) for our playground rules and follow them during all your contributions.

## Getting Started

We prefer that all changes to POCS have an associated [GitHub Issue in the project](https://github.com/panoptes/POCS/issues) that explains why it is needed. This allows us to debate the best approach to address the issue before folks spend a lot of time writing code. If you are unsure about a possible contribution to the project, please contact the project owners about your idea; of course, an [issue](https://github.com/panoptes/POCS/issues) is a good way to do this.

## Pull Request Process

> Note: This is a summary of the process. See the [POCS wiki](https://github.com/panoptes/POCS/wiki/PANOPTES-Feature-Development-Process) for more info.

- Pre-requisites
- Ensure you have a [github account.](https://github.com/join)
- [Setup ssh access for github](https://help.github.com/en/github/authenticating-to-github/connecting-to-github-with-ssh).
- If the change you wish to make is not already an [Issue in the project](https://github.com/panoptes/POCS/issues), please create one specifying the need.

### Process

1. Create a fork of the repository via github (button in top-right).
2. Clone your fork to your local system:

   ```bash
   cd $PANDIR
   git clone git@github.com:YOUR-GITHUB-NAME/POCS.git
   ```

3. Set the "upstream" branch to `panoptes` and fetch the upstream changes:

   ```bash
   cd POCS
   git remote add upstream https://github.com/panoptes/POCS.git
   git fetch upstream
   ```

4. Use a topic branch within your fork to make changes. All of our repositories have a default branch of `develop` when you first clone them, but your work should be in a separate branch (see note below). Your branch should be based off of the `upstream/develop` branch.

   Create a branch with a descriptive name, e.g.:

   ```bash
   git checkout -b new-camera-simulator upstream/develop
   git checkout -b issue-28 upstream/develop
   ```

5. Ensure that your code meets this project's standards (see Testing and Code Formatting below).

6. Run the testing suite locally to ensure that all tests are passing. See Testing below.

7. Submit a pull request to the repository, be sure to reference the issue number it addresses.

> See ["A successful Git branching model"](https://nvie.com/posts/a-successful-git-branching-model/) for details on how the repository is structured.

## Code Formatting

- All Python should use [PEP 8 Standards](https://www.python.org/dev/peps/pep-0008/)
- Line length is set at 100 characters instead of 80.
- It is recommended to have your editor auto-format code whenever you save a file rather than attempt to go back and change an entire file all at once. There are many plugins that exist for this.
- You can also use [yapf (Yet Another Python Formatter)](https://github.com/google/yapf) for which POCS includes a style file (.style.yapf). For example:

  ```bash
  # cd to the root of your workspace.
  cd $(git rev-parse --show-toplevel)
  # Format the modified python files in your workspace.
  yapf -i $(git diff --name-only | egrep '\.py$')
  ```

- Do not leave in commented-out code or unnecessary whitespace.
- Variable/function/class and file names should be meaningful and descriptive.
- File names should be lower case and underscored, not contain spaces. For example, `my_file.py` instead of `My File.py`.
- Define any project specific terminology or abbreviations you use in the file you use them.

## Log Messages

Use appropriate logging:

- DEBUG (i.e. `self.logger.debug()`) should attempt to capture all run*time information.
- INFO (i.e. `self.logger.info()`) should be used sparingly and meant to convey information to a person actively watching a running unit.
- WARNING (i.e. `self.logger.warning()`) should alert when something does not go as expected but operation of unit can continue.
- ERROR (i.e. `self.logger.error()`) should be used at critical levels when operation cannot continue.
- The logger supports variable information without the use of the `format` method.
- There is a `say` method available on the main `POCS` class that is meant to be used in friendly manner to convey information to a user. This should be used only for personable output and is typically displayed in the "chat box" of the PAWS website. These messages are also sent to the INFO level logger.

### Logging examples

Note: These are meant to illustrate the logging calls and are not necessarily indicative of real operation.

```python
self.say("I'm all ready to go, first checking the weather")

self.logger.info(f'PANOPTES unit initialized: {self.name}')

self.logger.debug("Setting up weather station")

self.logger.warning(f'Problem getting wind safety: {e!r}')

self.logger.debug(f'Rain: {is_raining} Clouds: {is_cloudy} Dark: {is_dark} Temp: {temp:.02f}')

self.logger.error('Unable to connect to AAG Cloud Sensor, cannot continue')
```

#### Viewing log files

- You typically want to follow an active log file by using `tail -F` on the command line.

```bash
tail -F $PANDIR/logs/panoptes.log
```

## Test POCS

POCS comes with a testing suite that allows it to test that all of the software works and is installed correctly. Running the test suite by default will use simulators for all of the hardware and is meant to test that the software works correctly. Additionally, the testing suite can be run with various flags to test that attached hardware is working properly.

### Software Testing

There are a few scenarios where you want to run the test suite:

1. You are getting your unit ready and want to test software is installed correctly.
2. You are upgrading to a new release of software (POCS, its dependencies or the operating system).
3. You are helping develop code for POCS and want test your code doesn't break something.

#### Testing your installation

In order to test your installation you should have followed all of the steps above for getting your unit ready. To run the test suite, you will need to open a terminal and navigate to the `$POCS` directory.

```bash
cd $POCS

# Run the software testing
panoptes-develop test
```

> Note: The test suite will give you some warnings about what is going on and give you a chance to cancel the tests (via `Ctrl-c`).

It is often helpful to view the log output in another terminal window while the test suite is running:

```bash
# Follow the log file
tail -F $PANDIR/logs/panoptes.log
```

#### Testing your code changes

> Note: This step is meant for people helping with software development.

The testing suite will automatically be run against any code committed to our github repositories. However, the test suite should also be run locally before pushing to github. This can be done either by running the entire test suite as above or by running an individual test related to the code you are changing. For instance, to test the code related to the cameras one can run:

```bash
pytest -xv pocs/tests/test_camera.py
```

Here the `-x` option will stop the tests upon the first failure and the `-v` makes the testing verbose. Note that some tests might require additional software. This software is installed in the docker image, which is used by the `test-software.sh` script above), but is **not** used when calling `pytest` directly. For instance, anything requiring plate solving needs `astrometry.net` installed.

Any new code should also include proper tests. See below for details.

#### Writing tests

All code changes should include tests. We strive to maintain a high code coverage and new code should necessarily maintain or increase code coverage. For more details see the [Writing Tests](https://github.com/panoptes/POCS/wiki/Writing-Tests-for-POCS) page.

### Hardware Testing

Hardware testing uses the same testing suite as the software testing but with additional options passed on the command line to signify what hardware should be tested.

The options to pass to `pytest` is `--with-hardware`, which accepts a list of possible hardware items that are connected. This list includes `camera`, `mount`, and `weather`. Optionally you can use `all` to test a fully connected unit.

> Warning: The hardware tests do not perform safety checking of the weather or dark sky. The `weather` test mentioned above tests if a weather station is connected but does not test the safety conditions. It is assumed that hardware testing is always done with direct supervision.

```bash
# Test an attached camera
pytest --with-hardware=camera

# Test an attached camera and mount
pytest --with-hardware=camera,mount

# Test a fully connected unit
pytest --with-hardware=all
```
