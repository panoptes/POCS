import typer
from rich import print
from typing_extensions import Annotated

from panoptes.pocs.mount import create_mount_from_config

app = typer.Typer()


@app.command(name='park')
def park_mount(
        confirm: Annotated[bool, typer.Option(..., '--confirm',
                                              prompt='Are you sure you want to park the mount?',
                                              help='Confirm mount parking.')] = False):
    """Parks the mount.

    Warning: This will move the mount to the park position but will not do any safety
    checking. Please make sure the mount is safe to park before running this command.
    """
    if not confirm:
        print('[red]Cancelled.[/red]')
        return typer.Abort()

    mount = create_mount_from_config()
    mount.unpark()
    mount.park()


@app.command(name='slew-home')
def search_for_home(
        confirm: Annotated[bool, typer.Option(..., '--confirm',
                                              prompt='Are you sure you want to slew to the home position?',
                                              help='Confirm slew to home.')] = False):
    """Slews the mount home position.

    Warning: This will move the mount to the home position but will not do any safety
    checking. Please make sure the mount is safe to move before running this command.
    """
    if not confirm:
        print('[red]Cancelled.[/red]')
        return typer.Abort()

    mount = create_mount_from_config()
    mount.unpark()
    mount.slew_to_home(blocking=True)
    mount.disconnect()


@app.command(name='search-home')
def search_for_home(
        confirm: Annotated[bool, typer.Option(..., '--confirm',
                                              prompt='Are you sure you want to search for home?',
                                              help='Confirm mount searching for home.')] = False):
    """Searches for the mount home position.

    Warning: This will move the mount to the home position but will not do any safety
    checking. Please make sure the mount is safe to move before running this command.
    """
    if not confirm:
        print('[red]Cancelled.[/red]')
        return typer.Abort()

    mount = create_mount_from_config()
    mount.search_for_home()
    mount.disconnect()
