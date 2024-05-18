import json
import os
import stat
import time
from pathlib import Path
from typing import List

import requests
import typer
from google.cloud import firestore
from google.cloud import storage
from panoptes.utils.config.client import set_config, get_config
from rich import print
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from panoptes.pocs.utils.cloud import upload_image

app = typer.Typer()
upload_app = typer.Typer()
app.add_typer(upload_app, name='upload')


@app.command('get-key')
def get_key_cmd(unit_id: str = typer.Option(..., prompt=True),
                secret_password: str = typer.Option(..., prompt=True, hide_input=True),
                save_dir: Path = Path('~/keys').expanduser(),
                key_name: str = 'panoptes-upload-key.json',
                enable_image_upload: bool = True,
                url: str = 'https://us-central1-project-panoptes-01.cloudfunctions.net/get-upload-key'
                ):
    """Get a service account key for image uploading.

    Note: You must know the `secret_password` to get the key.
    """
    # Check if a key already exists at location.
    save_path = save_dir / key_name
    if save_path.exists():
        print(f'[red]Key already exists at {save_path}[/]')
        return

    # Make a request for the key.
    res = requests.post(url, json=dict(pwd=secret_password, unit_id=unit_id))
    if not res.ok:
        print(f'[red]Error getting key: {res.text}[/]')
        return

    # Save the response content as the key.
    save_dir.mkdir(parents=True, exist_ok=True)
    with open(save_path, 'w') as f:
        f.write(res.content.decode('utf-8'))

    # Store the path to the key in the GOOGLE_APPLICATION_CREDENTIALS env var in zshrc and bashrc.
    # Also sets the UNIT_ID and PANID env vars (to the same thing).
    try:
        for rc_file in [Path('~/.zshrc').expanduser(), Path('~/.bashrc').expanduser()]:
            if not rc_file.exists():
                continue

            with rc_file.open('a') as f:
                f.write(f'\nexport GOOGLE_APPLICATION_CREDENTIALS="{save_path.absolute().as_posix()}"\n')
                f.write(f'\nexport PANID="{unit_id}"\n')
                f.write(f'\nexport UNIT_ID="{unit_id}"\n')

    except Exception as e:
        print(f'[red]Error writing to ~/.zshrc: {e}[/]')

    # Change file permissions so only the owner can read/write.
    os.chmod(save_path, stat.S_IRUSR | stat.S_IWUSR)
    print(f'Key saved to env var [green]GOOGLE_APPLICATION_CREDENTIALS=[/][blue]{save_path.absolute().as_posix()}[/]')

    # Update the config entries.
    if enable_image_upload:
        try:
            response = set_config('panoptes_network.service_account_key', save_path.absolute().as_posix())
            if response is None:
                raise ValueError('No response from config server')

            response = set_config('observations.upload_image', True)
            if response is None:
                raise ValueError('No response from config server')

            print(f'Service account key added to config and image uploading turned on.')

        except Exception as e:
            print(f'[red]Error updating config: {e}[/]')


@app.command('upload-metadata')
def upload_metadata(dir_path: Path = '.', unit_id: str = None, verbose: bool = False):
    """Send json files in directory to firestore."""
    try:
        unit_id = unit_id or os.getenv('unit_id', get_config('pan_id', default='PAN000'))
    except KeyError:
        print(f'Need to pass a unit_id param or set UNIT_ID envvar.')
        return

    print(f'Listening to {dir_path.absolute()} for {unit_id}')
    event_handler = FileSystemEventHandler()
    firestore_db = firestore.Client()
    # Get the unit reference to link metadata to unit.
    unit_metadata_ref = firestore_db.document(f'units/{unit_id}/metadata')
    metadata_records_ref = unit_metadata_ref.collection('records')

    def handleEvent(event):
        if event.is_directory:
            return

        if 'current' not in event.src_path:
            if verbose:
                print(f'Skipping {event.src_path}')
            return

        try:
            record = json.loads(Path(event.src_path).read_text())

            # Unpack the envelope.
            collection = record['type']
            data = record['data']
            data['date'] = record['date']
            data['received_time'] = firestore.SERVER_TIMESTAMP

            if verbose:
                print(f'Adding data for {collection=}: {data}')

            # Update the main "current" record for the unit.
            unit_metadata_ref.set({collection: data}, merge=True)

            # Add the record, storing the collection name in the data.
            data['collection'] = collection
            doc_ts, doc_id = metadata_records_ref.add(data)
            if verbose:
                print(f'Added data to firestore with {doc_id.id=} at {doc_ts}')
        except Exception as e:
            print(f'Exception {e!r}')

    event_handler.on_modified = handleEvent
    file_observer = Observer()
    file_observer.schedule(event_handler, dir_path.as_posix())
    file_observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f'Cleaning up file watcher')
        file_observer.stop()
    finally:
        file_observer.join()


@upload_app.command('image')
def upload_image_cmd(file_path: Path, bucket_path: str,
                     bucket_name: str = 'panoptes-images-incoming',
                     timeout: float = 180.,
                     storage_client=None
                     ) -> str:
    """Uploads an image to google storage bucket."""
    public_url = upload_image(
        file_path, bucket_path,
        bucket_name=bucket_name,
        timeout=timeout,
        storage_client=storage_client
    )
    print(f'[green]File successfully uploaded to {public_url}[/]')


@upload_app.command('directory')
def upload_directory(directory_path: Path,
                     exclude: str,
                     prefix: str,
                     bucket_name: str = 'panoptes-images-incoming',
                     continue_on_error: bool = False,
                     storage_client=None
                     ) -> List[str]:
    """Uploads all the contents of a directory.

    This removes the directory path itself from the absolute path and appends the
    optional `prefix`. Any file that matches the string `exclude` will be excluded.
    Regexp support not currently provided.

    Note: It would be more efficient to use the `gsutil`. This function is offered
    merely as a convenience.
    """
    assert directory_path.is_dir() and directory_path.exists(), print('[red]Need a directory that exists')

    storage_client = storage_client or storage.Client()

    public_urls = list()
    for file_path in directory_path.iterdir():
        if exclude in str(file_path):
            continue

        bucket_path = str(Path(prefix) / file_path)
        try:
            public_url = upload_image(
                file_path, bucket_path, bucket_name=bucket_name,
                storage_client=storage_client
            )
            public_urls.append(public_url)
        except Exception as e:
            print(f'[red]Upload error on {file_path}. {continue_on_error=}')
            if continue_on_error:
                continue

    return public_urls
