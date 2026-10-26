/**
 * Centralized Typed API Client for VisionGuard Backend.
 *
 * Source of truth: FastAPI OpenAPI schema, generated via openapi-typescript into api-types.ts.
 * Base URL configurable via VITE_API_BASE_URL (defaults to http://127.0.0.1:8000).
 */

import type { components } from "./api-types";

// Re-export canonical Pydantic-derived types
export type ModelsResponse = components["schemas"]["ModelsResponse"];
export type DatasetMetadata = components["schemas"]["DatasetMetadata"];
export type DatasetsResponse = components["schemas"]["DatasetsResponse"];
export type CorruptionKind = components["schemas"]["CorruptionKind"];
export type CorruptionSpec = components["schemas"]["CorruptionSpec"];
export type EvalConfig = components["schemas"]["EvalConfig"];
export type RunCreateRequest = components["schemas"]["RunCreateRequest"];
export type RunStatus = components["schemas"]["RunStatus"];
export type RunResponse = components["schemas"]["RunResponse"];
export type RunListResponse = components["schemas"]["RunListResponse"];
export type ArtifactItem = components["schemas"]["ArtifactItem"];
export type RunArtifactsResponse = components["schemas"]["RunArtifactsResponse"];

export type Prediction = components["schemas"]["Prediction"];
export type MatchRecord = components["schemas"]["MatchRecord"];
export type MetricSet = components["schemas"]["MetricSet"];
export type ImageConditionResult = components["schemas"]["ImageConditionResult"];
export type ConditionResult = components["schemas"]["ConditionResult"];
export type ImagePredictions = components["schemas"]["ImagePredictions"];
export type FailureInfo = components["schemas"]["FailureInfo"];
export type ImageError = components["schemas"]["ImageError"];
export type EvaluationReport = components["schemas"]["EvaluationReport"];
export type ReportResponse = components["schemas"]["ReportResponse"];

// Canonical aliases for consumers
export type ConditionReport = ConditionResult;
export type ConditionMetrics = MetricSet;
export type FailureRecord = FailureInfo;
export type CleanImagePredictions = ImagePredictions;
export type PerImageCondition = ImageConditionResult;
export type PerImagePrediction = Prediction;

const API_BASE_URL =
  (import.meta as any).env?.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API Error ${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function formatErrorDetail(errJson: any, defaultText: string): string {
  if (!errJson) return defaultText;
  if (typeof errJson.detail === "string") return errJson.detail;
  if (Array.isArray(errJson.detail)) {
    // Format FastAPI validation errors
    return errJson.detail
      .map((e: any) => {
        const loc = Array.isArray(e.loc) ? e.loc.join(".") : "";
        return loc ? `${loc}: ${e.msg || "invalid"}` : (e.msg || "validation error");
      })
      .join("; ");
  }
  return JSON.stringify(errJson.detail || errJson);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const headers = new Headers(options.headers || {});
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (options.body && typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (netErr: any) {
    throw new ApiError(0, `Network error connecting to VisionGuard API: ${netErr.message || "Connection failed"}`);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errJson = await response.json();
      detail = formatErrorDetail(errJson, response.statusText);
    } catch {
      // response body was not valid JSON
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getBaseUrl(): string {
    return API_BASE_URL;
  },

  async getHealth(): Promise<{ status: string; database: string }> {
    return request<{ status: string; database: string }>("/health");
  },

  async getModels(): Promise<ModelsResponse> {
    return request<ModelsResponse>("/api/v1/models");
  },

  async getDatasets(): Promise<DatasetsResponse> {
    return request<DatasetsResponse>("/api/v1/datasets");
  },

  async createRun(config: RunCreateRequest): Promise<RunResponse> {
    return request<RunResponse>("/api/v1/runs", {
      method: "POST",
      body: JSON.stringify(config),
    });
  },

  async getRuns(limit: number = 50, offset: number = 0): Promise<RunListResponse> {
    return request<RunListResponse>(`/api/v1/runs?limit=${limit}&offset=${offset}`);
  },

  async getRun(runId: string): Promise<RunResponse> {
    return request<RunResponse>(`/api/v1/runs/${runId}`);
  },

  async getReport(runId: string): Promise<ReportResponse> {
    return request<ReportResponse>(`/api/v1/runs/${runId}/report`);
  },

  async getArtifacts(runId: string): Promise<RunArtifactsResponse> {
    return request<RunArtifactsResponse>(`/api/v1/runs/${runId}/artifacts`);
  },

  getArtifactUrl(runId: string, artifactId: string): string {
    return `${API_BASE_URL}/api/v1/runs/${runId}/artifacts/${encodeURIComponent(artifactId)}`;
  },

  async fetchArtifactBlob(runId: string, artifactId: string): Promise<Blob> {
    const url = this.getArtifactUrl(runId, artifactId);
    let resp: Response;
    try {
      resp = await fetch(url);
    } catch (netErr: any) {
      throw new ApiError(0, `Network error loading artifact: ${netErr.message || "Connection failed"}`);
    }
    if (!resp.ok) {
      throw new ApiError(resp.status, `Failed to load artifact ${artifactId}`);
    }
    return resp.blob();
  },
};

