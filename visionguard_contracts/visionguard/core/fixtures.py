"""Builds the DEMO report fixture. Matches are hand-specified (not produced by the real matcher),
but every number derived from them (IoU, deltas, flips, metrics, failures) is computed so the
fixture is internally consistent. Replace with real output once the pipeline exists."""
from __future__ import annotations

from datetime import datetime, timezone

from .types import (
    ConditionResult, CorruptionKind, CorruptionSpec, DatasetInfo, EvalConfig, EvaluationReport,
    FailureInfo, FailureType, ImageConditionResult, ImagePredictions, MatchRecord, MetricSet,
    ModelInfo, Prediction, RunStatus,
)


def _p(cid: int, name: str, conf: float, box: list[float]) -> Prediction:
    return Prediction(class_id=cid, class_name=name, confidence=conf, bbox_xyxy=box)


def _iou(a: list[float], b: list[float]) -> float:
    iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = iw * ih
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua else 0.0


CLEAN = {
    "image_001": [_p(0, "person", 0.94, [100, 80, 300, 400]), _p(16, "dog", 0.88, [320, 200, 520, 420]),
                  _p(2, "car", 0.76, [10, 300, 120, 380])],
    "image_002": [_p(2, "car", 0.91, [50, 120, 400, 380]), _p(0, "person", 0.67, [420, 100, 520, 360])],
}

# (corrupted predictions, hand-chosen (clean_idx, corrupted_idx) pairs) per condition per image
CONDITIONS = {
    (CorruptionKind.BLUR, 2): {
        "image_001": ([_p(0, "person", 0.90, [104, 84, 298, 396]), _p(15, "cat", 0.55, [322, 204, 516, 418])],
                      [(0, 0), (1, 1)]),
        "image_002": ([_p(2, "car", 0.85, [55, 126, 395, 376]), _p(56, "chair", 0.52, [450, 200, 560, 400])],
                      [(0, 0)]),
    },
    (CorruptionKind.LOW_LIGHT, 2): {
        "image_001": ([_p(0, "person", 0.86, [102, 82, 301, 402]), _p(16, "dog", 0.71, [318, 198, 524, 424]),
                       _p(2, "car", 0.58, [12, 302, 118, 382])], [(0, 0), (1, 1), (2, 2)]),
        "image_002": ([_p(2, "car", 0.80, [52, 124, 398, 378]), _p(0, "person", 0.54, [424, 104, 516, 356])],
                      [(0, 0), (1, 1)]),
    },
}

SIZE = (640, 480)
IOU_T = 0.5


def _image_result(kind, sev, image_id, corr, pairs):
    clean = CLEAN[image_id]
    matches, failures = [], []
    for ci, ki in pairs:
        c, k = clean[ci], corr[ki]
        iou = _iou(c.bbox_xyxy, k.bbox_xyxy)
        assert iou >= IOU_T, f"fixture pair below IoU threshold: {image_id} {ci}->{ki} {iou:.2f}"
        flip = c.class_id != k.class_id
        matches.append(MatchRecord(clean_index=ci, corrupted_index=ki, iou=round(iou, 4),
                                   confidence_delta=round(k.confidence - c.confidence, 4), class_flip=flip))
        if flip:
            failures.append(FailureInfo(
                image_id=image_id, corruption=kind, severity=sev, failure_type=FailureType.CLASS_FLIP,
                clean_index=ci, corrupted_index=ki, clean_prediction=c, corrupted_prediction=k,
                iou=round(iou, 4), details=f"{c.class_name} became {k.class_name} (IoU {iou:.2f})"))
    un_c = [i for i in range(len(clean)) if i not in {p[0] for p in pairs}]
    un_k = [i for i in range(len(corr)) if i not in {p[1] for p in pairs}]
    for i in un_c:
        failures.append(FailureInfo(
            image_id=image_id, corruption=kind, severity=sev, failure_type=FailureType.MISSING_AFTER_CORRUPTION,
            clean_index=i, clean_prediction=clean[i], details=f"clean {clean[i].class_name} has no match"))
    for i in un_k:
        failures.append(FailureInfo(
            image_id=image_id, corruption=kind, severity=sev, failure_type=FailureType.NEW_AFTER_CORRUPTION,
            corrupted_index=i, corrupted_prediction=corr[i],
            details=f"corrupted {corr[i].class_name} has no clean counterpart"))
    res = ImageConditionResult(
        image_id=image_id, corrupted_image_path=f"fixture_assets/{kind.value}_s{sev}/{image_id}.jpg",
        predictions=corr, matches=matches, unmatched_clean_indices=un_c, unmatched_corrupted_indices=un_k,
        metrics=MetricSet.from_matches(len(clean), len(corr), matches))
    return res, failures


def build_fixture_report() -> EvaluationReport:
    config = EvalConfig(
        model_id="fasterrcnn_resnet50_fpn", dataset_id="visionguard_demo", seed=42,
        corruptions=[CorruptionSpec(kind=CorruptionKind.BLUR, severities=[2]),
                     CorruptionSpec(kind=CorruptionKind.LOW_LIGHT, severities=[2])])
    conditions, failures = [], []
    for (kind, sev), per in CONDITIONS.items():
        results, all_matches, n_c, n_k = [], [], 0, 0
        for image_id, (corr, pairs) in per.items():
            r, f = _image_result(kind, sev, image_id, corr, pairs)
            results.append(r); failures += f; all_matches += r.matches
            n_c += len(CLEAN[image_id]); n_k += len(corr)
        conditions.append(ConditionResult(corruption=kind, severity=sev, seed=config.seed,
                                          metrics=MetricSet.from_matches(n_c, n_k, all_matches),
                                          per_image=results))
    return EvaluationReport(
        is_fixture=True, run_id="fixture-0001", status=RunStatus.COMPLETED,
        created_at=datetime(2026, 10, 24, tzinfo=timezone.utc),
        model=ModelInfo(model_id=config.model_id, name="Faster R-CNN ResNet50 FPN (placeholder)",
                        framework="torchvision", weights="FIXTURE - not a real run", weights_license="n/a"),
        dataset=DatasetInfo(dataset_id="visionguard_demo", name="VisionGuard Demo (fixture)",
                            image_count=len(CLEAN), has_ground_truth=False),
        config=config,
        clean_predictions=[ImagePredictions(image_id=i, width=SIZE[0], height=SIZE[1],
                                            image_path=f"fixture_assets/clean/{i}.jpg", predictions=p)
                           for i, p in CLEAN.items()],
        conditions=conditions, failures=failures,
        software_versions={"note": "fixture data, not produced by a real run"})
