from pathlib import Path
from google.cloud import storage

from panoptes.pocs.utils.logger import get_logger

logger = get_logger()


def upload_image(
    file_path: Path,
    bucket_path: str,
    bucket_name: str = "panoptes-images-incoming",
    timeout: float = 180.0,
    storage_client=None,
) -> str:
    """Uploads an image to google storage bucket."""
    storage_client: storage.Client = storage_client or storage.Client()
    bucket: storage.Bucket = storage_client.bucket(bucket_name)

    blob = bucket.blob(bucket_path)
    logger.debug(f"Uploading {file_path} to {bucket_name}/{bucket_path}")
    blob.upload_from_filename(file_path.as_posix(), timeout=timeout)
    logger.info(f"File successfully uploaded to {blob.public_url}")

    return blob.public_url
