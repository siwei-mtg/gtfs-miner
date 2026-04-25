import boto3
from pathlib import Path
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
