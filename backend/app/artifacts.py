"""Artifact resolution and retrieval service for VisionGuard evaluation runs.

Provides secure retrieval of original and corrupted image artifacts, strictly
enforcing dataset root boundaries and preventing path traversal.
"""
from __future__ import annotations

import io
import mimetypes
import os
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from backend.app.schemas import ArtifactItem
from backend.visionguard.core.corruptions import apply as apply_corruption
from backend.visionguard.core.pipeline import _DATASET_ROOTS, auto_register_default_datasets

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"


def get_artifacts_storage_dir() -> Path:
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


def list_run_artifacts(run_id: str, report_data: dict[str, Any]) -> list[ArtifactItem]:
    """List all available and planned artifacts for a run."""
    report = report_data.get("report", {})
    clean_preds = report.get("clean_predictions", [])
    conditions = report.get("conditions", [])

    artifacts: list[ArtifactItem] = []

    # 1. Baseline clean images
    for cp in clean_preds:
        image_id = cp.get("image_id", "")
        image_path = cp.get("image_path", "")
        mime, _ = mimetypes.guess_type(image_path)
        artifacts.append(
            ArtifactItem(
                artifact_id=f"clean_{image_id}",
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
            artifacts.append(
                ArtifactItem(
                    artifact_id=f"corrupted_{corruption}_{severity}_{image_id}",
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
        artifacts.append(
            ArtifactItem(
                artifact_id=f"overlay_{image_id}",
                run_id=run_id,
                image_id=image_id,
                artifact_type="overlay",
                mime_type="image/png",
                available=False,
                details="Detection overlay generation is not yet implemented. Overlays can be rendered client-side using prediction bounding boxes.",
            )
        )

    # 4. Shared storage artifacts persisted on disk by workers
    storage_dir = (get_artifacts_storage_dir() / run_id).resolve()
    if storage_dir.is_dir():
        existing_ids = {a.artifact_id for a in artifacts}
        for path in storage_dir.iterdir():
            if path.is_file():
                art_id = path.stem if path.suffix in ALLOWED_IMAGE_EXTENSIONS else path.name
                if art_id not in existing_ids:
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
) -> tuple[bytes, str]:
    """Retrieve artifact bytes and mime_type for a given run and artifact_id.

    Raises:
        ValueError for invalid artifact format.
        FileNotFoundError for missing artifacts.
        PermissionError for path traversal attempts or unauthorized access.
        NotImplementedError for unimplemented artifact types (e.g. overlays).
    """
    storage_dir = (get_artifacts_storage_dir() / run_id).resolve()
    if storage_dir.is_dir():
        for candidate_name in [artifact_id, f"{artifact_id}.jpg", f"{artifact_id}.png", f"{artifact_id}.webp", f"{artifact_id}.json"]:
            cand = (storage_dir / candidate_name).resolve()
            if cand.is_file() and cand.is_relative_to(storage_dir):
                mime, _ = mimetypes.guess_type(str(cand))
                return cand.read_bytes(), mime or "application/octet-stream"

    report = report_data.get("report", {})
    clean_preds = {cp.get("image_id"): cp for cp in report.get("clean_predictions", [])}

    if artifact_id.startswith("overlay_"):
        raise NotImplementedError(
            "Detection overlay generation is not yet implemented. "
            "Bounding box coordinates are provided in the report for frontend rendering."
        )

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
        parts = artifact_id.split("_", 3)
        if len(parts) != 4:
            raise ValueError(f"Invalid corrupted artifact ID format: '{artifact_id}'")
        _, corruption, severity_str, image_id = parts
        try:
            severity = int(severity_str)
        except ValueError:
            raise ValueError(f"Invalid severity in artifact ID: '{severity_str}'")

        cp = clean_preds.get(image_id)
        if not cp:
            raise FileNotFoundError(f"Image '{image_id}' not found in run '{run_id}'")

        # Verify condition is in report
        conditions = report.get("conditions", [])
        matched_condition = any(
            c.get("corruption") == corruption and c.get("severity") == severity
            for c in conditions
        )
        if not matched_condition:
            raise FileNotFoundError(
                f"Corruption condition '{corruption}' severity {severity} not found in run '{run_id}'"
            )

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
