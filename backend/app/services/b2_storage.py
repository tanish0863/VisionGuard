"""Backblaze B2 S3-compatible artifact storage service for VisionGuard."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from backend.app.storage import validate_storage_key

logger = logging.getLogger(__name__)


def _get_env_param(primary: str, fallback: str, default: str = "") -> str:
    return os.environ.get(primary, "").strip() or os.environ.get(fallback, "").strip() or default


def get_b2_config() -> dict[str, str]:
    """Retrieve Backblaze B2 configuration from environment variables."""
    bucket = _get_env_param("VISIONGUARD_STORAGE_BUCKET", "B2_BUCKET_NAME", "visionguard-artifacts")
    key_id = _get_env_param("VISIONGUARD_STORAGE_ACCESS_KEY_ID", "B2_ACCESS_KEY_ID", "")
    secret_key = _get_env_param("VISIONGUARD_STORAGE_SECRET_ACCESS_KEY", "B2_SECRET_ACCESS_KEY", "")
    region = _get_env_param("VISIONGUARD_STORAGE_REGION", "B2_REGION", "us-east-005")
    endpoint = _get_env_param("VISIONGUARD_STORAGE_ENDPOINT", "B2_ENDPOINT_URL", "")
    if not endpoint and region:
        endpoint = f"https://s3.{region}.backblazeb2.com"

    return {
        "bucket": bucket,
        "endpoint_url": endpoint,
        "key_id": key_id,
        "secret_key": secret_key,
        "region": region,
    }


def get_b2_client(config: dict[str, str] | None = None) -> Any:
    """Create a boto3 S3 client configured for Backblaze B2."""
    cfg = config or get_b2_config()
    endpoint = cfg["endpoint_url"]
    if endpoint and not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        endpoint = f"https://{endpoint}"

    s3_config = Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"},
        retries={"max_attempts": 3, "mode": "standard"},
        connect_timeout=5,
        read_timeout=30,
    )

    return boto3.client(
        "s3",
        endpoint_url=endpoint or None,
        aws_access_key_id=cfg["key_id"],
        aws_secret_access_key=cfg["secret_key"],
        region_name=cfg["region"] or "us-east-005",
        config=s3_config,
    )


def upload_artifact(
    local_path: str | Path,
    object_key: str,
    content_type: str = "application/octet-stream",
    client: Any | None = None,
    bucket: str | None = None,
) -> str:
    """Upload a local artifact file to Backblaze B2 and return its object key."""
    valid_key = validate_storage_key(object_key)
    cfg = get_b2_config()
    target_bucket = bucket or cfg["bucket"]
    s3 = client or get_b2_client(cfg)

    file_path = Path(local_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Local artifact file not found: {local_path}")

    logger.info("Uploading %s to B2 bucket '%s' at key '%s'", file_path, target_bucket, valid_key)
    s3.upload_file(
        str(file_path),
        target_bucket,
        valid_key,
        ExtraArgs={"ContentType": content_type},
    )
    return valid_key


def upload_bytes(
    data: bytes,
    object_key: str,
    content_type: str = "application/octet-stream",
    metadata: dict[str, str] | None = None,
    client: Any | None = None,
    bucket: str | None = None,
) -> str:
    """Upload binary artifact directly to Backblaze B2."""
    valid_key = validate_storage_key(object_key)
    cfg = get_b2_config()
    target_bucket = bucket or cfg["bucket"]
    s3 = client or get_b2_client(cfg)

    params: dict[str, Any] = {
        "Bucket": target_bucket,
        "Key": valid_key,
        "Body": data,
        "ContentType": content_type,
    }
    if metadata:
        params["Metadata"] = metadata

    s3.put_object(**params)
    return valid_key


def generate_download_url(
    object_key: str,
    expires_in: int = 900,
    client: Any | None = None,
    bucket: str | None = None,
) -> str:
    """Generate a temporary presigned download URL for a Backblaze B2 object.

    Default expiration is 900 seconds (15 minutes).
    """
    valid_key = validate_storage_key(object_key)
    cfg = get_b2_config()
    target_bucket = bucket or cfg["bucket"]
    s3 = client or get_b2_client(cfg)

    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": target_bucket, "Key": valid_key},
        ExpiresIn=expires_in,
    )
    return str(url)


def delete_artifact(
    object_key: str,
    client: Any | None = None,
    bucket: str | None = None,
) -> bool:
    """Delete an artifact object from Backblaze B2."""
    valid_key = validate_storage_key(object_key)
    cfg = get_b2_config()
    target_bucket = bucket or cfg["bucket"]
    s3 = client or get_b2_client(cfg)

    try:
        s3.delete_object(Bucket=target_bucket, Key=valid_key)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in {"NoSuchKey", "404"}:
            return False
        raise
