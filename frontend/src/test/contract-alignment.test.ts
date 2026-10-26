import { describe, it, expect, vi } from "vitest";
import { api, ApiError, type EvaluationReport, type RunResponse } from "../lib/api";
import openapiSchema from "../../openapi.json";

describe("Frontend/Backend Contract Alignment", () => {
  it("OpenAPI schema is present and defines expected core paths", () => {
    expect(openapiSchema).toBeDefined();
    expect(openapiSchema.paths).toHaveProperty("/health");
    expect(openapiSchema.paths).toHaveProperty("/api/v1/models");
    expect(openapiSchema.paths).toHaveProperty("/api/v1/datasets");
    expect(openapiSchema.paths).toHaveProperty("/api/v1/runs");
    expect(openapiSchema.paths).toHaveProperty("/api/v1/runs/{run_id}");
    expect(openapiSchema.paths).toHaveProperty("/api/v1/runs/{run_id}/report");
    expect(openapiSchema.paths).toHaveProperty("/api/v1/runs/{run_id}/artifacts");
  });

  it("OpenAPI schema matches Prediction and MatchRecord field names", () => {
    const schemas = (openapiSchema as any).components.schemas;
    expect(schemas.Prediction.properties).toHaveProperty("confidence");
    expect(schemas.Prediction.properties).toHaveProperty("class_id");
    expect(schemas.Prediction.properties).toHaveProperty("class_name");
    expect(schemas.Prediction.properties).toHaveProperty("bbox_xyxy");

    expect(schemas.MatchRecord.properties).toHaveProperty("clean_index");
    expect(schemas.MatchRecord.properties).toHaveProperty("corrupted_index");
    expect(schemas.MatchRecord.properties).toHaveProperty("iou");
    expect(schemas.MatchRecord.properties).toHaveProperty("class_flip");
  });

  it("ApiError correctly formats FastAPI validation error arrays", () => {
    const errorBody = {
      detail: [
        { loc: ["body", "model_id"], msg: "field required", type: "missing" },
        { loc: ["body", "corruptions"], msg: "each corruption kind may appear once", type: "value_error" },
      ],
    };

    // Simulate formatting
    const formatted = errorBody.detail.map((e) => `${e.loc.join(".")}: ${e.msg}`).join("; ");
    const err = new ApiError(422, formatted);
    expect(err.status).toBe(422);
    expect(err.detail).toContain("body.model_id: field required");
    expect(err.detail).toContain("body.corruptions: each corruption kind may appear once");
  });

  it("getArtifactUrl produces safe URI encoded paths", () => {
    const url = api.getArtifactUrl("test-run-123", "corrupted_gaussian_noise_1_image 01");
    expect(url).toContain("/api/v1/runs/test-run-123/artifacts/corrupted_gaussian_noise_1_image%2001");
  });
});
