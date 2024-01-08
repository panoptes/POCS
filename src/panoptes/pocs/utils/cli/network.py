from pathlib import Path
from typing import List

import os
import stat
import requests
import typer
from google.cloud import storage
from rich import print

from panoptes.pocs.utils.cloud import upload_image
from panoptes.utils.config.client import set_config

app = typer.Typer()
upload_app = typer.Typer()
app.add_typer(upload_app, name='upload')


@app.command('get-key')
def get_key_cmd(secret_password: str,
                save_dir: Path = Path('~/keys').expanduser(),
                url: str = 'https://us-central1-project-panoptes-01.cloudfunctions.net/get-upload-key'
                ):
    """Get a service account key for image uploading.

    Note: You must know the `secret_password` to get the key.
    """
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / 'panoptes-upload-key.json'
    if save_path.exists():
        print(f'[red]Key already exists at {save_path}[/]')
        return

    # Make a request for the key.
    res = requests.post(url, json=dict(pwd=secret_password))
    if not res.ok:
        print(f'[red]Error getting key: {res.text}[/]')
        return

    # Save the response content as the key.
    with open(save_path, 'w') as f:
        f.write(res.content.decode('utf-8'))

    # Change file permissions so only the owner can read/write.
    os.chmod(save_path, stat.S_IRUSR | stat.S_IWUSR)
    print(f'Key saved to [blue]{save_path.absolute().as_posix()}[/]')

    # Update the config entries.
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


@upload_app.command('image')
def upload_image_cmd(file_path: Path, bucket_path: str,
                     bucket_name: str = 'panoptes-images-incoming',
                     timeout: float = 180.,
                     storage_client=None) -> str:
    """Uploads an image to google storage bucket."""
    public_url = upload_image(file_path, bucket_path,
                              bucket_name=bucket_name,
                              timeout=timeout,
                              storage_client=storage_client)
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
            public_url = upload_image(file_path, bucket_path, bucket_name=bucket_name,
                                      storage_client=storage_client)
            public_urls.append(public_url)
        except Exception as e:
            print(f'[red]Upload error on {file_path}. {continue_on_error=}')
            if continue_on_error:
                continue

    return public_urls
