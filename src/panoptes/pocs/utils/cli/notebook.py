"""Typer CLI for managing a Jupyter server on a PANOPTES unit.

Provides commands to start Jupyter Lab/Notebook, set a password, and restart the
supervised service.
"""

import subprocess
import shutil
from pathlib import Path

import typer
from rich import print

app = typer.Typer()


@app.command()
def start(
    environment: str = typer.Option(
        "lab", help='The environment to start, either "lab" or "notebook".'
    ),
    public: bool = typer.Option(
        True, help="If True, start the server on all interfaces. If False, only start on localhost."
    ),
    port: int = typer.Option(8888, help="The port to start the server on."),
    notebook_dir: Path = typer.Option(None, envvar="HOME", help="The notebook directory."),
):
    """Start a Jupyter server (Lab or classic Notebook).

    Args:
        environment (str): Which frontend to start: 'lab' or 'notebook'. Defaults to 'lab'.
        public (bool): If True, bind to 0.0.0.0 for remote access; otherwise localhost only.
        port (int): TCP port to listen on. Defaults to 8888.
        notebook_dir (Path): Directory to serve notebooks from. Defaults to $HOME.

    Returns:
        None
    """
    check_for_jupyter()

    print(f"Starting {environment} server.")

    try:
        cmd = [
            "jupyter",
            environment,
            "--no-browser",
            f"--port={port}",
            f"--notebook-dir={notebook_dir}",
        ]
        if public:
            cmd.append("--ip=0.0.0.0")
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("Notebook server stopped.")


@app.command("password")
def set_password(
    environment: str = typer.Option(
        "lab", help='The environment to set password for, either "lab" or "notebook".'
    ),
):
    """Set a password for the Jupyter server.

    Args:
        environment (str): Which frontend to configure: 'lab' or 'notebook'. Defaults to 'lab'.

    Returns:
        None
    """
    check_for_jupyter()
    print(f"Setting {environment} password.")
    cmd = ["jupyter", environment, "password"]
    subprocess.run(cmd)


def check_for_jupyter():
    """Check if Jupyter is installed"""
    if shutil.which("jupyter-lab") is None:
        mamba_available = shutil.which("mamba") is not None
        conda_available = shutil.which("conda") is not None
        if mamba_available:
            install_msg = "Install with `mamba install -c conda-forge jupyterlab`."
        elif conda_available:
            install_msg = "Install with `conda install -c conda-forge jupyterlab`."
        else:
            install_msg = "Install with `pip install jupyterlab`"

        print(
            f"[red]Jupyter is not installed. {install_msg}",
        )
        raise typer.Exit()


@app.command()
def restart():
    """Restart the jupyter server process via supervisorctl"""
    cmd = "supervisorctl restart pocs-jupyter-server"
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True)
