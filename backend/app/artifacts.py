"""Artifact resolution and retrieval service for VisionGuard evaluation runs.

Provides secure resolution and storage of original, corrupted, and custom image artifacts.
Supports:
- Distributed S3/Cloudflare R2 object storage for distributed worker/API architecture.
- Local filesystem storage for development and testing.
- Safe dynamic generation fallback for local datasets.
"""
from __future__ import annotations

import io
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from backend.app.schemas import ArtifactItem
from backend.app.storage import (
    ArtifactStorage,
    StorageObjectNotFoundError,
    StorageSecurityError,
    get_artifact_storage,
    validate_storage_key,
)
from backend.visionguard.core.corruptions import apply as apply_corruption
from backend.visionguard.core.pipeline import _DATASET_ROOTS, auto_register_default_datasets

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"


def get_artifacts_storage_dir() -> Path:
    """Return configured local artifacts directory (for local filesystem mode)."""
    env_dir = os.environ.get("VISIONGUARD_ARTIFACTS_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    return DEFAULT_ARTIFACTS_DIR.resolve()


def _is_safe_dataset_path(candidate_path: Path) -> bool:
    """Validate that candidate_path resolves to an allowed image within registered dataset roots."""
    auto_register_default_datasets()
    try:
        resolved = candidate_path.resolve()
    except Exception:
        return False

    if resolved.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        return False

    for root in _DATASET_ROOTS.values():
        try:
            resolved_root = root.resolve()
            if resolved.is_relative_to(resolved_root):
                return True
        except Exception:
            continue
    return False


def list_run_artifacts(
    run_id: str,
    report_data: dict[str, Any],
    storage: ArtifactStorage | None = None,
    database: Any | None = None,
) -> list[ArtifactItem]:
    """List all available and planned artifacts for a run."""
    report = report_data.get("report", {})
    clean_preds = report.get("clean_predictions", [])
    conditions = report.get("conditions", [])

    artifacts: list[ArtifactItem] = []
    seen_ids: set[str] = set()

    # 1. Baseline clean images
    for cp in clean_preds:
        image_id = cp.get("image_id", "")
        image_path = cp.get("image_path", "")
        mime, _ = mimetypes.guess_type(image_path)
        art_id = f"clean_{image_id}"
        seen_ids.add(art_id)
        artifacts.append(
            ArtifactItem(
                artifact_id=art_id,
                run_id=run_id,
                image_id=image_id,
                artifact_type="original",
                mime_type=mime or "image/jpeg",
                available=True,
                details=f"Original baseline image for '{image_id}'",
            )
        )

    # 2. Corrupted condition images
    for cond in conditions:
        corruption = cond.get("corruption")
        severity = cond.get("severity")
        for pic in cond.get("per_image", []):
            image_id = pic.get("image_id", "")
            art_id = f"corrupted_{corruption}_{severity}_{image_id}"
            seen_ids.add(art_id)
            artifacts.append(
                ArtifactItem(
                    artifact_id=art_id,
                    run_id=run_id,
                    image_id=image_id,
                    artifact_type="corrupted",
                    corruption=corruption,
                    severity=severity,
                    mime_type="image/jpeg",
                    available=True,
                    details=f"Corrupted image for {corruption} (severity {severity}) on '{image_id}'",
                )
            )

    # 3. Detection overlays (marked explicitly as unavailable)
    for cp in clean_preds:
        image_id = cp.get("image_id", "")
        art_id = f"overlay_{image_id}"
        seen_ids.add(art_id)
        artifacts.append(
            ArtifactItem(
                artifact_id=art_id,
                run_id=run_id,
                image_id=image_id,
                artifact_type="overlay",
                mime_type="image/png",
                available=False,
                details="Detection overlay generation is not yet implemented. Overlays can be rendered client-side using prediction bounding boxes.",
            )
        )

    # 4. Storage backend discovery (persisted on disk or S3/B2/R2 by workers)
    resolved_storage = storage if storage is not None else get_artifact_storage()
    prefix = f"runs/{run_id}/"
    try:
        remote_keys = resolved_storage.list_objects(prefix=prefix)
        for key in remote_keys:
            # Strip run_id prefix
            filename = key[len(prefix) :]
            # Normalize stem / art_id
            name_part = Path(filename).name
            art_id = Path(name_part).stem if Path(name_part).suffix in ALLOWED_IMAGE_EXTENSIONS else name_part
            if art_id not in seen_ids:
                seen_ids.add(art_id)
                mime, _ = mimetypes.guess_type(filename)
                artifacts.append(
                    ArtifactItem(
                        artifact_id=art_id,
                        run_id=run_id,
                        image_id=art_id,
                        artifact_type="stored",
                        mime_type=mime or "application/octet-stream",
                        available=True,
                        details=f"Stored artifact '{filename}'",
                    )
                )
    except Exception as exc:
        logger.debug("Storage artifact discovery encountered an error for run %s: %s", run_id, exc)

    # 4b. Database metadata discovery
    if database is not None and hasattr(database, "list_artifacts_for_run"):
        try:
            db_arts = database.list_artifacts_for_run(run_id)
            for db_art in db_arts:
                art_id = db_art.get("artifact_id", "")
                if art_id and art_id not in seen_ids:
                    seen_ids.add(art_id)
                    artifacts.append(
                        ArtifactItem(
                            artifact_id=art_id,
                            run_id=run_id,
                            image_id=art_id,
                            artifact_type=db_art.get("artifact_type", "stored"),
                            mime_type=db_art.get("content_type") or "application/octet-stream",
                            available=True,
                            details=f"Database registered artifact '{db_art.get('file_name', art_id)}'",
                        )
                    )
        except Exception as db_exc:
            logger.debug("Database artifact discovery encountered an error for run %s: %s", run_id, db_exc)

    # 5. Local shared volume directory fallback
    storage_dir = (get_artifacts_storage_dir() / run_id).resolve()
    if storage_dir.is_dir():
        for path in storage_dir.iterdir():
            if path.is_file():
                art_id = path.stem if path.suffix in ALLOWED_IMAGE_EXTENSIONS else path.name
                if art_id not in seen_ids:
                    seen_ids.add(art_id)
                    mime, _ = mimetypes.guess_type(str(path))
                    artifacts.append(
                        ArtifactItem(
                            artifact_id=art_id,
                            run_id=run_id,
                            image_id=art_id,
                            artifact_type="stored",
                            mime_type=mime or "application/octet-stream",
                            available=True,
                            details=f"Stored artifact '{path.name}'",
                        )
                    )

    return artifacts


def get_artifact_content(
    run_id: str,
    artifact_id: str,
    report_data: dict[str, Any],
    storage: ArtifactStorage | None = None,
    database: Any | None = None,
) -> tuple[bytes, str]:
    """Retrieve artifact bytes and mime_type for a given run and artifact_id.

    Resolution order:
    1. Query database for registered object_key and retrieve from storage.
    2. Query persistent object storage by candidate keys (S3/B2/R2 or configured filesystem).
    3. Query local shared directory on disk.
    4. Fallback to clean dataset image or deterministic dynamic corruption generation.
    """
    if artifact_id.startswith("overlay_"):
        raise NotImplementedError(
            "Detection overlay generation is not yet implemented. "
            "Bounding box coordinates are provided in the report for frontend rendering."
        )

    resolved_storage = storage if storage is not None else get_artifact_storage()

    # 1. Query database record if available
    if database is not None and hasattr(database, "get_artifact"):
        try:
            art_record = database.get_artifact(run_id, artifact_id)
            if art_record and art_record.get("object_key"):
                try:
                    data, mime = resolved_storage.get_object(art_record["object_key"])
                    return data, mime
                except StorageObjectNotFoundError:
                    pass
        except Exception as db_lookup_exc:
            logger.debug("Database artifact lookup error for %s/%s: %s", run_id, artifact_id, db_lookup_exc)

    # 2. Try resolving through storage backend candidate keys
    candidates = [
        f"runs/{run_id}/{artifact_id}",
        f"runs/{run_id}/{artifact_id}.jpg",
        f"runs/{run_id}/{artifact_id}.png",
        f"runs/{run_id}/{artifact_id}.webp",
        f"runs/{run_id}/{artifact_id}.json",
    ]
    if artifact_id.startswith("clean_"):
        candidates.append(f"runs/{run_id}/clean/{artifact_id[len('clean_'):]}.jpg")
        candidates.append(f"runs/{run_id}/clean_{artifact_id[len('clean_'):]}.jpg")
    elif artifact_id.startswith("corrupted_"):
        candidates.append(f"runs/{run_id}/corrupted/{artifact_id[len('corrupted_'):]}.jpg")

    for cand_key in candidates:
        try:
            data, mime = resolved_storage.get_object(cand_key)
            return data, mime
        except StorageObjectNotFoundError:
            continue
        except StorageSecurityError as exc:
            raise PermissionError(str(exc)) from exc
        except Exception as exc:
            logger.debug("Failed checking storage key '%s': %s", cand_key, exc)


    # 2. Try resolving through local artifacts directory
    storage_dir = (get_artifacts_storage_dir() / run_id).resolve()
    if storage_dir.is_dir():
        for candidate_name in [artifact_id, f"{artifact_id}.jpg", f"{artifact_id}.png", f"{artifact_id}.webp", f"{artifact_id}.json"]:
            cand = (storage_dir / candidate_name).resolve()
            if cand.is_file() and cand.is_relative_to(storage_dir):
                mime, _ = mimetypes.guess_type(str(cand))
                return cand.read_bytes(), mime or "application/octet-stream"

    # 3. Two-tier fallback for local datasets or backward-compatibility
    report = report_data.get("report", {})
    clean_preds = {cp.get("image_id"): cp for cp in report.get("clean_predictions", [])}

    if artifact_id.startswith("clean_"):
        image_id = artifact_id[len("clean_") :]
        cp = clean_preds.get(image_id)
        if not cp:
            raise FileNotFoundError(f"Original image '{image_id}' not found in run '{run_id}'")
        raw_path = Path(cp.get("image_path", ""))
        if not _is_safe_dataset_path(raw_path) or not raw_path.is_file():
            raise PermissionError("Access denied: path is not within registered dataset directories")
        mime, _ = mimetypes.guess_type(str(raw_path))
        return raw_path.read_bytes(), mime or "image/jpeg"

    if artifact_id.startswith("corrupted_"):
        conditions = report.get("conditions", [])
        matched = None
        for cond in conditions:
            c_name = cond.get("corruption")
            c_sev = cond.get("severity")
            prefix = f"corrupted_{c_name}_{c_sev}_"
            if artifact_id.startswith(prefix):
                matched = (c_name, c_sev, artifact_id[len(prefix) :])
                break

        if not matched:
            raise FileNotFoundError(
                f"Corruption condition matching artifact '{artifact_id}' not found in run '{run_id}'"
            )

        corruption, severity, image_id = matched
        cp = clean_preds.get(image_id)
        if not cp:
            raise FileNotFoundError(f"Image '{image_id}' not found in run '{run_id}'")

        raw_path = Path(cp.get("image_path", ""))
        if not _is_safe_dataset_path(raw_path) or not raw_path.is_file():
            raise PermissionError("Access denied: path is not within registered dataset directories")

        # Load clean image
        img_pil = Image.open(raw_path).convert("RGB")
        img_rgb = np.array(img_pil)

        # Apply deterministic corruption
        seed = report.get("config", {}).get("seed", 42)
        corr_rgb = apply_corruption(img_rgb, corruption, severity, seed=seed)

        # Encode as JPEG
        buf = io.BytesIO()
        Image.fromarray(corr_rgb).save(buf, format="JPEG", quality=90)
        return buf.getvalue(), "image/jpeg"

    raise FileNotFoundError(f"Unrecognized artifact ID '{artifact_id}' for run '{run_id}'")


def upload_run_artifacts(
    run_id: str,
    report: dict[str, Any],
    storage: ArtifactStorage | None = None,
    database: Any | None = None,
) -> list[str]:
    """Upload evaluation artifacts (clean, corrupted, and custom) to storage.

    Called by the worker after evaluation completes.
    Persists artifact metadata records into the database if database is provided.
    Failure to upload an individual artifact logs a warning and continues,
    ensuring that evaluation report persistence is never blocked by transient storage blips.
    """
    resolved_storage = storage if storage is not None else get_artifact_storage()
    uploaded_keys: list[str] = []

    clean_preds = {cp.get("image_id"): cp for cp in report.get("clean_predictions", [])}

    # 1. Upload clean baseline images
    for image_id, cp in clean_preds.items():
        raw_path = Path(cp.get("image_path", ""))
        if raw_path.is_file():
            key = f"runs/{run_id}/clean_{image_id}.jpg"
            art_id = f"clean_{image_id}"
            try:
                data = raw_path.read_bytes()
                resolved_storage.put_object(
                    key,
                    data,
                    content_type="image/jpeg",
                    metadata={"run_id": run_id, "image_id": image_id, "type": "clean"},
                )
                uploaded_keys.append(key)
                if database is not None and hasattr(database, "record_artifact"):
                    try:
                        database.record_artifact(
                            run_id=run_id,
                            artifact_id=art_id,
                            artifact_type="original",
                            file_name=f"{art_id}.jpg",
                            object_key=key,
                            content_type="image/jpeg",
                            size_bytes=len(data),
                        )
                    except Exception as db_exc:
                        logger.warning("Failed to record artifact metadata for %s: %s", art_id, db_exc)
            except Exception as exc:
                logger.warning("Failed to upload clean artifact '%s' for run %s: %s", key, run_id, exc)

    # 2. Upload corrupted images
    conditions = report.get("conditions", [])
    seed = report.get("config", {}).get("seed", 42)

    for cond in conditions:
        corruption = cond.get("corruption")
        severity = cond.get("severity")
        for pic in cond.get("per_image", []):
            image_id = pic.get("image_id", "")
            cp = clean_preds.get(image_id)
            if not cp:
                continue
            raw_path = Path(cp.get("image_path", ""))
            if not raw_path.is_file():
                continue

            art_id = f"corrupted_{corruption}_{severity}_{image_id}"
            key = f"runs/{run_id}/{art_id}.jpg"
            try:
                img_pil = Image.open(raw_path).convert("RGB")
                img_rgb = np.array(img_pil)
                corr_rgb = apply_corruption(img_rgb, corruption, severity, seed=seed)

                buf = io.BytesIO()
                Image.fromarray(corr_rgb).save(buf, format="JPEG", quality=90)
                corr_bytes = buf.getvalue()

                resolved_storage.put_object(
                    key,
                    corr_bytes,
                    content_type="image/jpeg",
                    metadata={
                        "run_id": run_id,
                        "image_id": image_id,
                        "corruption": corruption,
                        "severity": str(severity),
                        "type": "corrupted",
                    },
                )
                uploaded_keys.append(key)
                if database is not None and hasattr(database, "record_artifact"):
                    try:
                        database.record_artifact(
                            run_id=run_id,
                            artifact_id=art_id,
                            artifact_type="corrupted",
                            file_name=f"{art_id}.jpg",
                            object_key=key,
                            content_type="image/jpeg",
                            size_bytes=len(corr_bytes),
                        )
                    except Exception as db_exc:
                        logger.warning("Failed to record artifact metadata for %s: %s", art_id, db_exc)
            except Exception as exc:
                logger.warning("Failed to upload corrupted artifact '%s' for run %s: %s", key, run_id, exc)

    # 3. Upload any custom local files in local storage directory
    local_dir = (get_artifacts_storage_dir() / run_id).resolve()
    if local_dir.is_dir():
        for path in local_dir.iterdir():
            if path.is_file():
                key = f"runs/{run_id}/{path.name}"
                mime, _ = mimetypes.guess_type(str(path))
                try:
                    f_bytes = path.read_bytes()
                    resolved_storage.put_object(
                        key,
                        f_bytes,
                        content_type=mime or "application/octet-stream",
                        metadata={"run_id": run_id, "type": "custom"},
                    )
                    uploaded_keys.append(key)
                    if database is not None and hasattr(database, "record_artifact"):
                        try:
                            database.record_artifact(
                                run_id=run_id,
                                artifact_id=path.stem,
                                artifact_type="custom",
                                file_name=path.name,
                                object_key=key,
                                content_type=mime or "application/octet-stream",
                                size_bytes=len(f_bytes),
                            )
                        except Exception as db_exc:
                            logger.warning("Failed to record artifact metadata for %s: %s", path.name, db_exc)
                except Exception as exc:
                    logger.warning("Failed to upload custom artifact '%s': %s", key, exc)

    logger.info("Uploaded %d artifacts for run %s to storage", len(uploaded_keys), run_id)
    return uploaded_keys
