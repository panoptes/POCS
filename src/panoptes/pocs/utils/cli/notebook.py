import subprocess
import typer

app = typer.Typer()


@app.command()
def start(
        environment: str = typer.Option('lab',
                                        help='The environment to start, either "lab" or "notebook".'),
        public: bool = typer.Option(True,
                                    help='If True, start the server on all interfaces. '
                                         'If False, only start on localhost.'),
        port: int = typer.Option(8888, help='The port to start the server on.'),

):
    """Start a Jupyter notebook server"""
    typer.echo(f"Starting {environment} server")

    try:
        cmd = ["jupyter", environment, "--no-browser", f"--port={port}"]
        if public:
            cmd.append("--ip=0.0.0.0")
        subprocess.run(cmd)
    except KeyboardInterrupt:
        typer.echo("Notebook server stopped")


@app.command('password')
def set_password(
        environment: str = typer.Option('lab',
                                        help='The environment to set password for, either "lab" or "notebook".'),
):
    """Set a password for the notebook server"""
    typer.echo(f"Setting {environment} password")

    try:
        cmd = ["jupyter", environment, "password"]
        subprocess.run(cmd)
    except KeyboardInterrupt:
        typer.echo("Notebook server stopped")
