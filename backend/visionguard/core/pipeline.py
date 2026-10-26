"""VisionGuard – pipeline.py

Orchestrates the complete evaluation loop.

Public API
----------
>>> from visionguard.core.pipeline import evaluate_run
>>> report = evaluate_run(config, progress_callback=lambda done, total: ...)

Steps performed
---------------
1.  Validate ``EvalConfig`` (raises ``pydantic.ValidationError`` on bad input).
2.  Load the detector via ``model_adapter.TorchvisionDetector``.
3.  Load dataset images from the path registered in ``DATASET_ROOTS``.
4.  Run clean inference on every image; cache results.
5.  For every (corruption kind × severity) combination in ``config.corruptions``:
    a. Apply the corruption.
    b. Run inference on the corrupted image.
    c. Match clean ↔ corrupted predictions.
    d. Compute per-image metrics.
    e. Record per-image failures (MISSING, NEW, CLASS_FLIP).
6.  Pool per-image metrics → condition-level ``MetricSet``.
7.  Assemble and return ``EvaluationReport``.

Error-handling contract
-----------------------
- A single failed image produces an ``ImageError`` entry and does NOT abort
  the whole run.
- If EVERY image fails in a condition, the condition still appears in the
  report with n_clean=n_corrupted=n_matched=0.
- Run status:
    COMPLETED  – no errors at all.
    PARTIAL    – at least one error, but at least one image succeeded.
    FAILED     – every image failed (zero usable data).

Dataset registration
--------------------
Register your dataset root with ``register_dataset``:

    from visionguard.core.pipeline import register_dataset
    register_dataset("my_dataset", Path("/data/my_dataset"))

Images inside the root are discovered by ``_load_image_paths``.  Supported
extensions: .jpg .jpeg .png .bmp .webp.

Dataset interface
-----------------
The pipeline expects a directory layout where each image file is a
self-contained sample.  Ground-truth labels are not required and are not
read.  If you have COCO-format annotations, wire them up separately and set
``has_ground_truth=True`` on ``DatasetInfo``.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import logging
import platform
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Union

import cv2
import numpy as np

from visionguard_contracts.visionguard.core.types import (  # type: ignore
    ConditionResult,
    CorruptionKind,
    DatasetInfo,
    EvalConfig,
    EvaluationReport,
    FailureInfo,
    FailureType,
    ImageConditionResult,
    ImageError,
    ImagePredictions,
    MatchRecord as ContractMatchRecord,
    MetricSet,
    ModelInfo,
    Prediction,
    RunStatus,
    LIMITATIONS,
    METRIC_DEFINITIONS,
    SCHEMA_VERSION,
)

from .corruptions import apply as apply_corruption, CORRUPTION_PARAMS
from .matching import match as match_predictions, MatchRecord
from .metrics import compute_metrics, aggregate_condition
from .model_adapter import DetectorAdapter, FakeDetector, TorchvisionDetector

log = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]  # (completed, total)

# --------------------------------------------------------------------------- #
# Dataset registry                                                              #
# --------------------------------------------------------------------------- #

_DATASET_ROOTS: dict[str, Path] = {}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

DEFAULT_DEMO_DATASET_ID = "visionguard_demo"
DEFAULT_DEMO_DIR = (
    Path(__file__).resolve().parents[2] / "demo_data" / DEFAULT_DEMO_DATASET_ID
)


def register_dataset(dataset_id: str, root: Path) -> None:
    """Register a dataset root directory by ID.

    Parameters
    ----------
    dataset_id:
        The ``dataset_id`` string used in ``EvalConfig``.
    root:
        Absolute path to the directory containing image files.
    """
    _DATASET_ROOTS[dataset_id] = Path(root)
    log.info("Registered dataset '%s' at %s", dataset_id, root)


def auto_register_default_datasets() -> None:
    """Automatically register bundled default datasets if present on disk
    and not already registered. Never overwrites an already registered path.
    """
    if DEFAULT_DEMO_DATASET_ID not in _DATASET_ROOTS:
        if DEFAULT_DEMO_DIR.is_dir():
            register_dataset(DEFAULT_DEMO_DATASET_ID, DEFAULT_DEMO_DIR)


# Register bundled default datasets if present at import time
auto_register_default_datasets()


def get_registered_datasets() -> list[dict[str, Any]]:
    """Return metadata for all currently registered datasets."""
    auto_register_default_datasets()
    result: list[dict[str, Any]] = []
    for d_id in sorted(_DATASET_ROOTS):
        root = _DATASET_ROOTS[d_id]
        if root.is_dir():
            image_paths = sorted(
                p for p in root.rglob("*") if p.suffix.lower() in _IMAGE_EXTENSIONS
            )
            count = len(image_paths)
            supported = count > 0
        else:
            count = 0
            supported = False

        name = d_id.replace("_", " ").title()
        if d_id == DEFAULT_DEMO_DATASET_ID:
            name = "VisionGuard Demo Dataset"
            desc = "Bundled benchmark demo dataset with diverse outdoor and indoor scenes"
        else:
            desc = f"Registered dataset at {root.as_posix()}"

        result.append(
            {
                "id": d_id,
                "name": name,
                "description": desc,
                "image_count": count,
                "has_ground_truth": False,
                "supported": supported,
            }
        )
    return result



# --------------------------------------------------------------------------- #
# Model registry                                                                #
# --------------------------------------------------------------------------- #

def _build_detector(config: EvalConfig) -> DetectorAdapter:
    """Construct a DetectorAdapter from ``config.model_id``."""
    if config.model_id in TorchvisionDetector._SUPPORTED:
        return TorchvisionDetector(
            model_id=config.model_id,
            score_threshold=config.score_threshold,
            nms_iou_threshold=0.5,  # default; recorded in report via detector.nms_settings
        )
    raise ValueError(
        f"Unknown model_id '{config.model_id}'. "
        f"Supported: {list(TorchvisionDetector._SUPPORTED)}. "
        "Register additional detectors via a custom adapter."
    )


# --------------------------------------------------------------------------- #
# Image loading                                                                 #
# --------------------------------------------------------------------------- #

def _load_image_paths(dataset_id: str, max_images: Optional[int]) -> list[Path]:
    """Return sorted image paths for ``dataset_id``."""
    if dataset_id not in _DATASET_ROOTS:
        auto_register_default_datasets()

    if dataset_id not in _DATASET_ROOTS:
        raise FileNotFoundError(
            f"Dataset '{dataset_id}' is not registered. "
            "Call pipeline.register_dataset(dataset_id, root_path) first."
        )
    root = _DATASET_ROOTS[dataset_id]
    paths = sorted(
        p for p in root.rglob("*") if p.suffix.lower() in _IMAGE_EXTENSIONS
    )
    if not paths:
        raise FileNotFoundError(
            f"No images found in '{root}'. "
            f"Supported extensions: {_IMAGE_EXTENSIONS}"
        )
    if max_images is not None:
        paths = paths[:max_images]
    return paths


def _read_rgb(path: Path) -> np.ndarray:
    """Read an image file and return an H×W×3 uint8 RGB array."""
    bgr = cv2.imread(str(path))
    if bgr is None:
        raise OSError(f"cv2.imread returned None for '{path}'")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


# --------------------------------------------------------------------------- #
# Prediction conversion                                                         #
# --------------------------------------------------------------------------- #

def _to_contract_predictions(
    raw: list[dict],
    image_width: int,
    image_height: int,
) -> list[Prediction]:
    """Convert adapter dicts to validated ``Prediction`` contract objects.

    Clamps boxes to image dimensions (handles occasional floating-point drift
    from the detector before Pydantic validates the strict bounds).
    """
    result = []
    for p in raw:
        x1, y1, x2, y2 = p["bbox_xyxy"]
        x1 = max(0.0, float(x1))
        y1 = max(0.0, float(y1))
        x2 = min(float(image_width), float(x2))
        y2 = min(float(image_height), float(y2))
        if x2 <= x1 or y2 <= y1:
            log.debug("Skipping degenerate box [%.1f,%.1f,%.1f,%.1f]", x1, y1, x2, y2)
            continue
        result.append(
            Prediction(
                class_id=int(p["class_id"]),
                class_name=str(p["class_name"]),
                confidence=float(p["confidence"]),
                bbox_xyxy=[x1, y1, x2, y2],
            )
        )
    return result


def _to_contract_match_records(matches: list[MatchRecord]) -> list[ContractMatchRecord]:
    """Convert local ``MatchRecord`` dataclasses to contract objects."""
    return [
        ContractMatchRecord(
            clean_index=m.clean_index,
            corrupted_index=m.corrupted_index,
            iou=m.iou,
            confidence_delta=m.confidence_delta,
            class_flip=m.class_flip,
        )
        for m in matches
    ]


# --------------------------------------------------------------------------- #
# Failure classification                                                        #
# --------------------------------------------------------------------------- #

def _record_failures(
    image_id: str,
    corruption: CorruptionKind,
    severity: int,
    clean_preds: list[Prediction],
    corrupted_preds: list[Prediction],
    matches: list[ContractMatchRecord],
    unmatched_clean: list[int],
    unmatched_corrupted: list[int],
    failures: list[FailureInfo],
) -> None:
    """Classify and append failures for one image/condition pair."""
    for ci in unmatched_clean:
        failures.append(FailureInfo(
            image_id=image_id,
            corruption=corruption,
            severity=severity,
            failure_type=FailureType.MISSING_AFTER_CORRUPTION,
            clean_index=ci,
            clean_prediction=clean_preds[ci],
            details=(
                f"clean '{clean_preds[ci].class_name}' "
                f"(conf={clean_preds[ci].confidence:.2f}) has no counterpart "
                "in the corrupted image"
            ),
        ))

    for ki in unmatched_corrupted:
        failures.append(FailureInfo(
            image_id=image_id,
            corruption=corruption,
            severity=severity,
            failure_type=FailureType.NEW_AFTER_CORRUPTION,
            corrupted_index=ki,
            corrupted_prediction=corrupted_preds[ki],
            details=(
                f"corrupted '{corrupted_preds[ki].class_name}' "
                f"(conf={corrupted_preds[ki].confidence:.2f}) has no clean counterpart"
            ),
        ))

    for m in matches:
        if m.class_flip:
            cp = clean_preds[m.clean_index]
            kp = corrupted_preds[m.corrupted_index]
            failures.append(FailureInfo(
                image_id=image_id,
                corruption=corruption,
                severity=severity,
                failure_type=FailureType.CLASS_FLIP,
                clean_index=m.clean_index,
                corrupted_index=m.corrupted_index,
                clean_prediction=cp,
                corrupted_prediction=kp,
                iou=m.iou,
                details=(
                    f"'{cp.class_name}' became '{kp.class_name}' "
                    f"(IoU={m.iou:.3f}, Δconf={m.confidence_delta:+.3f})"
                ),
            ))


# --------------------------------------------------------------------------- #
# Software version snapshot                                                     #
# --------------------------------------------------------------------------- #

def _software_versions() -> dict[str, str]:
    versions: dict[str, str] = {"python": platform.python_version()}
    for pkg in ("numpy", "scipy", "opencv-python", "torch", "torchvision", "pydantic"):
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            pass
    # opencv may be installed under a different dist name
    if "opencv-python" not in versions:
        try:
            versions["opencv-python"] = importlib.metadata.version("opencv-python-headless")
        except importlib.metadata.PackageNotFoundError:
            versions["opencv-python"] = cv2.__version__
    return versions


# --------------------------------------------------------------------------- #
# SHA-256 of model weights file                                                 #
# --------------------------------------------------------------------------- #

def _sha256_of_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Main entry point                                                              #
# --------------------------------------------------------------------------- #

def evaluate_run(
    config: Union[EvalConfig, dict],
    *,
    run_id: Optional[str] = None,
    detector: Optional[DetectorAdapter] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> EvaluationReport:
    """Run the full VisionGuard evaluation and return an ``EvaluationReport``.

    Parameters
    ----------
    config:
        An ``EvalConfig`` instance or a dict that can be validated into one.
        Raises ``pydantic.ValidationError`` immediately on invalid config.
    run_id:
        Unique identifier for this run.  Generated automatically if omitted.
    detector:
        A pre-constructed ``DetectorAdapter``.  When ``None``, the adapter is
        built from ``config.model_id``.  Pass a ``FakeDetector`` in tests.
    progress_callback:
        Called as ``progress_callback(images_completed, images_total)`` after
        each image finishes its clean inference step.

    Returns
    -------
    EvaluationReport
        Status is COMPLETED, PARTIAL, or FAILED (see module docstring).

    Raises
    ------
    pydantic.ValidationError
        When ``config`` cannot be validated.
    FileNotFoundError
        When the dataset is not registered or contains no images.
    """
    # ------------------------------------------------------------------ #
    # Step 1 – validate config                                             #
    # ------------------------------------------------------------------ #
    if isinstance(config, dict):
        config = EvalConfig.model_validate(config)
    else:
        # Re-validate to catch mutations after initial construction.
        EvalConfig.model_validate(config.model_dump())

    _run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(tz=timezone.utc)
    log.info("Starting run %s  model=%s  dataset=%s",
             _run_id, config.model_id, config.dataset_id)

    # ------------------------------------------------------------------ #
    # Step 2 – build detector                                              #
    # ------------------------------------------------------------------ #
    if detector is None:
        detector = _build_detector(config)

    adapter_info = detector.info()

    # ------------------------------------------------------------------ #
    # Step 3 – load dataset                                                #
    # ------------------------------------------------------------------ #
    image_paths = _load_image_paths(config.dataset_id, config.max_images)
    n_images = len(image_paths)
    log.info("Dataset '%s': %d image(s)", config.dataset_id, n_images)

    # ------------------------------------------------------------------ #
    # Step 4 – run clean inference; cache results                          #
    # ------------------------------------------------------------------ #
    clean_image_data: list[tuple[str, int, int, list[Prediction], Path]] = []
    # ^-- (image_id, width, height, predictions, path)
    errors: list[ImageError] = []

    for idx, path in enumerate(image_paths):
        image_id = path.stem
        try:
            img_rgb = _read_rgb(path)
        except Exception as exc:
            log.warning("load failed  %s: %s", image_id, exc)
            errors.append(ImageError(
                image_id=image_id, stage="load",
                message=f"Could not read image: {exc}",
            ))
            if progress_callback:
                progress_callback(idx + 1, n_images)
            continue

        h, w = img_rgb.shape[:2]
        try:
            raw_preds = detector.predict(img_rgb)
            preds = _to_contract_predictions(raw_preds, w, h)
        except Exception as exc:
            log.warning("clean inference failed  %s: %s", image_id, exc)
            errors.append(ImageError(
                image_id=image_id, stage="clean_inference",
                message=f"Inference error: {exc}",
            ))
            if progress_callback:
                progress_callback(idx + 1, n_images)
            continue

        log.debug("clean %s  %d preds", image_id, len(preds))
        clean_image_data.append((image_id, w, h, preds, path))

        if progress_callback:
            progress_callback(idx + 1, n_images)

    # If every image failed during load/clean-inference, mark as FAILED now.
    if not clean_image_data:
        return _assemble_report(
            run_id=_run_id, created_at=created_at,
            config=config, detector=detector, adapter_info=adapter_info,
            image_paths=image_paths,
            clean_image_data=[],
            conditions=[], all_failures=[], errors=errors,
            status=RunStatus.FAILED,
        )

    # ------------------------------------------------------------------ #
    # Step 5-8 – per-condition loop (corruption × severity)               #
    # ------------------------------------------------------------------ #
    conditions: list[ConditionResult] = []
    all_failures: list[FailureInfo] = []

    # Determine total conditions for logging.
    total_conditions = sum(len(spec.severities) for spec in config.corruptions)
    condition_idx = 0

    for spec in config.corruptions:
        kind_str = spec.kind.value          # e.g. "blur"
        kind_enum = spec.kind               # CorruptionKind enum member

        for severity in spec.severities:
            condition_idx += 1
            log.info(
                "Condition %d/%d  %s severity=%d  seed=%d",
                condition_idx, total_conditions, kind_str, severity, config.seed,
            )

            per_image_results: list[tuple[int, int, list[MatchRecord]]] = []
            image_condition_results: list[ImageConditionResult] = []

            for image_id, w, h, clean_preds, path in clean_image_data:
                img_rgb = None

                # Step 5a – apply corruption --------------------------------
                try:
                    img_rgb = _read_rgb(path)  # reload; do not mutate cached array
                    corrupted_rgb = apply_corruption(
                        img_rgb, kind=kind_str, severity=severity, seed=config.seed
                    )
                except Exception as exc:
                    log.warning(
                        "corruption failed  %s  %s s%d: %s",
                        image_id, kind_str, severity, exc,
                    )
                    errors.append(ImageError(
                        image_id=image_id, stage="corruption",
                        corruption=kind_enum, severity=severity,
                        message=f"Corruption error: {exc}",
                    ))
                    continue

                # Step 5b – corrupted inference -----------------------------
                try:
                    raw_corr = detector.predict(corrupted_rgb)
                    corr_preds = _to_contract_predictions(raw_corr, w, h)
                except Exception as exc:
                    log.warning(
                        "corrupted inference failed  %s  %s s%d: %s",
                        image_id, kind_str, severity, exc,
                    )
                    errors.append(ImageError(
                        image_id=image_id, stage="corrupted_inference",
                        corruption=kind_enum, severity=severity,
                        message=f"Inference error: {exc}",
                    ))
                    continue

                # Step 5c – match clean ↔ corrupted ------------------------
                # Convert Prediction contracts to dicts for the matcher.
                clean_dicts = [
                    {
                        "class_id": p.class_id,
                        "class_name": p.class_name,
                        "confidence": p.confidence,
                        "bbox_xyxy": list(p.bbox_xyxy),
                    }
                    for p in clean_preds
                ]
                corr_dicts = [
                    {
                        "class_id": p.class_id,
                        "class_name": p.class_name,
                        "confidence": p.confidence,
                        "bbox_xyxy": list(p.bbox_xyxy),
                    }
                    for p in corr_preds
                ]

                try:
                    match_result = match_predictions(
                        clean_dicts, corr_dicts,
                        iou_threshold=config.match_iou_threshold,
                    )
                except Exception as exc:
                    log.warning(
                        "matching failed  %s  %s s%d: %s",
                        image_id, kind_str, severity, exc,
                    )
                    errors.append(ImageError(
                        image_id=image_id, stage="matching",
                        corruption=kind_enum, severity=severity,
                        message=f"Matching error: {exc}",
                    ))
                    continue

                # Step 5d – per-image metrics --------------------------------
                contract_matches = _to_contract_match_records(match_result.matches)
                image_metrics = MetricSet.from_matches(
                    len(clean_preds), len(corr_preds), contract_matches
                )

                image_result = ImageConditionResult(
                    image_id=image_id,
                    predictions=corr_preds,
                    matches=contract_matches,
                    unmatched_clean_indices=match_result.unmatched_clean_indices,
                    unmatched_corrupted_indices=match_result.unmatched_corrupted_indices,
                    metrics=image_metrics,
                )
                image_condition_results.append(image_result)

                per_image_results.append((
                    len(clean_preds),
                    len(corr_preds),
                    match_result.matches,
                ))

                # Step 5e – record failures ----------------------------------
                _record_failures(
                    image_id=image_id,
                    corruption=kind_enum,
                    severity=severity,
                    clean_preds=clean_preds,
                    corrupted_preds=corr_preds,
                    matches=contract_matches,
                    unmatched_clean=match_result.unmatched_clean_indices,
                    unmatched_corrupted=match_result.unmatched_corrupted_indices,
                    failures=all_failures,
                )

            # Step 6 – pool per-image metrics → condition MetricSet ----------
            if per_image_results:
                all_match_records: list[MatchRecord] = []
                total_clean = total_corr = 0
                for nc, nk, ms in per_image_results:
                    total_clean += nc
                    total_corr += nk
                    all_match_records.extend(ms)
                contract_all = _to_contract_match_records(all_match_records)
                cond_metrics = MetricSet.from_matches(
                    total_clean, total_corr, contract_all
                )
            else:
                # All images failed for this condition.
                cond_metrics = MetricSet.from_matches(0, 0, [])

            conditions.append(ConditionResult(
                corruption=kind_enum,
                severity=severity,
                seed=config.seed,
                metrics=cond_metrics,
                per_image=image_condition_results,
            ))

    # ------------------------------------------------------------------ #
    # Determine run status                                                  #
    # ------------------------------------------------------------------ #
    n_succeeded = sum(len(c.per_image) for c in conditions)
    n_attempted = len(clean_image_data) * total_conditions

    if errors and n_succeeded == 0:
        status = RunStatus.FAILED
    elif errors:
        status = RunStatus.PARTIAL
    else:
        status = RunStatus.COMPLETED

    # ------------------------------------------------------------------ #
    # Step 9 – assemble and return report                                  #
    # ------------------------------------------------------------------ #
    return _assemble_report(
        run_id=_run_id, created_at=created_at,
        config=config, detector=detector, adapter_info=adapter_info,
        image_paths=image_paths,
        clean_image_data=clean_image_data,
        conditions=conditions, all_failures=all_failures, errors=errors,
        status=status,
    )


# --------------------------------------------------------------------------- #
# Report assembly                                                               #
# --------------------------------------------------------------------------- #

def _assemble_report(
    *,
    run_id: str,
    created_at: datetime,
    config: EvalConfig,
    detector: DetectorAdapter,
    adapter_info: dict,
    image_paths: list[Path],
    clean_image_data: list[tuple],
    conditions: list[ConditionResult],
    all_failures: list[FailureInfo],
    errors: list[ImageError],
    status: RunStatus,
) -> EvaluationReport:
    """Assemble the final ``EvaluationReport`` from all pipeline outputs."""

    # Build ImagePredictions for clean run.
    clean_predictions: list[ImagePredictions] = []
    for image_id, w, h, preds, path in clean_image_data:
        clean_predictions.append(ImagePredictions(
            image_id=image_id,
            width=w,
            height=h,
            image_path=str(path),
            predictions=preds,
        ))

    # Build ModelInfo from adapter.
    model_info = ModelInfo(
        model_id=config.model_id,
        name=adapter_info.get("model_id", config.model_id),
        framework=adapter_info.get("adapter", "unknown"),
        weights=adapter_info.get("weights", "unknown"),
        weights_license=(
            "PyTorch Foundation License Agreement (torchvision COCO weights)"
            if "Torchvision" in adapter_info.get("adapter", "")
            else "unknown"
        ),
        weights_sha256=None,  # expensive to compute at runtime; left for offline audit
    )

    dataset_info = DatasetInfo(
        dataset_id=config.dataset_id,
        name=config.dataset_id,
        image_count=len(image_paths),
        has_ground_truth=False,
    )

    sw_versions = _software_versions()
    # Record the NMS and score settings in software_versions for traceability.
    sw_versions["score_threshold"] = str(config.score_threshold)
    sw_versions["match_iou_threshold"] = str(config.match_iou_threshold)
    nms = detector.nms_settings
    sw_versions["nms_iou_threshold"] = str(nms.get("nms_iou_threshold", "n/a"))
    sw_versions["nms_source"] = str(nms.get("source", ""))

    return EvaluationReport(
        run_id=run_id,
        status=status,
        created_at=created_at,
        model=model_info,
        dataset=dataset_info,
        config=config,
        clean_predictions=clean_predictions,
        conditions=conditions,
        failures=all_failures,
        errors=errors,
        ground_truth_metrics=None,
        software_versions=sw_versions,
        metric_definitions=dict(METRIC_DEFINITIONS),
        limitations=list(LIMITATIONS),
    )
