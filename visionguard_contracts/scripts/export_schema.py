"""Writes fixtures/ and schema/ files. Run: python -m scripts.export_schema"""
import json
from pathlib import Path

from visionguard.core.fixtures import build_fixture_report
from visionguard.core.types import EvalConfig, EvaluationReport

root = Path(__file__).resolve().parent.parent
rep = build_fixture_report()
(root / "fixtures/sample_report.json").write_text(rep.model_dump_json(indent=2) + "\n")
(root / "fixtures/sample_config.json").write_text(rep.config.model_dump_json(indent=2) + "\n")
(root / "schema/evaluation_report.schema.json").write_text(json.dumps(EvaluationReport.model_json_schema(), indent=2) + "\n")
(root / "schema/eval_config.schema.json").write_text(json.dumps(EvalConfig.model_json_schema(), indent=2) + "\n")
print("exported")
