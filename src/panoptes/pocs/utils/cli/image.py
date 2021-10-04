from pathlib import Path

import watchdog.events
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import typer

app = typer.Typer()


@app.command()
def process_image(
        image_path: Path
):
    """Process a raw image."""
    if image_path.exists() is False:
        raise FileNotFoundError(f'{image_path} does not exist')

    typer.secho(f'Processing {image_path}')


@app.command()
def watch_directory(dir_path: Path):
    """Watches for changes to a directory and acts on changes."""
    if dir_path.is_dir() is False:
        raise NotADirectoryError(f'Not a directory: {dir_path}')

    typer.secho(f'Listening on {dir_path}')
    file_handler = FileSystemEventHandler()
    file_handler.on_any_event = handle_new_file
    observer = Observer()
    observer.schedule(file_handler, str(dir_path.absolute()), recursive=True)
    observer.start()
    try:
        while observer.is_alive():
            observer.join(1)
    finally:
        observer.stop()
        observer.join()


def handle_new_file(event: watchdog.events.FileSystemEvent):
    """Handles the file event."""
    if event.event_type == 'created' and not event.is_directory:
        typer.secho(f'Received new file: {event.src_path}')
        process_image(Path(event.src_path))
