from pathlib import Path

import typer

from google.cloud import storage

app = typer.Typer()

storage_client: storage.Client = storage.Client()


@app.command()
def upload(file_path: Path, bucket_path: str, bucket_name: str = 'panoptes-images-incoming'):
    """Uploads an image to google storage bucket."""
    bucket: storage.Bucket = storage_client.bucket(bucket_name)
    if not bucket.exists():
        typer.secho(f'Bucket does not exist: {bucket_name}', fg='red')
        return

    blob = bucket.blob(bucket_path)
    typer.secho(f'Uploading {file_path} to {bucket_name}/{bucket_path}')
    blob.upload_from_filename(file_path)
    typer.secho(f'File successfully uploaded to {blob.public_url}')

    return blob.public_url
