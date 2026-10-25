"""VisionGuard shared contracts. SINGLE SOURCE OF TRUTH for ML <-> backend <-> frontend <-> tests.

Conventions
- bbox_xyxy = [x_min, y_min, x_max, y_max], absolute pixels of the ORIGINAL image.
- confidence in [0, 1]. ML core works on RGB images only.
- Reports are only produced in terminal states: COMPLETED, PARTIAL, FAILED.
- Changing any field requires bumping SCHEMA_VERSION and a reviewed PR.
"""
from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0.0"

METRIC_DEFINITIONS: dict[str, str] = {
    "detection_retention": (
        "Matched clean detections / clean detections. A clean detection is retained if it is matched "
        "one-to-one to a corrupted detection with IoU >= match_iou_threshold, regardless of class. "
        "Measures prediction consistency, not accuracy."
    ),
    "class_consistent_retention": (
        "Matched pairs with the SAME class / clean detections. Stricter than detection_retention."
    ),
    "mean_matched_iou": "Mean IoU over matched pairs. Shows how far boxes move under corruption.",
    "mean_confidence_delta": (
        "Mean of (corrupted confidence - clean confidence) over matched pairs. Negative = less confident. "
        "Confidence is not correctness."
    ),
    "class_flip_rate": "Matched pairs whose class changed / matched pairs.",
    "unmatched": (
        "Detections with no counterpart in the other run. NOT automatically false positives or false "
        "negatives: no ground truth is used."
    ),
}

LIMITATIONS: list[str] = [
    "Metrics measure prediction consistency under controlled corruption, not ground-truth accuracy.",
    "Precision, recall, F1 and mAP are not reported unless the dataset has valid ground-truth labels.",
    "Only the listed corruptions and severities were tested; this does not prove general robustness.",
    "Results depend on the detector, weights, score threshold and matching threshold recorded in this report.",
    "Condition-level metrics pool all matches across images (micro-average), not an average of per-image ratios.",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CorruptionKind(str, Enum):
    BLUR = "blur"
    LOW_LIGHT = "low_light"
    GAUSSIAN_NOISE = "gaussian_noise"


class RunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


TERMINAL_STATUSES = {RunStatus.COMPLETED, RunStatus.PARTIAL, RunStatus.FAILED}


class FailureType(str, Enum):
    MISSING_AFTER_CORRUPTION = "MISSING_AFTER_CORRUPTION"  # clean detection with no match
    NEW_AFTER_CORRUPTION = "NEW_AFTER_CORRUPTION"          # corrupted detection with no match
    CLASS_FLIP = "CLASS_FLIP"                              # matched by IoU, class changed
    LOCALIZATION_SHIFT = "LOCALIZATION_SHIFT"              # matched, IoU well below 1 (reserved)
    CONFIDENCE_DROP = "CONFIDENCE_DROP"                    # matched, large confidence drop (reserved)


# ----------------------------------------------------------------------------- config
class CorruptionSpec(Strict):
    kind: CorruptionKind
    severities: list[int] = Field(min_length=1)

    @field_validator("severities")
    @classmethod
    def _severities(cls, v: list[int]) -> list[int]:
        if any(s not in (1, 2, 3) for s in v):
            raise ValueError("severity must be 1, 2 or 3")
        if len(set(v)) != len(v):
            raise ValueError("duplicate severities")
        return v


class EvalConfig(Strict):
    model_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    corruptions: list[CorruptionSpec] = Field(min_length=1)
    seed: int = 0
    score_threshold: float = Field(0.5, ge=0.0, le=1.0)
    match_iou_threshold: float = Field(0.5, gt=0.0, le=1.0)
    max_images: Optional[int] = Field(None, ge=1)

    @field_validator("corruptions")
    @classmethod
    def _unique_kinds(cls, v: list[CorruptionSpec]) -> list[CorruptionSpec]:
        kinds = [c.kind for c in v]
        if len(set(kinds)) != len(kinds):
            raise ValueError("each corruption kind may appear once")
        return v


# ------------------------------------------------------------------------ predictions
class Prediction(Strict):
    class_id: int = Field(ge=0)
    class_name: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bbox_xyxy: list[float] = Field(min_length=4, max_length=4)

    @field_validator("bbox_xyxy")
    @classmethod
    def _box(cls, v: list[float]) -> list[float]:
        if not all(math.isfinite(x) for x in v):
            raise ValueError("bbox coordinates must be finite")
        x1, y1, x2, y2 = v
        if x1 < 0 or y1 < 0:
            raise ValueError("bbox coordinates must be >= 0")
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox must satisfy x_max > x_min and y_max > y_min")
        return v


class ImagePredictions(Strict):
    image_id: str = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    image_path: Optional[str] = None  # relative to the artifact root; null if unavailable
    predictions: list[Prediction]

    @model_validator(mode="after")
    def _inside_image(self) -> "ImagePredictions":
        for p in self.predictions:
            if p.bbox_xyxy[2] > self.width + 1e-6 or p.bbox_xyxy[3] > self.height + 1e-6:
                raise ValueError(f"{self.image_id}: bbox exceeds image size {self.width}x{self.height}")
        return self


# --------------------------------------------------------------------------- matching
class MatchRecord(Strict):
    clean_index: int = Field(ge=0)      # index into the clean predictions of this image
    corrupted_index: int = Field(ge=0)  # index into the corrupted predictions of this image
    iou: float = Field(ge=0.0, le=1.0)
    confidence_delta: float = Field(ge=-1.0, le=1.0)  # corrupted - clean
    class_flip: bool


_METRIC_FIELDS = (
    "detection_retention", "class_consistent_retention", "mean_matched_iou",
    "mean_confidence_delta", "class_flip_rate",
)


class MetricSet(Strict):
    n_clean: int = Field(ge=0)
    n_corrupted: int = Field(ge=0)
    n_matched: int = Field(ge=0)
    n_class_flips: int = Field(ge=0)
    n_unmatched_clean: int = Field(ge=0)
    n_unmatched_corrupted: int = Field(ge=0)
    detection_retention: Optional[float] = Field(None, ge=0.0, le=1.0)
    class_consistent_retention: Optional[float] = Field(None, ge=0.0, le=1.0)
    mean_matched_iou: Optional[float] = Field(None, ge=0.0, le=1.0)
    mean_confidence_delta: Optional[float] = Field(None, ge=-1.0, le=1.0)
    class_flip_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    # A metric that cannot be computed is null AND explained here (never 0, never NaN).
    unavailable: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> "MetricSet":
        if self.n_matched + self.n_unmatched_clean != self.n_clean:
            raise ValueError("n_matched + n_unmatched_clean must equal n_clean")
        if self.n_matched + self.n_unmatched_corrupted != self.n_corrupted:
            raise ValueError("n_matched + n_unmatched_corrupted must equal n_corrupted")
        if self.n_class_flips > self.n_matched:
            raise ValueError("n_class_flips cannot exceed n_matched")
        for name in _METRIC_FIELDS:
            is_none = getattr(self, name) is None
            if is_none and name not in self.unavailable:
                raise ValueError(f"{name} is null but has no reason in 'unavailable'")
            if not is_none and name in self.unavailable:
                raise ValueError(f"{name} has a value but is listed as unavailable")
        return self

    @classmethod
    def from_matches(cls, n_clean: int, n_corrupted: int, matches: list[MatchRecord]) -> "MetricSet":
        """Reference implementation of the metric definitions (also used for pooling)."""
        m = len(matches)
        flips = sum(1 for x in matches if x.class_flip)
        un: dict[str, str] = {}
        vals: dict[str, Optional[float]] = {}
        if n_clean == 0:
            for k in ("detection_retention", "class_consistent_retention"):
                vals[k] = None
                un[k] = "no clean detections"
        else:
            vals["detection_retention"] = m / n_clean
            vals["class_consistent_retention"] = (m - flips) / n_clean
        if m == 0:
            for k in ("mean_matched_iou", "mean_confidence_delta", "class_flip_rate"):
                vals[k] = None
                un[k] = "no matched pairs"
        else:
            vals["mean_matched_iou"] = sum(x.iou for x in matches) / m
            vals["mean_confidence_delta"] = sum(x.confidence_delta for x in matches) / m
            vals["class_flip_rate"] = flips / m
        return cls(
            n_clean=n_clean, n_corrupted=n_corrupted, n_matched=m, n_class_flips=flips,
            n_unmatched_clean=n_clean - m, n_unmatched_corrupted=n_corrupted - m,
            unavailable=un, **{k: (None if v is None else round(v, 4)) for k, v in vals.items()},
        )


class ImageConditionResult(Strict):
    image_id: str
    corrupted_image_path: Optional[str] = None
    predictions: list[Prediction]  # corrupted predictions
    matches: list[MatchRecord]
    unmatched_clean_indices: list[int]
    unmatched_corrupted_indices: list[int]
    metrics: MetricSet

    @model_validator(mode="after")
    def _one_to_one(self) -> "ImageConditionResult":
        ci = [m.clean_index for m in self.matches]
        ki = [m.corrupted_index for m in self.matches]
        if len(set(ci)) != len(ci) or len(set(ki)) != len(ki):
            raise ValueError(f"{self.image_id}: matching must be one-to-one")
        if set(ci) & set(self.unmatched_clean_indices) or set(ki) & set(self.unmatched_corrupted_indices):
            raise ValueError(f"{self.image_id}: an index is both matched and unmatched")
        mt = self.metrics
        if (mt.n_corrupted != len(self.predictions) or mt.n_matched != len(self.matches)
                or mt.n_unmatched_clean != len(self.unmatched_clean_indices)
                or mt.n_unmatched_corrupted != len(self.unmatched_corrupted_indices)
                or mt.n_class_flips != sum(m.class_flip for m in self.matches)):
            raise ValueError(f"{self.image_id}: metric counts disagree with matches/predictions")
        return self


class ConditionResult(Strict):
    corruption: CorruptionKind
    severity: int
    seed: int
    metrics: MetricSet  # pooled over all images
    per_image: list[ImageConditionResult]

    @field_validator("severity")
    @classmethod
    def _sev(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError("severity must be 1, 2 or 3")
        return v

    @model_validator(mode="after")
    def _pooled(self) -> "ConditionResult":
        mt = self.metrics
        if (mt.n_matched != sum(r.metrics.n_matched for r in self.per_image)
                or mt.n_corrupted != sum(r.metrics.n_corrupted for r in self.per_image)
                or mt.n_clean != sum(r.metrics.n_clean for r in self.per_image)):
            raise ValueError("pooled metric counts must equal the sum over per_image")
        return self


class FailureInfo(Strict):
    image_id: str
    corruption: CorruptionKind
    severity: int
    failure_type: FailureType
    clean_index: Optional[int] = None
    corrupted_index: Optional[int] = None
    clean_prediction: Optional[Prediction] = None
    corrupted_prediction: Optional[Prediction] = None
    iou: Optional[float] = Field(None, ge=0.0, le=1.0)
    details: str


# ---------------------------------------------------------------------------- report
class ModelInfo(Strict):
    model_id: str
    name: str
    framework: str
    weights: str
    weights_license: str
    weights_sha256: Optional[str] = None


class DatasetInfo(Strict):
    dataset_id: str
    name: str
    image_count: int = Field(ge=0)
    has_ground_truth: bool
    license: Optional[str] = None


class ImageError(Strict):
    image_id: Optional[str] = None
    stage: str  # load | clean_inference | corruption | corrupted_inference | matching
    corruption: Optional[CorruptionKind] = None
    severity: Optional[int] = None
    message: str


class EvaluationReport(Strict):
    schema_version: str = SCHEMA_VERSION
    is_fixture: bool = False  # true => demo data, NOT a real evaluation; UI must show a banner
    run_id: str
    status: RunStatus
    created_at: datetime
    model: ModelInfo
    dataset: DatasetInfo
    config: EvalConfig
    clean_predictions: list[ImagePredictions]
    conditions: list[ConditionResult]
    failures: list[FailureInfo]
    errors: list[ImageError] = Field(default_factory=list)
    ground_truth_metrics: Optional[dict[str, float]] = None  # reserved (P1); null without labels
    software_versions: dict[str, str] = Field(default_factory=dict)
    metric_definitions: dict[str, str] = Field(default_factory=lambda: dict(METRIC_DEFINITIONS))
    limitations: list[str] = Field(default_factory=lambda: list(LIMITATIONS))

    @model_validator(mode="after")
    def _integrity(self) -> "EvaluationReport":
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if self.status not in TERMINAL_STATUSES:
            raise ValueError("a report can only exist in a terminal status")
        if self.status == RunStatus.COMPLETED and self.errors:
            raise ValueError("COMPLETED run must have no errors")
        if self.status in (RunStatus.PARTIAL, RunStatus.FAILED) and not self.errors:
            raise ValueError(f"{self.status.value} run must record at least one error")
        if not self.dataset.has_ground_truth and self.ground_truth_metrics is not None:
            raise ValueError("ground_truth_metrics must be null when the dataset has no labels")

        clean = {ip.image_id: ip for ip in self.clean_predictions}
        if len(clean) != len(self.clean_predictions):
            raise ValueError("duplicate image_id in clean_predictions")
        wanted = {(c.kind, s) for c in self.config.corruptions for s in c.severities}
        seen: set[tuple[CorruptionKind, int]] = set()
        for cond in self.conditions:
            key = (cond.corruption, cond.severity)
            if key not in wanted or key in seen:
                raise ValueError(f"condition {key} not in config or duplicated")
            seen.add(key)
            ids: set[str] = set()
            for r in cond.per_image:
                if r.image_id not in clean or r.image_id in ids:
                    raise ValueError(f"unknown or duplicate image_id {r.image_id} in {key}")
                ids.add(r.image_id)
                n = len(clean[r.image_id].predictions)
                matched = {m.clean_index for m in r.matches}
                if matched | set(r.unmatched_clean_indices) != set(range(n)) or r.metrics.n_clean != n:
                    raise ValueError(f"{r.image_id} {key}: clean indices do not partition 0..{n - 1}")
                nk = len(r.predictions)
                matched_k = {m.corrupted_index for m in r.matches}
                if matched_k | set(r.unmatched_corrupted_indices) != set(range(nk)):
                    raise ValueError(f"{r.image_id} {key}: corrupted indices do not partition 0..{nk - 1}")
        for f in self.failures:
            if f.image_id not in clean:
                raise ValueError(f"failure references unknown image_id {f.image_id}")
        return self
