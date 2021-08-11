import re
import shutil
import sys
import subprocess
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from fastapi import FastAPI


class Command(BaseModel):
    """Accepts an arbitrary command string which is passed to gphoto2."""
    arguments: str = '--auto-detect'
    filename: str = '%Y%m%dT%H%M%S.%C'
    base_dir: str = '/images'
    output: Optional[str] = ''
    error: Optional[str] = ''
    success: bool = False
    returncode: Optional[int]


app = FastAPI()


@app.on_event('startup')
def startup_tasks():
    gphoto2_path = shutil.which('gphoto2')
    if gphoto2_path is None:
        print('Cannot find gphoto2, exiting system.')
        sys.exit(1)


@app.post('/')
def gphoto(command: Command):
    """Perform arbitrary gphoto2 command."""

    # Fix the filename.
    print(command.arguments)
    filename_match = re.search(r'--filename (.*.cr2)', command.arguments)
    if filename_match:
        filename_path = Path(filename_match.group(1))
        print(f'Found matching filename {filename_path}')
        command.filename = filename_path.name
        # Remove from arguments
        filename_in_args = f'--filename {str(filename_path)}'
        print(f'Removing {filename_in_args!r} from arguments.')
        command.arguments = command.arguments.replace(filename_in_args, '')

    # Build the full command.
    full_command = [
        shutil.which('gphoto2'),
        f'--filename={command.base_dir}/{command.filename}',
        *command.arguments.split(' ')
    ]

    print(f'Running {full_command=!r}')
    completed_proc = subprocess.run(full_command, capture_output=True)

    command.success = completed_proc.returncode >= 0
    command.returncode = completed_proc.returncode
    command.output = completed_proc.stdout
    command.error = completed_proc.stderr

    return command
