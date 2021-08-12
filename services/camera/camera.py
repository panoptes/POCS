import re
import shutil
import sys
import subprocess
from pathlib import Path
from typing import Optional
from loguru import logger

from pydantic import BaseModel, BaseSettings, DirectoryPath
from fastapi import FastAPI


class Settings(BaseSettings):
    base_dir: Optional[DirectoryPath]


class Command(BaseModel):
    """Accepts an arbitrary command string which is passed to gphoto2."""
    arguments: str = '--auto-detect'
    success: bool = False
    output: Optional[str]
    error: Optional[str]
    returncode: Optional[int]


settings = Settings()
app = FastAPI()


@app.on_event('startup')
def startup_tasks():
    if shutil.which('gphoto2') is None:
        logger.error('Cannot find gphoto2, exiting system.')
        sys.exit(1)


@app.post('/')
def gphoto(command: Command):
    """Perform arbitrary gphoto2 command."""
    logger.info(f'Received {command=!r}')

    # Fix the filename.
    filename_match = re.search(r'--filename (.*.cr2)', command.arguments)
    if filename_match:
        filename_path = Path(filename_match.group(1))

        # If the application has a base directory, save there with same filename.
        if settings.base_dir is not None:
            logger.debug(f'Saving file to {settings.base_dir=} instead of {str(filename_path)}')
            app_filename = settings.base_dir / filename_path.name

            # Replace in arguments.
            filename_in_args = f'--filename {str(filename_path)}'
            logger.debug(f'Replacing {filename_path} with {app_filename}.')
            command.arguments = command.arguments.replace(filename_in_args, f'--filename {app_filename}')

    # Build the full command.
    full_command = [shutil.which('gphoto2'), *command.arguments.split(' ')]

    logger.debug(f'Running {full_command=!r}')
    completed_proc = subprocess.run(full_command, capture_output=True)

    # Populate return items.
    command.success = completed_proc.returncode >= 0
    command.returncode = completed_proc.returncode
    command.output = completed_proc.stdout
    command.error = completed_proc.stderr

    logger.info(f'Returning {command!r}')
    return command
