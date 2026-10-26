"""Distributed artifact storage abstraction for VisionGuard.

Supports:
- Local filesystem storage for development and local testing.
- Cloudflare R2 / S3-compatible object storage for distributed deployments
  (e.g., FastAPI on Render + Workers on Hugging Face Spaces).
"""
from __future__ import annotations

import io
import logging
import mimetypes
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

logger = logging.getLogger(__name__)

# Security: Allowed pattern for object keys (rejects path traversal and unsafe chars)
_SAFE_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+(/[a-zA-Z0-9_\-\.]+)*$")
_MAX_KEY_LENGTH = 1024


class StorageConfigurationError(RuntimeError):
    """Raised when storage backend environment or options are invalid."""
    pass


class StorageObjectNotFoundError(FileNotFoundError):
    """Raised when the requested object is not found in the storage backend."""
    pass


class StorageSecurityError(PermissionError):
    """Raised when an object key violates security constraints or attempts traversal."""
    pass


def validate_storage_key(key: str) -> str:
    """Validate and sanitize a storage key.

    Rejects:
    - Null bytes, backslashes, leading/trailing whitespace.
    - Path traversal attempts ('..', '.', empty path segments).
    - Absolute URI schemes (http://, file://).
    - Keys exceeding max length.

    Returns the normalized key without leading slashes.
    """
    if not key or not isinstance(key, str):
        raise StorageSecurityError("Storage key cannot be empty")

    cleaned = key.strip().replace("\\", "/").lstrip("/")

    if len(cleaned) > _MAX_KEY_LENGTH:
        raise StorageSecurityError(f"Storage key exceeds maximum length of {_MAX_KEY_LENGTH} characters")

    if "\x00" in cleaned:
        raise StorageSecurityError("Storage key contains null byte")

    # Reject path traversal segments
    parts = cleaned.split("/")
    for part in parts:
        if part in {"..", "."} or not part:
            raise StorageSecurityError(f"Storage key contains invalid traversal segment '{part}': '{key}'")

    if not _SAFE_KEY_PATTERN.match(cleaned):
        raise StorageSecurityError(f"Storage key contains forbidden characters: '{key}'")

    return cleaned


@runtime_checkable
class ArtifactStorage(Protocol):
    """Abstract interface for VisionGuard artifact storage backends."""

    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Store binary data under the given key; returns normalized storage key."""
        ...

    def get_object(self, key: str) -> tuple[bytes, str]:
        """Retrieve binary data and content type for key; raises StorageObjectNotFoundError if missing."""
        ...

    def head_object(self, key: str) -> dict[str, Any] | None:
        """Retrieve metadata and size without reading body; returns None if not found."""
        ...

    def delete_object(self, key: str) -> bool:
        """Delete object at key; returns True if deleted or False if not found."""
        ...

    def list_objects(self, prefix: str = "") -> list[str]:
        """List all object keys matching the given prefix."""
        ...

    def object_exists(self, key: str) -> bool:
        """Check whether an object exists."""
        ...

    def generate_presigned_url(self, key: str, expires_in: int = 900) -> str:
        """Generate a temporary signed download URL for the object."""
        ...


class FileSystemArtifactStorage:
    """Local filesystem storage backend for development and testing."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_environment(cls) -> FileSystemArtifactStorage:
        env_dir = os.environ.get("VISIONGUARD_ARTIFACTS_DIR")
        if env_dir:
            root = Path(env_dir).resolve()
        else:
            root = Path(__file__).resolve().parents[2] / "artifacts"
        return cls(root)

    def _resolve_safe_path(self, key: str) -> Path:
        valid_key = validate_storage_key(key)
        target = (self.root / valid_key).resolve()
        try:
            if not target.is_relative_to(self.root):
                raise StorageSecurityError(f"Resolved path '{target}' escapes root '{self.root}'")
        except AttributeError:
            # Python < 3.9 fallback
            if not str(target).startswith(str(self.root)):
                raise StorageSecurityError(f"Resolved path '{target}' escapes root '{self.root}'")
        return target

    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        valid_key = validate_storage_key(key)
        target = self._resolve_safe_path(valid_key)
        target.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write via temporary file
        temp_dir = target.parent
        with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False) as tf:
            tf.write(data)
            temp_name = tf.name

        try:
            os.replace(temp_name, target)
        except Exception:
            if os.path.exists(temp_name):
                os.remove(temp_name)
            raise

        return valid_key

    def get_object(self, key: str) -> tuple[bytes, str]:
        target = self._resolve_safe_path(key)
        if not target.is_file():
            raise StorageObjectNotFoundError(f"Artifact object not found: '{key}'")
        mime, _ = mimetypes.guess_type(str(target))
        return target.read_bytes(), mime or "application/octet-stream"

    def head_object(self, key: str) -> dict[str, Any] | None:
        target = self._resolve_safe_path(key)
        if not target.is_file():
            return None
        stat = target.stat()
        mime, _ = mimetypes.guess_type(str(target))
        return {
            "key": validate_storage_key(key),
            "size": stat.st_size,
            "content_type": mime or "application/octet-stream",
            "last_modified": stat.st_mtime,
        }

    def delete_object(self, key: str) -> bool:
        target = self._resolve_safe_path(key)
        if not target.is_file():
            return False
        try:
            target.unlink()
            return True
        except FileNotFoundError:
            return False

    def list_objects(self, prefix: str = "") -> list[str]:
        sanitized_prefix = prefix.strip().replace("\\", "/").lstrip("/")
        results: list[str] = []
        for path in self.root.rglob("*"):
            if path.is_file():
                rel = path.relative_to(self.root).as_posix()
                if not sanitized_prefix or rel.startswith(sanitized_prefix):
                    results.append(rel)
        return sorted(results)

    def object_exists(self, key: str) -> bool:
        target = self._resolve_safe_path(key)
        return target.is_file()

    def generate_presigned_url(self, key: str, expires_in: int = 900) -> str:
        valid_key = validate_storage_key(key)
        return f"/api/v1/artifacts/{valid_key}"


class S3ArtifactStorage:
    """S3-compatible distributed object storage (Backblaze B2 / Cloudflare R2 / AWS S3 / MinIO)."""

    def __init__(
        self,
        bucket_name: str,
        s3_client: Any,
        key_prefix: str = "",
    ) -> None:
        self.bucket = bucket_name.strip()
        if not self.bucket:
            raise StorageConfigurationError("S3/B2 bucket name cannot be empty")
        self.client = s3_client
        self.key_prefix = key_prefix.strip().strip("/")

    @classmethod
    def from_environment(cls) -> S3ArtifactStorage:
        import boto3
        from botocore.config import Config

        bucket = (
            os.getenv("VISIONGUARD_STORAGE_BUCKET", "").strip()
            or os.getenv("B2_BUCKET_NAME", "").strip()
        )
        if not bucket:
            raise StorageConfigurationError(
                "VISIONGUARD_STORAGE_BUCKET (or B2_BUCKET_NAME) environment variable is required for S3/B2 storage"
            )

        region = (
            os.getenv("VISIONGUARD_STORAGE_REGION", "").strip()
            or os.getenv("B2_REGION", "").strip()
            or "us-east-005"
        )

        endpoint_url = (
            os.getenv("VISIONGUARD_STORAGE_ENDPOINT", "").strip()
            or os.getenv("B2_ENDPOINT_URL", "").strip()
            or (f"https://s3.{region}.backblazeb2.com" if region and region != "auto" else None)
        )
        if endpoint_url and not endpoint_url.startswith("http://") and not endpoint_url.startswith("https://"):
            endpoint_url = f"https://{endpoint_url}"

        access_key = (
            os.getenv("VISIONGUARD_STORAGE_ACCESS_KEY_ID", "").strip()
            or os.getenv("B2_ACCESS_KEY_ID", "").strip()
        )
        secret_key = (
            os.getenv("VISIONGUARD_STORAGE_SECRET_ACCESS_KEY", "").strip()
            or os.getenv("B2_SECRET_ACCESS_KEY", "").strip()
        )

        if not access_key or not secret_key:
            raise StorageConfigurationError(
                "VISIONGUARD_STORAGE_ACCESS_KEY_ID and VISIONGUARD_STORAGE_SECRET_ACCESS_KEY "
                "(or B2_ACCESS_KEY_ID and B2_SECRET_ACCESS_KEY) are required"
            )

        # Standard Backblaze B2 / S3 client configuration with virtual-host addressing
        s3_config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
        )

        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=s3_config,
        )

        prefix = (
            os.getenv("VISIONGUARD_STORAGE_PREFIX", "").strip()
            or os.getenv("B2_PREFIX", "").strip()
        )
        return cls(bucket_name=bucket, s3_client=client, key_prefix=prefix)

    def _full_key(self, key: str) -> str:
        valid_key = validate_storage_key(key)
        if self.key_prefix:
            return f"{self.key_prefix}/{valid_key}"
        return valid_key

    def _strip_prefix(self, full_key: str) -> str:
        if self.key_prefix and full_key.startswith(f"{self.key_prefix}/"):
            return full_key[len(self.key_prefix) + 1 :]
        return full_key

    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        full_key = self._full_key(key)
        params: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": full_key,
            "Body": data,
            "ContentType": content_type,
        }
        if metadata:
            params["Metadata"] = metadata

        try:
            self.client.put_object(**params)
        except Exception as exc:
            logger.error("Failed to upload object '%s' to R2/S3 bucket '%s': %s", full_key, self.bucket, exc)
            raise

        return validate_storage_key(key)

    def get_object(self, key: str) -> tuple[bytes, str]:
        from botocore.exceptions import ClientError

        full_key = self._full_key(key)
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=full_key)
            content_type = resp.get("ContentType") or "application/octet-stream"
            body = resp["Body"].read()
            return body, content_type
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"NoSuchKey", "404"}:
                raise StorageObjectNotFoundError(f"Object not found in R2/S3: '{key}'") from exc
            logger.error("S3/R2 get_object error for key '%s': %s", full_key, exc)
            raise

    def head_object(self, key: str) -> dict[str, Any] | None:
        from botocore.exceptions import ClientError

        full_key = self._full_key(key)
        try:
            resp = self.client.head_object(Bucket=self.bucket, Key=full_key)
            return {
                "key": validate_storage_key(key),
                "size": resp.get("ContentLength", 0),
                "content_type": resp.get("ContentType", "application/octet-stream"),
                "last_modified": resp.get("LastModified"),
                "metadata": resp.get("Metadata", {}),
            }
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"NoSuchKey", "404"}:
                return None
            raise

    def delete_object(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        full_key = self._full_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=full_key)
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"NoSuchKey", "404"}:
                return False
            raise

    def list_objects(self, prefix: str = "") -> list[str]:
        full_prefix = self._full_key(prefix) if prefix else (f"{self.key_prefix}/" if self.key_prefix else "")
        results: list[str] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                key = obj.get("Key", "")
                results.append(self._strip_prefix(key))
        return sorted(results)

    def object_exists(self, key: str) -> bool:
        return self.head_object(key) is not None

    def generate_presigned_url(self, key: str, expires_in: int = 900) -> str:
        full_key = self._full_key(key)
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": full_key},
            ExpiresIn=expires_in,
        )
        return str(url)


def get_artifact_storage() -> ArtifactStorage:
    """Factory to get the configured storage backend based on environment."""
    backend = os.getenv("VISIONGUARD_STORAGE_BACKEND", "local").strip().lower()
    if backend in {"b2", "backblaze", "r2", "s3", "cloudflare"}:
        return S3ArtifactStorage.from_environment()
    return FileSystemArtifactStorage.from_environment()
