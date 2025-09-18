import os
import subprocess
import sys

import typer
from git import GitCommandError, Repo
from rich import print
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from panoptes.pocs.utils.cli import (
    camera,
    config,
    mount,
    network,
    notebook,
    power,
    run,
    sensor,
    weather,
)

app = typer.Typer()
state = {"verbose": False}

app.add_typer(config.app, name="config", help="Interact with the config server.")
app.add_typer(network.app, name="network", help="Interact with panoptes network.")
app.add_typer(mount.app, name="mount", help="Simple mount controls.")
app.add_typer(camera.app, name="camera", help="Simple camera controls.")
app.add_typer(notebook.app, name="notebook", help="Start Jupyter notebook environment.")
app.add_typer(power.app, name="power", help="Interact with power relays.")
app.add_typer(run.app, name="run", help="Run POCS!")
app.add_typer(sensor.app, name="sensor", help="Interact with system sensors.")
app.add_typer(weather.app, name="weather", help="Interact with weather station service.")


@app.callback()
def main(
    context: typer.Context,
    config_host: str = "127.0.0.1",
    config_port: int = 6563,
    verbose: bool = False,
):
    state.update(
        {
            "config_host": config_host,
            "config_port": config_port,
            "verbose": verbose,
        }
    )
    if verbose:
        print(f"Command options from main: {context.params!r}")


@app.command(name='update')
def update_repo():
    """Update POCS.

    This will pull the latest changes from github and show any relevant messages.
    """
    new_commits = []

    project_root = find_project_root()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        # Start update task
        t_update = progress.add_task(f"Updating {project_root}", total=1)
        repo = Repo(project_root)

        try:
            origin = repo.remotes.origin
            origin.fetch()

            # If local dir is dirty, stash changes.
            if repo.is_dirty():
                progress.update(t_update, description="Stashing local changes...", advance=1)
                repo.git.stash("push")

            # Get the current commit and the latest remote commit
            current_commit = repo.head.commit
            latest_remote_commit = repo.active_branch.tracking_branch().commit

            if current_commit == latest_remote_commit:
                progress.update(t_update, description="Project is already up to date. No action needed.", advance=1)
                return

            # Find the commits between the current state and the remote
            new_commits = list(repo.iter_commits(f'{current_commit}...{latest_remote_commit}'))

            progress.update(t_update, description="Updates found. Pulling latest changes...", advance=1)
            origin.pull()

            progress.update(t_update, description="Successfully pulled the latest changes.", advance=1)
        except GitCommandError as e:
            progress.update(t_update, description=f"[red]Failed to pull the latest changes: {e}[/red]", advance=1)
            raise typer.Abort()
        except Exception as e:
            progress.update(t_update, description=f"[red]Error: {e}[/red]", advance=1)
            raise typer.Abort()
        else:
            progress.update(t_update, description="[green]Update process complete![/green]", advance=1)

            # After pulling, show any update messages and sync dependencies
            if len(new_commits):
                show_messages(start_commit=new_commits[0].hexsha, end_commit=new_commits[-1].hexsha)
        finally:
            # Apply stashed changes
            if repo.git.stash("list"):
                repo.git.stash("pop")

        # Sync dependencies with the new pyproject.toml by showing message updates.
        run_hatch_command(['run', 'pocs', 'update-deps'])


@app.command(name="show-messages")
def show_messages(
    start_commit: str = None,
    end_commit: str = None,
):
    """Shows any important update messages."""
    if start_commit is not None and end_commit is not None:
        project_root = find_project_root()
        repo = Repo(project_root)

        start_commit = start_commit or repo.active_branch.commit
        end_commit = end_commit or repo.active_branch.commit

        commits = list(repo.iter_commits(f'{start_commit}...{end_commit}'))

        notices = []
        for commit in commits:
            notice_location = commit.message.find("NOTICE: ")
            if notice_location != -1:
                notices.append(f"* [green]{commit.message[notice_location + 8:]}[/]")

        if notices:
            print(Panel.fit(f"\n{', '.join(notices)}", title='[bold magenta]Notices[/]', border_style='yellow'))


@app.command(name="update-deps")
def update_dependencies(context: typer.Context):
    """A simple way to force dependency updates."""
    context.params.update(context.parent.params)
    verbose = context.params["verbose"]
    if verbose:
        print("Dependencies updated")


def run_hatch_command(command: list):
    """
    Runs a hatch command using subprocess and handles potential errors.
    """
    try:
        process = subprocess.run(
            ['hatch'] + command,
            capture_output=True,
            text=True,
            check=True,
            timeout=120
        )
        print(process.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing hatch command: {e.stderr}", file=sys.stderr)
        raise
    except FileNotFoundError:
        print("Hatch is not installed or not in PATH.", file=sys.stderr)
        raise


def find_project_root(start_path=None):
    """
    Finds the project root by searching for a 'pyproject.toml' file
    or a '.git' directory.

    Args:
        start_path (str, optional): The directory to start the search from.
                                    Defaults to the current working directory.

    Returns:
        str: The absolute path to the project root, or None if not found.
    """
    if start_path is None:
        # Start from the directory of the currently executing script
        start_path = os.path.abspath(os.path.dirname(__file__))

    current_path = start_path

    while True:
        # Check for common project root markers
        if any(os.path.exists(os.path.join(current_path, marker)) for marker in ['pyproject.toml', '.git', 'setup.py']):
            return current_path

        parent_path = os.path.dirname(current_path)

        # If we've reached the root of the file system, stop
        if parent_path == current_path:
            return None

        current_path = parent_path


if __name__ == "__main__":
    app()
