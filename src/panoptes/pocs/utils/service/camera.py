import shutil
import sys
import subprocess
from typing import Optional

from pydantic import BaseModel
from fastapi import FastAPI


class Command(BaseModel):
    """Accepts an arbitrary command string which is passed to gphoto2."""
    arguments: str = '--auto-detect'
    output: Optional[str] = ''
    success: bool = False


app = FastAPI()


@app.on_event('startup')
def startup_tasks():
    gphoto2_path = shutil.which('gphoto2')
    if gphoto2_path is None:
        print('Cannot find gphoto2, exiting system.')
        sys.exit(1)


@app.post('/gphoto')
def gphoto(command: Command):
    """Perform arbitrary gphoto2 command."""

    # Build the full command.
    full_command = [shutil.which('gphoto2'), command.arguments]

    print(f'Running {command.arguments=!r}')
    completed_proc = subprocess.run(full_command, capture_output=True)

    command.success = completed_proc.returncode >= 0
    command.output = completed_proc.stdout

    return command
