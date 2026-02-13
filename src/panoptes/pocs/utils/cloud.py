"""Google Cloud Storage helper functions for PANOPTES."""

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
    """Upload a local image file to a Google Cloud Storage bucket.

    Args:
        file_path (Path): Path to the local file to upload.
        bucket_path (str): Destination path within the bucket (object name), e.g. "images/2025/09/foo.jpg".
        bucket_name (str): Name of the target GCS bucket. Defaults to "panoptes-images-incoming".
        timeout (float): Timeout in seconds for the upload request. Defaults to 180.0.
        storage_client (google.cloud.storage.Client | None): Optional pre-configured storage client.
            If not provided, a new Client() will be created using application default credentials.

    Returns:
        str: The public URL of the uploaded object.

    Raises:
        google.api_core.exceptions.GoogleAPIError: If the upload fails due to a GCS error.
        FileNotFoundError: If the provided file_path does not exist.

    Notes:
        Ensure that application default credentials are configured (e.g., via GOOGLE_APPLICATION_CREDENTIALS)
        or the environment supports implicit credentials for the storage client.
    """
    storage_client: storage.Client = storage_client or storage.Client()
    bucket: storage.Bucket = storage_client.bucket(bucket_name)

    blob = bucket.blob(bucket_path)
    logger.debug(f"Uploading {file_path} to {bucket_name}/{bucket_path}")
    blob.upload_from_filename(file_path.as_posix(), timeout=timeout)
    logger.debug(f"File successfully uploaded to {blob.public_url}")

    return blob.public_url
