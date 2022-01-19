from pathlib import Path
from typing import List

import typer

from google.cloud import storage

app = typer.Typer()
upload_app = typer.Typer()
app.add_typer(upload_app, name='upload')


@upload_app.command('image')
def upload_image(file_path: Path, bucket_path: str,
                 bucket_name: str = 'panoptes-images-incoming',
                 storage_client=None) -> str:
    """Uploads an image to google storage bucket."""
    storage_client: storage.Client = storage_client or storage.Client()
    bucket: storage.Bucket = storage_client.bucket(bucket_name)

    blob = bucket.blob(bucket_path)
    typer.secho(f'Uploading {file_path} to {bucket_name}/{bucket_path}')
    blob.upload_from_filename(str(file_path))
    typer.secho(f'File successfully uploaded to {blob.public_url}')

    return blob.public_url


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
    assert directory_path.is_dir() and directory_path.exists(), typer.secho(
        'Need a directory that exists')

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
            typer.secho(f'Upload error on {file_path}. {continue_on_error=}')
            if continue_on_error:
                continue

    return public_urls
