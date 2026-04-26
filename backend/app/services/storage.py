import shutil
from pathlib import Path
from typing import BinaryIO

import boto3

from app.core.config import settings


def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def upload_file(local_path: Path, key: str) -> str:
    if settings.use_r2:
        _r2_client().upload_file(str(local_path), settings.R2_BUCKET_NAME, key)
        return key
    dest = settings.project_dir / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(local_path.read_bytes())
    return str(dest)


def upload_fileobj(fileobj: BinaryIO, key: str) -> str:
    """Stream a file-like object straight to R2 (no temp landing).

    Used by the upload endpoint so the API container doesn't have to write
    the GTFS zip to its own filesystem — the Worker container is a separate
    process with a separate filesystem and would otherwise see ENOENT.

    Returns the storage key so the caller can dispatch it to Celery.
    """
    if settings.use_r2:
        _r2_client().upload_fileobj(fileobj, settings.R2_BUCKET_NAME, key)
        return key
    dest = settings.project_dir / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(fileobj, f)
    return str(dest)


def download_to_path(key: str, local_path: Path) -> Path:
    """Pull a stored object down to a local file path.

    Used by the worker to materialise the input zip on its own filesystem
    before opening it. When R2 isn't configured, treat `key` as a local
    path under `project_dir` (or absolute) and copy if needed.
    """
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if settings.use_r2:
        _r2_client().download_file(settings.R2_BUCKET_NAME, key, str(local_path))
        return local_path
    src = Path(key)
    if not src.is_absolute():
        src = settings.project_dir / key
    if src.resolve() != local_path.resolve():
        local_path.write_bytes(src.read_bytes())
    return local_path


def delete_file(key: str) -> None:
    """Delete a stored file by key.

    Key format: {tenant_id}/projects/{project_id}/output/{filename}
    """
    if settings.use_r2:
        _r2_client().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    else:
        target = settings.project_dir / key
        if target.exists():
            target.unlink()


def generate_presigned_url(key: str, expires: int = 3600) -> str:
    if settings.use_r2:
        return _r2_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key},
            ExpiresIn=expires,
        )
    return f"/api/v1/projects/download/{key}"
