import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from visionguard.core import evaluate_run
from visionguard.core.fixtures import build_fixture_report
from visionguard.core.types import (EvalConfig, EvaluationReport, MatchRecord, MetricSet, Prediction)

ROOT = Path(__file__).resolve().parent.parent


def P(**kw):
    base = dict(class_id=0, class_name="person", confidence=0.9, bbox_xyxy=[1, 1, 10, 10])
    return Prediction(**{**base, **kw})


def test_fixture_is_valid_and_flagged():
    r = build_fixture_report()
    assert r.is_fixture and r.schema_version == "1.0.0"


def test_json_roundtrip():
    r = build_fixture_report()
    assert EvaluationReport.model_validate_json(r.model_dump_json()) == r


def test_committed_fixture_matches_builder():
    on_disk = json.loads((ROOT / "fixtures/sample_report.json").read_text())
    assert on_disk == json.loads(build_fixture_report().model_dump_json())


def test_committed_schema_matches_models():
    on_disk = json.loads((ROOT / "schema/evaluation_report.schema.json").read_text())
    assert on_disk == EvaluationReport.model_json_schema()


@pytest.mark.parametrize("kw", [
    dict(confidence=1.2), dict(confidence=-0.1), dict(bbox_xyxy=[5, 5, 5, 9]), dict(bbox_xyxy=[-1, 0, 4, 4]),
    dict(bbox_xyxy=[0, 0, 4]), dict(bbox_xyxy=[0, 0, float("inf"), 4]), dict(class_id=-1), dict(extra=1),
])
def test_bad_predictions_rejected(kw):
    with pytest.raises(ValidationError):
        P(**kw)


def test_bad_config_rejected():
    ok = dict(model_id="m", dataset_id="d", corruptions=[{"kind": "blur", "severities": [1]}])
    EvalConfig(**ok)
    for bad in (dict(corruptions=[{"kind": "blur", "severities": [4]}]),
                dict(corruptions=[{"kind": "fog", "severities": [1]}]),
                dict(corruptions=[{"kind": "blur", "severities": [1]}, {"kind": "blur", "severities": [2]}]),
                dict(corruptions=[]), dict(score_threshold=2)):
        with pytest.raises(ValidationError):
            EvalConfig(**{**ok, **bad})


def test_metric_zero_cases_are_null_with_reason():
    m = MetricSet.from_matches(0, 0, [])
    assert m.detection_retention is None and "detection_retention" in m.unavailable
    m = MetricSet.from_matches(3, 0, [])
    assert m.detection_retention == 0.0 and m.mean_matched_iou is None and m.class_flip_rate is None


def test_metric_values():
    ms = [MatchRecord(clean_index=0, corrupted_index=0, iou=0.8, confidence_delta=-0.1, class_flip=False),
          MatchRecord(clean_index=1, corrupted_index=1, iou=0.6, confidence_delta=-0.3, class_flip=True)]
    m = MetricSet.from_matches(4, 3, ms)
    assert m.detection_retention == 0.5 and m.class_consistent_retention == 0.25
    assert m.mean_matched_iou == 0.7 and m.mean_confidence_delta == -0.2 and m.class_flip_rate == 0.5


def test_inconsistent_metrics_rejected():
    with pytest.raises(ValidationError):
        MetricSet(n_clean=3, n_corrupted=3, n_matched=1, n_class_flips=0, n_unmatched_clean=1,
                  n_unmatched_corrupted=2, detection_retention=0.3, class_consistent_retention=0.3,
                  mean_matched_iou=0.5, mean_confidence_delta=0.0, class_flip_rate=0.0)


def test_duplicate_match_rejected():
    d = json.loads(build_fixture_report().model_dump_json())
    img = d["conditions"][1]["per_image"][0]
    img["matches"][1]["corrupted_index"] = img["matches"][0]["corrupted_index"]
    with pytest.raises(ValidationError):
        EvaluationReport.model_validate(d)


def test_schema_version_and_status_rules():
    d = json.loads(build_fixture_report().model_dump_json())
    for patch in (dict(schema_version="9.9.9"), dict(status="RUNNING"), dict(status="PARTIAL"),
                  dict(ground_truth_metrics={"mAP": 0.5})):
        with pytest.raises(ValidationError):
            EvaluationReport.model_validate({**d, **patch})


def test_evaluate_run_stub_contract():
    calls = []
    cfg = EvalConfig.model_validate_json((ROOT / "fixtures/sample_config.json").read_text())
    r = evaluate_run(cfg, run_id="run-123", progress_callback=lambda d, t: calls.append((d, t)))
    assert r.run_id == "run-123" and calls == [(1, 2), (2, 2)]
    with pytest.raises(ValidationError):
        evaluate_run({"model_id": "m"})
