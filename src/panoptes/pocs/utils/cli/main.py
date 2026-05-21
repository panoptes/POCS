"""Top-level Typer application entry point for POCS CLI.

Aggregates feature subcommands (camera, mount, config, network, etc.) and
provides a shared callback to set common options like verbosity.
"""

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
    telemetry,
    weather,
)

app = typer.Typer(no_args_is_help=True)
state = {"verbose": False}

app.add_typer(config.app, name="config", help="Interact with the config store.")
app.add_typer(network.app, name="network", help="Interact with panoptes network.")
app.add_typer(mount.app, name="mount", help="Simple mount controls.")
app.add_typer(camera.app, name="camera", help="Simple camera controls.")
app.add_typer(notebook.app, name="notebook", help="Start Jupyter notebook environment.")
app.add_typer(power.app, name="power", help="Interact with power relays.")
app.add_typer(run.app, name="run", help="Run POCS!")
app.add_typer(sensor.app, name="sensor", help="Interact with system sensors.")
app.add_typer(telemetry.app, name="telemetry", help="Run the POCS telemetry server.")
app.add_typer(weather.app, name="weather", help="Interact with weather station service.")


@app.callback()
def main(
    context: typer.Context,
    config_host: str = typer.Option("127.0.0.1", hidden=True),
    config_port: int = typer.Option(6563, hidden=True),
    verbose: bool = False,
):
    """Top-level CLI callback to set shared options for subcommands.

    Args:
        context: Typer context object.
        verbose: If True, enables verbose output.

    Returns:
        None
    """
    state.update(
        {
            "config_host": config_host,
            "config_port": config_port,
            "verbose": verbose,
        }
    )
    if verbose:
        print(f"Command options from main: {context.params!r}")


@app.command(name="version")
def show_version():
    """Show the version of POCS and related packages."""
    from importlib.metadata import PackageNotFoundError, version

    # We try to get the git version for POCS if we are in a repo
    pocs_version = "unknown"
    try:
        project_root = find_project_root()
        if project_root:
            repo = Repo(project_root)
            pocs_version = repo.git.describe("--tags", "--always", "--dirty")
    except Exception:
        try:
            pocs_version = version("panoptes-pocs")
        except PackageNotFoundError:
            pass

    print(f"panoptes-pocs: [green]{pocs_version}[/]")

    try:
        utils_version = version("panoptes-utils")
        print(f"panoptes-utils: [green]{utils_version}[/]")
    except PackageNotFoundError:
        print("panoptes-utils: [red]not found[/]")


@app.command(name="update")
def update_repo(
    branch: str = typer.Option(
        None,
        "--branch",
        "-b",
        help="Update from a specific git branch, ignoring tagged release requirement.",
    ),
    dev: bool = typer.Option(
        False,
        "--dev",
        help="Pull the latest commit from 'main' instead of the latest tagged release.",
    ),
):
    """Update POCS.

    By default, checks out the latest tagged release. Use ``--dev`` to pull the
    latest commit from ``main``, or ``--branch`` to update from a specific branch
    (which bypasses the tagged-release requirement).

    Args:
        branch: A specific git branch to checkout and pull from. Overrides tagged-release
            behaviour when provided. Names starting with ``-`` are rejected.
        dev: If True, pull the latest commit from ``main`` instead of the latest tag.
    """
    # Validate branch name to prevent git option injection.
    if branch is not None and branch.startswith("-"):
        print(f"[red]Invalid branch name: '{branch}'. Branch names must not start with '-'.[/red]")
        raise typer.Exit(code=1)

    new_commits = []
    project_root = find_project_root()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        t_update = progress.add_task(f"Updating {project_root}...", total=None)
        repo = Repo(project_root)

        try:
            origin = repo.remotes.origin
            progress.update(t_update, description="Fetching remote information...")
            origin.fetch("--tags")

            # If local dir is dirty, stash changes.
            if repo.is_dirty():
                progress.update(t_update, description="Stashing local changes...")
                repo.git.stash("push")

            # Determine the target ref (tag, branch, or 'main' for --dev).
            if branch is not None:
                # --branch explicitly provided: checkout and pull that branch.
                target_ref = branch
                target_is_branch = True
            elif dev:
                # --dev: pull latest commit from main.
                target_ref = "main"
                target_is_branch = True
            else:
                # Default: find the latest tagged release.
                tags = sorted(
                    repo.tags,
                    key=lambda t: t.commit.committed_date,
                )
                if not tags:
                    print("[red]No tags found in the repository. Use --dev to pull from main.[/red]")
                    raise typer.Exit(code=1)
                latest_tag = tags[-1]
                target_ref = latest_tag.name
                target_is_branch = False
                progress.update(t_update, description=f"Latest release tag: {target_ref}")

            # Checkout the target ref if we're not already on it.
            current_ref = repo.active_branch.name if not repo.head.is_detached else repo.head.commit.hexsha
            if current_ref != target_ref:
                progress.update(t_update, description=f"Checking out '{target_ref}'...")
                repo.git.checkout(target_ref)
                print(f"[bold green]Switched to '{target_ref}'.[/bold green]")

            if target_is_branch:
                # Pull latest commits for the branch.
                current_commit = repo.head.commit
                tracking = repo.active_branch.tracking_branch()
                if tracking is None:
                    # Set upstream to origin/<branch> if not already set.
                    repo.git.branch("--set-upstream-to", f"origin/{target_ref}", target_ref)
                    tracking = repo.active_branch.tracking_branch()

                latest_remote_commit = tracking.commit if tracking else None

                if latest_remote_commit and current_commit == latest_remote_commit:
                    progress.update(t_update, description="Already up to date.")
                    return

                if latest_remote_commit:
                    new_commits = list(repo.iter_commits(f"{current_commit}...{latest_remote_commit}"))

                progress.update(t_update, description=f"Pulling latest changes from '{target_ref}'...")
                origin.pull(target_ref)
            else:
                # Tag checkout: check if we're already at the latest tag.
                current_commit = repo.head.commit
                tag_commit = latest_tag.commit
                if current_commit == tag_commit:
                    progress.update(t_update, description=f"Already at latest release ({target_ref}).")
                    return

                progress.update(
                    t_update, description=f"Checked out release tag '{target_ref}'. No pull needed."
                )

            progress.update(t_update, description="Successfully updated.")
        except GitCommandError as e:
            progress.update(t_update, description=f"[red]Failed to update: {e}[/red]")
            raise typer.Abort()
        except Exception as e:
            progress.update(t_update, description=f"[red]Error: {e}[/red]")
            raise typer.Abort()
        else:
            progress.update(t_update, description="[green]Update process complete![/green]")

            if new_commits:
                show_messages(start_commit=new_commits[0].hexsha, end_commit=new_commits[-1].hexsha)
        finally:
            # Re-apply any stashed changes.
            if repo.git.stash("list"):
                repo.git.stash("pop")

        # Sync dependencies with the new pyproject.toml.
        run_uv_command(["run", "pocs", "update-deps"])


@app.command(name="show-messages")
def show_messages(
    start_commit: str = None,
    end_commit: str = None,
):
    """Show any important update messages between two commits.

    Args:
        start_commit: The starting commit SHA or ref. If None, uses the active branch head.
        end_commit: The ending commit SHA or ref. If None, uses the active branch head.

    Returns:
        None
    """
    project_root = find_project_root()
    repo = Repo(project_root)

    start_commit = start_commit or repo.active_branch.commit
    end_commit = end_commit or repo.active_branch.commit

    commits = list(repo.iter_commits(f"{start_commit}...{end_commit}"))

    notices = []
    for commit in commits:
        notice_location = commit.message.find("NOTICE: ")
        if notice_location != -1:
            notice_msg = commit.message[notice_location + 8 :].replace("\n", " ")
            notices.append(f"* [green]{notice_msg}[/]")

    if notices:
        print(
            Panel.fit(
                f"\n{'\n'.join(notices)}",
                title="[bold magenta]Notices[/]",
                border_style="yellow",
            )
        )


@app.command(name="update-deps")
def update_dependencies(context: typer.Context):
    """A simple way to force dependency updates.

    Args:
        context: Typer context allowing propagation of parent parameters.

    Returns:
        None
    """
    context.params.update(context.parent.params)
    verbose = context.params["verbose"]
    if verbose:
        print("Dependencies updated")


def run_uv_command(command: list):
    """Run a uv command using subprocess and handle potential errors.

    Args:
        command: The list of arguments to pass to the uv executable, e.g.,
            ["run", "pocs", "update-deps"].

    Returns:
        None

    Raises:
        subprocess.CalledProcessError: If the uv command exits with a non-zero status.
        FileNotFoundError: If uv is not installed or not found in PATH.
    """
    try:
        process = subprocess.run(["uv"] + command, capture_output=True, text=True, check=True, timeout=120)
        print(process.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing uv command: {e.stderr}", file=sys.stderr)
        raise
    except FileNotFoundError:
        print("uv is not installed or not in PATH.", file=sys.stderr)
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
        if any(
            os.path.exists(os.path.join(current_path, marker))
            for marker in ["pyproject.toml", ".git", "setup.py"]
        ):
            return current_path

        parent_path = os.path.dirname(current_path)

        # If we've reached the root of the file system, stop
        if parent_path == current_path:
            return None

        current_path = parent_path


if __name__ == "__main__":
    app()
