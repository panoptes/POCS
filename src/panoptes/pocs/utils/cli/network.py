"""Typer CLI commands for PANOPTES networking and uploads.

Includes helpers to retrieve a service account key, watch and upload JSON metadata
to Firestore, and upload images or directories to Google Cloud Storage.
"""
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
app.add_typer(upload_app, name="upload")


@app.command("get-key")
def get_key_cmd(
    unit_id: str = typer.Option(..., prompt=True),
    secret_password: str = typer.Option(..., prompt=True, hide_input=True),
    save_dir: Path = Path("~/keys").expanduser(),
    key_name: str = "panoptes-upload-key.json",
    enable_image_upload: bool = True,
    url: str = "https://us-central1-project-panoptes-01.cloudfunctions.net/get-upload-key",
):
    """Retrieve and install a service account key for image uploads.

    Args:
        unit_id (str): The PANOPTES unit identifier to associate with the key.
        secret_password (str): Shared secret required by the key service.
        save_dir (Path): Directory to save the JSON key file. Defaults to ~/keys.
        key_name (str): Filename for the key JSON. Defaults to 'panoptes-upload-key.json'.
        enable_image_upload (bool): If True, update config to enable image upload and
            set the key path. Defaults to True.
        url (str): HTTPS endpoint that returns the key when provided unit_id and password.

    Returns:
        None

    Notes:
        Also appends environment exports to ~/.zshrc and ~/.bashrc for
        GOOGLE_APPLICATION_CREDENTIALS, PANID, and UNIT_ID, and sets key file
        permissions to owner read/write only.
    """
    # Check if a key already exists at location.
    save_path = save_dir / key_name
    if save_path.exists():
        print(f"[red]Key already exists at {save_path}[/]")
        return

    # Make a request for the key.
    res = requests.post(url, json=dict(pwd=secret_password, unit_id=unit_id))
    if not res.ok:
        print(f"[red]Error getting key: {res.text}[/]")
        return

    # Save the response content as the key.
    save_dir.mkdir(parents=True, exist_ok=True)
    with open(save_path, "w") as f:
        f.write(res.content.decode("utf-8"))

    # Store the path to the key in the GOOGLE_APPLICATION_CREDENTIALS env var in zshrc and bashrc.
    # Also sets the UNIT_ID and PANID env vars (to the same thing).
    try:
        for rc_file in [Path("~/.zshrc").expanduser(), Path("~/.bashrc").expanduser()]:
            if not rc_file.exists():
                continue

            with rc_file.open("a") as f:
                f.write(
                    f'\nexport GOOGLE_APPLICATION_CREDENTIALS="{save_path.absolute().as_posix()}"\n'
                )
                f.write(f'\nexport PANID="{unit_id}"\n')
                f.write(f'\nexport UNIT_ID="{unit_id}"\n')

    except Exception as e:
        print(f"[red]Error writing to ~/.zshrc: {e}[/]")

    # Change file permissions so only the owner can read/write.
    os.chmod(save_path, stat.S_IRUSR | stat.S_IWUSR)
    print(
        f"Key saved to env var [green]GOOGLE_APPLICATION_CREDENTIALS=[/][blue]{save_path.absolute().as_posix()}[/]"
    )

    # Update the config entries.
    if enable_image_upload:
        try:
            response = set_config(
                "panoptes_network.service_account_key", save_path.absolute().as_posix()
            )
            if response is None:
                raise ValueError("No response from config server")

            response = set_config("observations.upload_image", True)
            if response is None:
                raise ValueError("No response from config server")

            print("Service account key added to config and image uploading turned on.")

        except Exception as e:
            print(f"[red]Error updating config: {e}[/]")


@app.command("upload-metadata")
def upload_metadata(
    dir_path: Path = "/home/panoptes/json_store/panoptes",
    unit_id: str = None,
    verbose: bool = False,
):
    """Watch a directory and upload JSON metadata files to Firestore.

    Args:
        dir_path (Path): Directory containing JSON envelopes to watch. Defaults to
            '/home/panoptes/json_store/panoptes'.
        unit_id (str | None): Unit identifier to attach to records; if None uses
            environment/config via _get_unit_id().
        verbose (bool): If True, echo progress and debug information.

    Returns:
        None

    Notes:
        Expects files named with 'current' under dir_path that contain envelopes of
        the form {'type': <record_type>, 'data': {...}, 'date': ...}. Records are
        added under units/{unit_id}/metadata and the unit document is updated.
    """
    unit_id = unit_id or _get_unit_id()

    if verbose:
        print(f"Listening to {dir_path.absolute()} for {unit_id}")

    firestore_db = firestore.Client()
    # Get the unit reference to link metadata to unit.
    unit_ref = firestore_db.document(f"units/{unit_id}")
    metadata_records_ref = unit_ref.collection("metadata")

    def handleEvent(event):
        if event.is_directory:
            return

        if "current" not in event.src_path:
            if verbose:
                print(f"Skipping {event.src_path}")
            return

        try:
            record = json.loads(Path(event.src_path).read_text())

            # Unpack the envelope.
            record_type = record["type"]
            data = record["data"]
            data["date"] = record["date"]
            data["received_time"] = firestore.SERVER_TIMESTAMP

            if verbose:
                print(f"Adding data for {record_type=}: {data}")

            # Update the unit's metadata with the record_type.
            unit_ref.set(
                {
                    "metadata": {record_type: data},
                    "last_updated": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )

            # Add the record, storing the record_type name in the data.
            data["record_type"] = record_type
            doc_ts, doc_id = metadata_records_ref.add(data)
            if verbose:
                print(f"Added data to firestore with {doc_id.id=} at {doc_ts}")
        except Exception as e:
            print(f"Exception {e!r}")

    file_observer = _start_event_handler(dir_path, handleEvent)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if verbose:
            print("Cleaning up file watcher")
        file_observer.stop()
    finally:
        file_observer.join()


@upload_app.command("image")
def upload_image_cmd(
    file_path: Path,
    bucket_path: str,
    bucket_name: str = "panoptes-images-incoming",
    timeout: float = 180.0,
    storage_client=None,
) -> str:
    """Upload a single image file to a Google Cloud Storage bucket.

    Args:
        file_path (Path): Local path to the image file to upload.
        bucket_path (str): Object name (path) within the bucket to store the file.
        bucket_name (str): Destination bucket name. Defaults to 'panoptes-images-incoming'.
        timeout (float): Request timeout in seconds. Defaults to 180.0.
        storage_client: Optional pre-configured storage client instance.

    Returns:
        str: The public URL of the uploaded object.
    """
    public_url = upload_image(
        file_path,
        bucket_path,
        bucket_name=bucket_name,
        timeout=timeout,
        storage_client=storage_client,
    )
    print(f"[green]File successfully uploaded to {public_url}[/]")
    return public_url


@upload_app.command("directory")
def upload_directory(
    directory_path: Path,
    exclude: str,
    prefix: str,
    bucket_name: str = "panoptes-images-incoming",
    continue_on_error: bool = False,
    storage_client=None,
) -> List[str]:
    """Upload all files in a directory to a Google Cloud Storage bucket.

    This removes the directory path itself from the absolute path and appends the
    optional `prefix`. Any file that contains the substring `exclude` will be skipped.

    Args:
        directory_path (Path): The directory whose files will be uploaded.
        exclude (str): Substring filter; skip files whose path contains this value.
        prefix (str): Path prefix to prepend to each object's bucket path.
        bucket_name (str): Destination bucket name. Defaults to 'panoptes-images-incoming'.
        continue_on_error (bool): If True, continue uploading other files if an error occurs.
        storage_client: Optional pre-configured storage client instance.

    Returns:
        list[str]: Public URLs of successfully uploaded files.

    Notes:
        For bulk transfers, using 'gsutil -m rsync' is typically faster and more robust.
    """
    assert directory_path.is_dir() and directory_path.exists(), print(
        "[red]Need a directory that exists"
    )

    storage_client = storage_client or storage.Client()

    public_urls = list()
    for file_path in directory_path.iterdir():
        if exclude in str(file_path):
            continue

        bucket_path = str(Path(prefix) / file_path)
        try:
            public_url = upload_image(
                file_path, bucket_path, bucket_name=bucket_name, storage_client=storage_client
            )
            public_urls.append(public_url)
        except Exception:
            print(f"[red]Upload error on {file_path}. {continue_on_error=}")
            if continue_on_error:
                continue

    return public_urls


def _get_unit_id():
    """Get the unit id from the environment or config."""
    unit_id = os.getenv("UNIT_ID", get_config("pan_id"))

    if unit_id is None:
        raise ValueError("No unit id found in environment or config")

    return unit_id


def _start_event_handler(dir_path: Path, handle_event: callable):
    """Start the event handler."""
    event_handler = FileSystemEventHandler()
    event_handler.on_modified = handle_event
    file_observer = Observer()
    file_observer.schedule(event_handler, dir_path.as_posix())
    file_observer.start()
    return file_observer
