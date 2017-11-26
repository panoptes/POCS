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
   - Use a tool such as [yapf](https://github.com/google/yapf) to format your
     files; we'd rather spend time developing Panoptes and not arguing about
     style.
- Do not leave in commented-out code or unnecessary whitespace.
- Variable/function/class and file names should be meaningful and descriptive
- File names should be lower case and underscored, not contain spaces. For
  example, `my_file.py` instead of `My File.py`
- Define any project specific terminology or abbreviations you use in the file you use them
