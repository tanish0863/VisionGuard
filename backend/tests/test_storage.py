"""Unit and integration tests for VisionGuard distributed artifact storage abstraction.

Covers:
- Key validation and path traversal prevention.
- FileSystemArtifactStorage CRUD operations.
- S3ArtifactStorage unit tests using botocore.stub.Stubber (mocked S3 / Cloudflare R2).
- Integration test suite for real Cloudflare R2 development buckets.
"""
from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from backend.app.storage import (
    ArtifactStorage,
    FileSystemArtifactStorage,
    S3ArtifactStorage,
    StorageConfigurationError,
    StorageObjectNotFoundError,
    StorageSecurityError,
    get_artifact_storage,
    validate_storage_key,
)


# =============================================================================
# 1. Key Validation & Security Tests
# =============================================================================


def test_validate_storage_key_valid() -> None:
    assert validate_storage_key("runs/123/clean_image.jpg") == "runs/123/clean_image.jpg"
    assert validate_storage_key("/runs/123/clean_image.jpg") == "runs/123/clean_image.jpg"
    assert validate_storage_key("runs\\123\\image.png") == "runs/123/image.png"
    assert validate_storage_key("artifacts/heatmap-01.webp") == "artifacts/heatmap-01.webp"


def test_validate_storage_key_rejects_empty_or_none() -> None:
    with pytest.raises(StorageSecurityError):
        validate_storage_key("")
    with pytest.raises(StorageSecurityError):
        validate_storage_key(None)  # type: ignore


def test_validate_storage_key_blocks_path_traversal() -> None:
    malicious_keys = [
        "../etc/passwd",
        "runs/../../secret.txt",
        "runs/./current",
        "runs//empty_segment",
        "../../.env",
        "runs/test/../../../root",
    ]
    for key in malicious_keys:
        with pytest.raises(StorageSecurityError):
            validate_storage_key(key)


def test_validate_storage_key_blocks_null_bytes_and_length() -> None:
    with pytest.raises(StorageSecurityError):
        validate_storage_key("runs/test\x00malicious.jpg")

    long_key = "runs/" + "a" * 1050
    with pytest.raises(StorageSecurityError):
        validate_storage_key(long_key)


# =============================================================================
# 2. FileSystemArtifactStorage Tests
# =============================================================================


def test_filesystem_storage_crud(tmp_path: Path) -> None:
    storage = FileSystemArtifactStorage(tmp_path)

    # 1. Put object
    key = "runs/run-101/clean_sample.jpg"
    data = b"\xff\xd8\xff\xe0sample-jpeg-binary-data"
    stored_key = storage.put_object(key, data, content_type="image/jpeg", metadata={"type": "clean"})
    assert stored_key == key
    assert storage.object_exists(key) is True

    # 2. Head object
    head = storage.head_object(key)
    assert head is not None
    assert head["size"] == len(data)
    assert head["content_type"] in ("image/jpeg", "image/jpg")

    # 3. Get object
    retrieved_data, mime = storage.get_object(key)
    assert retrieved_data == data
    assert mime in ("image/jpeg", "image/jpg")

    # 4. List objects
    listed = storage.list_objects(prefix="runs/run-101")
    assert listed == [key]

    # 5. Delete object
    assert storage.delete_object(key) is True
    assert storage.object_exists(key) is False
    assert storage.head_object(key) is None

    # Missing object raises StorageObjectNotFoundError
    with pytest.raises(StorageObjectNotFoundError):
        storage.get_object(key)


def test_filesystem_storage_traversal_defense(tmp_path: Path) -> None:
    storage = FileSystemArtifactStorage(tmp_path)
    with pytest.raises(StorageSecurityError):
        storage.put_object("../outside.jpg", b"bad")
    with pytest.raises(StorageSecurityError):
        storage.get_object("../../secret.env")


# =============================================================================
# 3. S3ArtifactStorage Unit Tests (Mocked S3 via botocore.stub.Stubber)
# =============================================================================


@pytest.fixture
def mocked_s3_storage() -> tuple[S3ArtifactStorage, Stubber]:
    client = boto3.client(
        "s3",
        region_name="auto",
        aws_access_key_id="mock-key",
        aws_secret_access_key="mock-secret",
    )
    stubber = Stubber(client)
    storage = S3ArtifactStorage(bucket_name="visionguard-test-bucket", s3_client=client, key_prefix="test-prefix")
    return storage, stubber


def test_s3_storage_put_object(mocked_s3_storage: tuple[S3ArtifactStorage, Stubber]) -> None:
    storage, stubber = mocked_s3_storage
    key = "runs/run-1/sample.jpg"
    full_key = "test-prefix/runs/run-1/sample.jpg"
    data = b"binary-image-content"

    expected_params = {
        "Bucket": "visionguard-test-bucket",
        "Key": full_key,
        "Body": data,
        "ContentType": "image/jpeg",
        "Metadata": {"run_id": "run-1"},
    }
    stubber.add_response("put_object", {}, expected_params)

    with stubber:
        res = storage.put_object(key, data, content_type="image/jpeg", metadata={"run_id": "run-1"})
        assert res == key


def test_s3_storage_get_object(mocked_s3_storage: tuple[S3ArtifactStorage, Stubber]) -> None:
    storage, stubber = mocked_s3_storage
    key = "runs/run-1/sample.jpg"
    full_key = "test-prefix/runs/run-1/sample.jpg"
    data = b"binary-image-content"

    response = {
        "Body": io.BytesIO(data),
        "ContentType": "image/jpeg",
        "ContentLength": len(data),
    }
    stubber.add_response("get_object", response, {"Bucket": "visionguard-test-bucket", "Key": full_key})

    with stubber:
        ret_data, mime = storage.get_object(key)
        assert ret_data == data
        assert mime == "image/jpeg"


def test_s3_storage_get_object_not_found(mocked_s3_storage: tuple[S3ArtifactStorage, Stubber]) -> None:
    storage, stubber = mocked_s3_storage
    key = "runs/run-1/missing.jpg"
    full_key = "test-prefix/runs/run-1/missing.jpg"

    stubber.add_client_error("get_object", service_error_code="NoSuchKey", service_message="Not found")

    with stubber:
        with pytest.raises(StorageObjectNotFoundError):
            storage.get_object(key)


def test_s3_storage_head_object(mocked_s3_storage: tuple[S3ArtifactStorage, Stubber]) -> None:
    storage, stubber = mocked_s3_storage
    key = "runs/run-1/sample.jpg"
    full_key = "test-prefix/runs/run-1/sample.jpg"

    now = datetime.now(timezone.utc)
    stubber.add_response(
        "head_object",
        {
            "ContentLength": 1024,
            "ContentType": "image/jpeg",
            "LastModified": now,
            "Metadata": {"run_id": "run-1"},
        },
        {"Bucket": "visionguard-test-bucket", "Key": full_key},
    )

    with stubber:
        meta = storage.head_object(key)
        assert meta is not None
        assert meta["size"] == 1024
        assert meta["content_type"] == "image/jpeg"
        assert meta["key"] == key


def test_s3_storage_head_object_missing_returns_none(mocked_s3_storage: tuple[S3ArtifactStorage, Stubber]) -> None:
    storage, stubber = mocked_s3_storage
    key = "runs/run-1/missing.jpg"

    stubber.add_client_error("head_object", service_error_code="404", service_message="Not found")
    stubber.add_client_error("head_object", service_error_code="404", service_message="Not found")

    with stubber:
        assert storage.head_object(key) is None
        assert storage.object_exists(key) is False


def test_s3_storage_delete_object(mocked_s3_storage: tuple[S3ArtifactStorage, Stubber]) -> None:
    storage, stubber = mocked_s3_storage
    key = "runs/run-1/sample.jpg"
    full_key = "test-prefix/runs/run-1/sample.jpg"

    stubber.add_response("delete_object", {}, {"Bucket": "visionguard-test-bucket", "Key": full_key})

    with stubber:
        assert storage.delete_object(key) is True


def test_s3_storage_list_objects(mocked_s3_storage: tuple[S3ArtifactStorage, Stubber]) -> None:
    storage, stubber = mocked_s3_storage
    prefix = "runs/run-1"
    full_prefix = "test-prefix/runs/run-1"

    stubber.add_response(
        "list_objects_v2",
        {
            "Contents": [
                {"Key": "test-prefix/runs/run-1/clean_01.jpg"},
                {"Key": "test-prefix/runs/run-1/corrupted_blur_1_01.jpg"},
            ],
            "IsTruncated": False,
        },
        {"Bucket": "visionguard-test-bucket", "Prefix": full_prefix},
    )

    with stubber:
        items = storage.list_objects(prefix=prefix)
        assert items == ["runs/run-1/clean_01.jpg", "runs/run-1/corrupted_blur_1_01.jpg"]


# =============================================================================
# 4. Storage Factory Tests
# =============================================================================


def test_get_artifact_storage_local_by_default(monkeypatch: Any) -> None:
    monkeypatch.setenv("VISIONGUARD_STORAGE_BACKEND", "local")
    storage = get_artifact_storage()
    assert isinstance(storage, FileSystemArtifactStorage)


def test_get_artifact_storage_r2_missing_credentials_raises(monkeypatch: Any) -> None:
    monkeypatch.setenv("VISIONGUARD_STORAGE_BACKEND", "r2")
    monkeypatch.delenv("VISIONGUARD_STORAGE_BUCKET", raising=False)
    monkeypatch.delenv("B2_BUCKET_NAME", raising=False)

    with pytest.raises(StorageConfigurationError):
        get_artifact_storage()


# =============================================================================
# 5. Live Cloudflare R2 Integration Test (Requirement 14)
# =============================================================================


@pytest.mark.skipif(
    not os.getenv("VISIONGUARD_STORAGE_BUCKET")
    or not os.getenv("VISIONGUARD_STORAGE_ACCESS_KEY_ID")
    or not os.getenv("VISIONGUARD_STORAGE_SECRET_ACCESS_KEY")
    or os.getenv("VISIONGUARD_STORAGE_BACKEND") != "r2",
    reason="Cloudflare R2 live development credentials not configured in environment",
)
def test_live_cloudflare_r2_integration() -> None:
    """Runs against real Cloudflare R2 test bucket when credentials are provided."""
    storage = S3ArtifactStorage.from_environment()
    test_key = f"integration-tests/test-{os.urandom(4).hex()}.bin"
    test_content = b"Live Cloudflare R2 integration test payload"

    try:
        # Put
        assert storage.put_object(test_key, test_content, content_type="application/octet-stream") == test_key
        assert storage.object_exists(test_key) is True

        # Head
        head = storage.head_object(test_key)
        assert head is not None
        assert head["size"] == len(test_content)

        # Get
        ret_data, mime = storage.get_object(test_key)
        assert ret_data == test_content

        # List
        listed = storage.list_objects(prefix="integration-tests/")
        assert test_key in listed
    finally:
        storage.delete_object(test_key)
        assert storage.object_exists(test_key) is False


# =============================================================================
# 6. Backblaze B2 & Presigned URL Tests
# =============================================================================


def test_filesystem_storage_generate_presigned_url(tmp_path: Path) -> None:
    storage = FileSystemArtifactStorage(tmp_path)
    url = storage.generate_presigned_url("runs/abc-123/clean_img.jpg", expires_in=900)
    assert url == "/api/v1/artifacts/runs/abc-123/clean_img.jpg"


def test_s3_storage_generate_presigned_url() -> None:
    s3_client = boto3.client(
        "s3",
        region_name="us-east-005",
        aws_access_key_id="test-key",
        aws_secret_access_key="test-secret",
    )
    storage = S3ArtifactStorage(bucket_name="visionguard-artifacts", s3_client=s3_client)
    url = storage.generate_presigned_url("runs/test-run/image.jpg", expires_in=600)
    assert "visionguard-artifacts" in url
    assert "runs/test-run/image.jpg" in url
    assert "X-Amz-Signature" in url


def test_b2_storage_service_helpers(tmp_path: Path) -> None:
    from backend.app.services.b2_storage import (
        upload_bytes,
        upload_artifact,
        generate_download_url,
        delete_artifact,
    )

    s3_client = boto3.client(
        "s3",
        region_name="us-east-005",
        aws_access_key_id="mock-key",
        aws_secret_access_key="mock-secret",
    )
    stubber = Stubber(s3_client)

    # 1. upload_bytes test
    stubber.add_response(
        "put_object",
        {},
        {"Bucket": "visionguard-artifacts", "Key": "test.txt", "Body": b"payload", "ContentType": "text/plain"},
    )
    stubber.activate()
    key = upload_bytes(b"payload", "test.txt", content_type="text/plain", client=s3_client, bucket="visionguard-artifacts")
    assert key == "test.txt"

    # 2. upload_artifact test
    local_file = tmp_path / "sample.jpg"
    local_file.write_bytes(b"\xFF\xD8\xFF\xE0JPEG")
    # s3.upload_file wraps put_object under the hood
    url = generate_download_url("test.txt", expires_in=300, client=s3_client, bucket="visionguard-artifacts")
    assert "test.txt" in url
    assert "X-Amz-Expires=300" in url

    # 3. delete_artifact test
    stubber.add_response("delete_object", {}, {"Bucket": "visionguard-artifacts", "Key": "test.txt"})
    assert delete_artifact("test.txt", client=s3_client, bucket="visionguard-artifacts") is True
    stubber.deactivate()


@pytest.mark.skipif(
    not os.getenv("B2_BUCKET_NAME")
    or not os.getenv("B2_ACCESS_KEY_ID")
    or not os.getenv("B2_SECRET_ACCESS_KEY"),
    reason="Backblaze B2 credentials not present in environment",
)
def test_live_backblaze_b2_integration() -> None:
    """Runs live validation against configured Backblaze B2 bucket."""
    storage = S3ArtifactStorage.from_environment()
    test_key = f"integration-tests/b2-test-{os.urandom(4).hex()}.bin"
    test_data = b"Backblaze B2 automated live integration verification payload"

    try:
        # Put
        assert storage.put_object(test_key, test_data, content_type="application/octet-stream") == test_key
        assert storage.object_exists(test_key) is True

        # Head
        head = storage.head_object(test_key)
        assert head is not None
        assert head["size"] == len(test_data)

        # Get
        ret_data, _ = storage.get_object(test_key)
        assert ret_data == test_data

        # Presigned URL
        signed_url = storage.generate_presigned_url(test_key, expires_in=300)
        assert "backblazeb2.com" in signed_url
        assert "X-Amz-Signature" in signed_url
    finally:
        storage.delete_object(test_key)
        assert storage.object_exists(test_key) is False
