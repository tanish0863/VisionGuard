import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  Eye,
  FileSearch,
  Filter,
  Layers,
  Play,
  Plus,
  RefreshCw,
  Sparkles,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  api,
  type ArtifactItem,
  type CorruptionKind,
  type DatasetMetadata,
  type EvaluationReport,
  type FailureRecord,
  type RunCreateRequest,
  type RunResponse,
} from "@/lib/api";

// -----------------------------------------------------------------------------
// Workspace Layout
// -----------------------------------------------------------------------------

export function Workspace({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const [apiConnected, setApiConnected] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;
    api
      .getHealth()
      .then(() => {
        if (mounted) setApiConnected(true);
      })
      .catch(() => {
        if (mounted) setApiConnected(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="vg-workspace min-h-screen bg-background text-foreground">
      <header className="vg-header flex flex-wrap items-center justify-between gap-5 border-b border-border px-6 py-5">
        <Link to="/" className="flex items-center gap-2 text-xl font-semibold">
          <Activity className="text-primary" />
          VisionGuard <span className="font-normal text-muted-foreground">AI</span>
        </Link>
        <nav aria-label="Workspace navigation" className="flex flex-wrap items-center gap-5 text-sm">
          <Link to="/dashboard" activeProps={{ className: "text-primary font-medium" }}>
            Overview
          </Link>
          <Link to="/new" activeProps={{ className: "text-primary font-medium" }}>
            New evaluation
          </Link>
          <Link to="/settings" activeProps={{ className: "text-primary font-medium" }}>
            Settings & glossary
          </Link>
        </nav>
        {apiConnected === true ? (
          <span className="flex items-center gap-2 text-xs font-medium text-emerald-400">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            Backend Connected (FastAPI)
          </span>
        ) : apiConnected === false ? (
          <span className="flex items-center gap-2 text-xs text-rose-400">
            <AlertCircle size={15} />
            Backend Disconnected (Port 8000)
          </span>
        ) : (
          <span className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock size={15} className="animate-spin" />
            Checking connection...
          </span>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-6 py-12">
        <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-3 text-xs uppercase tracking-wider text-primary">
              VisionGuard / Reliability workspace
            </p>
            <h1 className="text-3xl font-medium">{title}</h1>
          </div>
          <Link to="/" className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft size={15} />
            Back to journey
          </Link>
        </div>

        {apiConnected === false && (
          <div
            role="status"
            className="mb-8 flex gap-3 rounded-lg border border-rose-500/30 bg-rose-950/20 p-4 text-sm text-rose-200"
          >
            <AlertCircle className="shrink-0 text-rose-400" size={18} />
            <div>
              <p className="font-medium">Backend service unreachable</p>
              <p className="mt-1 text-xs text-rose-300/80">
                Ensure the FastAPI backend is running at{" "}
                <code className="font-mono bg-black/40 px-1 py-0.5 rounded">{api.getBaseUrl()}</code>.
                Start with:{" "}
                <code className="font-mono bg-black/40 px-1 py-0.5 rounded">
                  uvicorn backend.app.main:app --port 8000
                </code>
              </p>
            </div>
          </div>
        )}

        {children}
      </main>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Status Badge Component
// -----------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "COMPLETED":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-950/60 border border-emerald-500/30 px-2.5 py-1 text-xs font-medium text-emerald-400">
          <CheckCircle2 size={12} /> Completed
        </span>
      );
    case "RUNNING":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-950/60 border border-blue-500/30 px-2.5 py-1 text-xs font-medium text-blue-400 animate-pulse">
          <Clock size={12} className="animate-spin" /> Running
        </span>
      );
    case "QUEUED":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-950/60 border border-amber-500/30 px-2.5 py-1 text-xs font-medium text-amber-400">
          <Clock size={12} /> Queued
        </span>
      );
    case "FAILED":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-950/60 border border-rose-500/30 px-2.5 py-1 text-xs font-medium text-rose-400">
          <XCircle size={12} /> Failed
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-muted/50 px-2.5 py-1 text-xs text-muted-foreground">
          {status}
        </span>
      );
  }
}

// -----------------------------------------------------------------------------
// Dashboard View
// -----------------------------------------------------------------------------

export function Dashboard() {
  const [runs, setRuns] = useState<RunResponse[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = () => {
    setLoading(true);
    setError(null);
    api
      .getRuns(20, 0)
      .then((res) => {
        setRuns(res.runs);
        setTotal(res.total);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.detail || err.message || "Failed to load runs");
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const latestRun = runs[0];
  const completedRunsCount = runs.filter((r) => r.status === "COMPLETED").length;

  return (
    <Workspace title="Model Reliability Overview">
      <div className="mb-10 flex flex-wrap items-center justify-between gap-6">
        <p className="max-w-xl text-muted-foreground">
          Benchmark Faster R-CNN object-detection consistency against synthetic image corruptions.
          Investigate degradation and failure evidence with reproducible evaluation runs.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" size="sm" onClick={fetchRuns} disabled={loading} className="gap-2">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            Refresh
          </Button>
          <Button asChild>
            <Link to="/new">
              <Plus size={16} className="mr-1" />
              New Evaluation
            </Link>
          </Button>
        </div>
      </div>

      <div className="mb-12 grid gap-5 sm:grid-cols-3">
        <div className="border-t border-border py-6">
          <p className="text-sm text-muted-foreground">Total evaluations</p>
          <p className="my-2 text-3xl font-semibold">{loading ? "..." : total}</p>
          <p className="text-xs text-muted-foreground">{completedRunsCount} completed runs</p>
        </div>
        <div className="border-t border-border py-6">
          <p className="text-sm text-muted-foreground">Latest evaluation status</p>
          <div className="my-3">
            {loading ? (
              <p className="text-2xl text-muted-foreground">Loading...</p>
            ) : latestRun ? (
              <StatusBadge status={latestRun.status} />
            ) : (
              <p className="text-2xl text-muted-foreground">None</p>
            )}
          </div>
          <p className="text-xs text-muted-foreground font-mono">
            {latestRun ? latestRun.model_id : "No evaluations recorded"}
          </p>
        </div>
        <div className="border-t border-border py-6">
          <p className="text-sm text-muted-foreground">Evaluator engine</p>
          <p className="my-2 text-xl font-medium">Faster R-CNN ResNet-50</p>
          <p className="text-xs text-muted-foreground">Torchvision Detector & Matching Engine</p>
        </div>
      </div>

      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-xl font-medium">Recent evaluations</h2>
        <span className="text-xs text-muted-foreground font-mono">PostgreSQL / Neon database</span>
      </div>

      {error ? (
        <div className="rounded-lg border border-destructive/40 bg-card p-8 text-center text-muted-foreground">
          <AlertCircle className="mx-auto mb-3 text-destructive" size={24} />
          <p className="font-medium text-foreground">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchRuns} className="mt-4">
            Try again
          </Button>
        </div>
      ) : loading && runs.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-12 text-center text-muted-foreground">
          <Clock className="mx-auto mb-3 animate-spin text-primary" size={24} />
          <p>Loading evaluation runs from backend...</p>
        </div>
      ) : runs.length === 0 ? (
        <div className="rounded-lg border border-border bg-card p-16 text-center text-muted-foreground">
          <FileSearch className="mx-auto mb-4 text-muted-foreground/60" size={32} />
          <p className="text-base text-foreground font-medium">No evaluations yet</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Configure corruptions and launch your first evaluation run against the demo dataset.
          </p>
          <Button asChild className="mt-6">
            <Link to="/new">Launch First Evaluation</Link>
          </Button>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[700px] text-left text-sm">
            <thead className="border-b border-border bg-muted/20 text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-normal">Run ID</th>
                <th className="px-4 py-3 font-normal">Created date</th>
                <th className="px-4 py-3 font-normal">Dataset</th>
                <th className="px-4 py-3 font-normal">Model</th>
                <th className="px-4 py-3 font-normal">Status</th>
                <th className="px-4 py-3 font-normal text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {runs.map((run) => (
                <tr key={run.run_id} className="hover:bg-muted/10 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-primary">
                    <Link to="/runs/$id" params={{ id: run.run_id }} className="hover:underline">
                      {run.run_id.slice(0, 18)}...
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(run.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">{run.dataset_id}</td>
                  <td className="px-4 py-3 font-mono text-xs">{run.model_id}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button asChild variant="ghost" size="sm">
                        <Link to="/runs/$id" params={{ id: run.run_id }}>
                          Details
                        </Link>
                      </Button>
                      {run.status === "COMPLETED" && (
                        <Button asChild variant="outline" size="sm">
                          <Link to="/runs/$id_/failures" params={{ id: run.run_id }}>
                            Failures
                          </Link>
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Workspace>
  );
}

// -----------------------------------------------------------------------------
// New Evaluation View
// -----------------------------------------------------------------------------

export function NewEvaluation() {
  const navigate = useNavigate();

  const [models, setModels] = useState<string[]>([]);
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState<boolean>(true);

  const [selectedModel, setSelectedModel] = useState<string>("");
  const [selectedDataset, setSelectedDataset] = useState<string>("");

  // Corruption selection state: map of kind -> array of selected severities
  const [corruptionsState, setCorruptionsState] = useState<Record<CorruptionKind, number[]>>({
    blur: [1],
    low_light: [],
    gaussian_noise: [],
  });

  const [scoreThreshold, setScoreThreshold] = useState<string>("0.5");
  const [matchIouThreshold, setMatchIouThreshold] = useState<string>("0.5");
  const [seed, setSeed] = useState<string>("42");

  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([api.getModels(), api.getDatasets()])
      .then(([modelsRes, datasetsRes]) => {
        if (!mounted) return;
        setModels(modelsRes.models);
        if (modelsRes.models.length > 0) {
          setSelectedModel(modelsRes.models[0]);
        }
        setDatasets(datasetsRes.datasets);
        const supported = datasetsRes.datasets.find((d) => d.supported);
        if (supported) {
          setSelectedDataset(supported.id);
        } else if (datasetsRes.datasets.length > 0) {
          setSelectedDataset(datasetsRes.datasets[0].id);
        }
        setLoadingCatalog(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setErrorMsg(err.detail || err.message || "Failed to load model and dataset catalog");
        setLoadingCatalog(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const toggleSeverity = (kind: CorruptionKind, sev: number) => {
    setCorruptionsState((prev) => {
      const current = prev[kind] || [];
      const updated = current.includes(sev)
        ? current.filter((s) => s !== sev)
        : [...current, sev].sort();
      return { ...prev, [kind]: updated };
    });
  };

  const applyPreset = (preset: "blur1" | "noise2" | "all1") => {
    if (preset === "blur1") {
      setCorruptionsState({ blur: [1], low_light: [], gaussian_noise: [] });
    } else if (preset === "noise2") {
      setCorruptionsState({ blur: [], low_light: [], gaussian_noise: [2] });
    } else if (preset === "all1") {
      setCorruptionsState({ blur: [1], low_light: [1], gaussian_noise: [1] });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    // Build corruptions list
    const activeCorruptions = (
      Object.entries(corruptionsState) as [CorruptionKind, number[]][]
    )
      .filter(([_, sevs]) => sevs.length > 0)
      .map(([kind, severities]) => ({
        kind,
        severities,
      }));

    if (activeCorruptions.length === 0) {
      setErrorMsg("Please select at least one corruption condition (e.g. Blur severity 1).");
      return;
    }

    const score = Number.parseFloat(scoreThreshold);
    if (Number.isNaN(score) || score < 0 || score > 1) {
      setErrorMsg("Score threshold must be between 0.0 and 1.0");
      return;
    }

    const iou = Number.parseFloat(matchIouThreshold);
    if (Number.isNaN(iou) || iou <= 0 || iou > 1) {
      setErrorMsg("Match IoU threshold must be greater than 0.0 and up to 1.0");
      return;
    }

    const seedNum = Number.parseInt(seed, 10) || 42;

    const req: RunCreateRequest = {
      model_id: selectedModel,
      dataset_id: selectedDataset,
      corruptions: activeCorruptions,
      seed: seedNum,
      score_threshold: score,
      match_iou_threshold: iou,
    };

    setSubmitting(true);
    try {
      const res = await api.createRun(req);
      navigate({ to: "/runs/$id", params: { id: res.run_id } });
    } catch (err: any) {
      setErrorMsg(err.detail || err.message || "Failed to submit evaluation run");
      setSubmitting(false);
    }
  };

  const currentDatasetObj = datasets.find((d) => d.id === selectedDataset);

  const selectedConditionsCount = Object.values(corruptionsState).reduce(
    (acc, sevs) => acc + sevs.length,
    0
  );

  return (
    <Workspace title="New Evaluation">
      <div className="grid gap-12 lg:grid-cols-[1.3fr_1fr]">
        <form className="space-y-9" onSubmit={handleSubmit}>
          {errorMsg && (
            <div className="rounded-lg border border-destructive/40 bg-card p-4 text-sm text-rose-300">
              <div className="flex items-center gap-2">
                <AlertCircle size={16} className="text-destructive shrink-0" />
                <p className="font-medium">{errorMsg}</p>
              </div>
            </div>
          )}

          {/* 01 / Dataset Selection */}
          <fieldset>
            <legend className="mb-4 text-xl font-medium">01 / Dataset</legend>
            <label className="vg-label">
              <span>Benchmark dataset</span>
              <select
                className="vg-input"
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value)}
                disabled={loadingCatalog || datasets.length === 0}
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.image_count} images)
                  </option>
                ))}
              </select>
            </label>
            {currentDatasetObj && (
              <div className="mt-3 rounded-md border border-border bg-card p-4 text-xs text-muted-foreground space-y-1.5">
                <p className="font-medium text-foreground">{currentDatasetObj.description}</p>
                <div className="flex items-center gap-4 pt-1">
                  <span>Images: <strong>{currentDatasetObj.image_count}</strong></span>
                  <span>Ground truth: <strong>{currentDatasetObj.has_ground_truth ? "Yes" : "None (Reference-free)"}</strong></span>
                  <span className="text-emerald-400 font-medium">Supported</span>
                </div>
              </div>
            )}
          </fieldset>

          {/* 02 / Model Selection */}
          <fieldset>
            <legend className="mb-4 text-xl font-medium">02 / Model</legend>
            <label className="vg-label">
              <span>Detection model</span>
              <select
                className="vg-input"
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={loadingCatalog || models.length === 0}
              >
                {models.map((m) => (
                  <option key={m} value={m}>
                    {m} (Torchvision Faster R-CNN)
                  </option>
                ))}
              </select>
            </label>
            <p className="mt-2 text-xs text-muted-foreground">
              Evaluator executes pre-trained PyTorch weights with COCO category taxonomy.
            </p>
          </fieldset>

          {/* 03 / Corruptions */}
          <fieldset>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <legend className="text-xl font-medium">03 / Corruptions</legend>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => applyPreset("blur1")}>
                  Preset: Blur s1
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => applyPreset("noise2")}>
                  Preset: Noise s2
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => applyPreset("all1")}>
                  Preset: All s1
                </Button>
              </div>
            </div>

            <div className="space-y-4 rounded-lg border border-border bg-card p-5">
              {(
                [
                  { kind: "blur" as CorruptionKind, label: "Gaussian blur", desc: "Simulates optical blur / out-of-focus optics" },
                  { kind: "low_light" as CorruptionKind, label: "Low light / Darkening", desc: "Simulates twilight, tunnel, or nighttime illumination" },
                  { kind: "gaussian_noise" as CorruptionKind, label: "Gaussian noise", desc: "Simulates sensor noise under low SNR" },
                ] as const
              ).map(({ kind, label, desc }) => {
                const activeSeverities = corruptionsState[kind] || [];
                return (
                  <div key={kind} className="border-b border-border/50 pb-4 last:border-b-0 last:pb-0">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-sm">{label}</p>
                        <p className="text-xs text-muted-foreground">{desc}</p>
                      </div>
                      <div className="flex gap-1.5">
                        {[1, 2, 3].map((sev) => {
                          const isSelected = activeSeverities.includes(sev);
                          return (
                            <button
                              key={sev}
                              type="button"
                              onClick={() => toggleSeverity(kind, sev)}
                              className={`rounded px-2.5 py-1 text-xs font-mono transition-colors ${
                                isSelected
                                  ? "bg-primary text-primary-foreground font-semibold"
                                  : "border border-border bg-muted/30 text-muted-foreground hover:bg-muted"
                              }`}
                            >
                              Severity {sev}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Selected: <strong>{selectedConditionsCount}</strong> corruption condition(s).
            </p>
          </fieldset>

          {/* 04 / Thresholds & Seed */}
          <fieldset>
            <legend className="mb-4 text-xl font-medium">04 / Thresholds & Matching</legend>
            <div className="grid gap-4 sm:grid-cols-3">
              <label className="vg-label">
                <span>Confidence threshold τ</span>
                <input
                  className="vg-input"
                  type="number"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={scoreThreshold}
                  onChange={(e) => setScoreThreshold(e.target.value)}
                />
                <span className="text-xs text-muted-foreground">Filter weak predictions</span>
              </label>

              <label className="vg-label">
                <span>Match IoU threshold θ</span>
                <input
                  className="vg-input"
                  type="number"
                  min="0.05"
                  max="1.0"
                  step="0.05"
                  value={matchIouThreshold}
                  onChange={(e) => setMatchIouThreshold(e.target.value)}
                />
                <span className="text-xs text-muted-foreground">Spatial matching overlap</span>
              </label>

              <label className="vg-label">
                <span>Random seed</span>
                <input
                  className="vg-input"
                  type="number"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                />
                <span className="text-xs text-muted-foreground">Reproducible noise</span>
              </label>
            </div>
          </fieldset>

          <Button type="submit" disabled={submitting || loadingCatalog || selectedConditionsCount === 0} className="w-full sm:w-auto gap-2">
            {submitting ? (
              <>
                <Clock size={16} className="animate-spin" />
                Dispatching Run...
              </>
            ) : (
              <>
                <Play size={16} />
                Launch Evaluation
              </>
            )}
          </Button>
        </form>

        {/* Configuration preview panel */}
        <aside className="border-t border-border pt-6 lg:border-t-0 lg:border-l lg:pl-8 lg:sticky lg:top-8 lg:self-start">
          <h2 className="mb-5 text-xl font-medium">Evaluation manifest</h2>
          <div className="rounded-lg border border-border bg-card p-5 space-y-4 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">Model</dt>
              <dd className="mt-1 font-mono font-medium">{selectedModel || "None"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Dataset</dt>
              <dd className="mt-1 font-mono">{selectedDataset || "None"}</dd>
              <dd className="text-xs text-muted-foreground mt-0.5">
                {currentDatasetObj?.image_count || 10} images (Reference-free mode)
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Conditions to evaluate</dt>
              <dd className="mt-1">
                {selectedConditionsCount === 0 ? (
                  <span className="text-rose-400">None selected</span>
                ) : (
                  <ul className="list-disc pl-4 text-xs space-y-1 mt-1 font-mono">
                    {(Object.entries(corruptionsState) as [CorruptionKind, number[]][])
                      .filter(([_, sevs]) => sevs.length > 0)
                      .map(([kind, sevs]) => (
                        <li key={kind}>
                          {kind}: severities [{sevs.join(", ")}]
                        </li>
                      ))}
                  </ul>
                )}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Matching parameters</dt>
              <dd className="mt-1 text-xs font-mono">
                score_threshold: {scoreThreshold} | iou: {matchIouThreshold} | seed: {seed}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Execution target</dt>
              <dd className="mt-1 text-xs text-emerald-400 font-medium">
                Decoupled Worker via FastAPI / Neon PostgreSQL
              </dd>
            </div>
          </div>
        </aside>
      </div>
    </Workspace>
  );
}

// -----------------------------------------------------------------------------
// Run Details View (/runs/$id)
// -----------------------------------------------------------------------------

export function RunDetails({ id }: { id: string }) {
  const [run, setRun] = useState<RunResponse | null>(null);
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let timer: any = null;
    let cancelled = false;

    const poll = async () => {
      try {
        const runData = await api.getRun(id);
        if (cancelled) return;
        setRun(runData);

        if (runData.status === "COMPLETED") {
          const [repData, artData] = await Promise.all([
            api.getReport(id).catch(() => null),
            api.getArtifacts(id).catch(() => null),
          ]);
          if (cancelled) return;
          if (repData) setReport(repData.report);
          if (artData) setArtifacts(artData.artifacts);
          setLoading(false);
          return;
        }

        if (runData.status === "FAILED") {
          setLoading(false);
          return;
        }

        // If QUEUED or RUNNING, keep polling every 2 seconds
        setLoading(false);
        timer = setTimeout(poll, 2000);
      } catch (err: any) {
        if (cancelled) return;
        setError(err.detail || err.message || "Failed to load run details");
        setLoading(false);
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  // Aggregate metrics from completed conditions
  const conditions = report?.conditions || [];
  let totalCleanDetections = 0;
  let totalMatchedDetections = 0;
  let totalClassFlips = 0;
  let iouSum = 0;
  let iouCount = 0;

  conditions.forEach((c) => {
    totalCleanDetections += c.metrics.n_clean || 0;
    totalMatchedDetections += c.metrics.n_matched || 0;
    totalClassFlips += c.metrics.n_class_flips || 0;
    if (c.metrics.mean_matched_iou != null) {
      iouSum += c.metrics.mean_matched_iou;
      iouCount += 1;
    }
  });

  const overallRetention =
    totalCleanDetections > 0 ? totalMatchedDetections / totalCleanDetections : null;
  const overallClassConsistency =
    totalMatchedDetections > 0
      ? (totalMatchedDetections - totalClassFlips) / totalMatchedDetections
      : null;
  const overallMeanIoU = iouCount > 0 ? iouSum / iouCount : null;

  return (
    <Workspace title="Evaluation Details">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <p className="font-mono text-sm text-muted-foreground break-all">
          Run ID: <span className="text-foreground">{id}</span>
        </p>
        <div className="flex items-center gap-3">
          <Button asChild variant="outline" size="sm">
            <Link to="/runs/$id_/failures" params={{ id }}>
              <Eye size={14} className="mr-1.5" />
              Visual Evidence & Failures
            </Link>
          </Button>
        </div>
      </div>

      {/* Status Bar */}
      <div className="mb-8 rounded-lg border border-border bg-card p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs text-muted-foreground">Status</p>
            <div className="mt-1.5 flex items-center gap-3">
              <StatusBadge status={run?.status || "LOADING"} />
              <span className="text-sm text-muted-foreground">
                {run?.status === "QUEUED" && "Waiting in job queue for evaluator worker..."}
                {run?.status === "RUNNING" && "Evaluating Faster R-CNN on clean and corrupted images..."}
                {run?.status === "COMPLETED" && "Inference and matching complete. Evidence ready."}
                {run?.status === "FAILED" && (run.error_message || "Evaluation encountered an error.")}
              </span>
            </div>
          </div>
          <div className="text-right text-xs text-muted-foreground">
            <p>Created: {run ? new Date(run.created_at).toLocaleTimeString() : "..."}</p>
            {run?.finished_at && <p>Finished: {new Date(run.finished_at).toLocaleTimeString()}</p>}
          </div>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-destructive/40 bg-card p-8 text-center text-rose-300">
          <AlertCircle className="mx-auto mb-3 text-destructive" size={24} />
          <p className="font-medium">{error}</p>
        </div>
      ) : run?.status === "QUEUED" || run?.status === "RUNNING" ? (
        <div className="rounded-lg border border-border bg-card p-16 text-center text-muted-foreground">
          <Clock className="mx-auto mb-4 animate-spin text-primary" size={32} />
          <h3 className="text-lg font-medium text-foreground">
            {run.status === "QUEUED" ? "Evaluation Queued" : "Evaluation in Progress"}
          </h3>
          <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
            The worker process is executing the Faster R-CNN evaluation pipeline and matching detection boxes.
            This view automatically updates upon completion.
          </p>
        </div>
      ) : report ? (
        <div className="space-y-10">
          {/* Reference-free disclosure note */}
          <div className="rounded-lg border border-border/80 bg-muted/20 p-4 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">Reference-Free Consistency Evaluation</p>
            <p className="mt-1">
              This dataset (<code className="font-mono">{report.dataset.dataset_id}</code>) is evaluated
              without ground-truth annotations. Metrics quantify how stably baseline clean detections are
              retained under image corruptions.
            </p>
          </div>

          {/* Metric KPI cards */}
          <div className="grid gap-5 sm:grid-cols-4">
            <div className="rounded-lg border border-border bg-card p-5">
              <p className="text-xs text-muted-foreground">Detection Retention</p>
              <p className="my-2 text-3xl font-semibold text-primary">
                {overallRetention != null ? `${(overallRetention * 100).toFixed(1)}%` : "N/A"}
              </p>
              <p className="text-xs text-muted-foreground">Baseline detections preserved</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-5">
              <p className="text-xs text-muted-foreground">Class Consistency</p>
              <p className="my-2 text-3xl font-semibold">
                {overallClassConsistency != null ? `${(overallClassConsistency * 100).toFixed(1)}%` : "N/A"}
              </p>
              <p className="text-xs text-muted-foreground">Matched objects retaining class</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-5">
              <p className="text-xs text-muted-foreground">Mean Matched IoU</p>
              <p className="my-2 text-3xl font-semibold">
                {overallMeanIoU != null ? overallMeanIoU.toFixed(3) : "N/A"}
              </p>
              <p className="text-xs text-muted-foreground">Spatial box alignment</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-5">
              <p className="text-xs text-muted-foreground">Total Failures</p>
              <p className="my-2 text-3xl font-semibold text-rose-400">
                {report.failures?.length || 0}
              </p>
              <p className="text-xs text-muted-foreground">Missing or flipped detections</p>
            </div>
          </div>

          {/* Conditions Breakdown Table */}
          <div>
            <h2 className="mb-4 text-xl font-medium">Condition breakdown</h2>
            <div className="overflow-x-auto rounded-lg border border-border bg-card">
              <table className="w-full min-w-[700px] text-left text-sm">
                <thead className="border-b border-border bg-muted/20 text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3 font-normal">Condition</th>
                    <th className="px-4 py-3 font-normal">Severity</th>
                    <th className="px-4 py-3 font-normal">Clean dets</th>
                    <th className="px-4 py-3 font-normal">Corrupted dets</th>
                    <th className="px-4 py-3 font-normal">Matched</th>
                    <th className="px-4 py-3 font-normal">Retention</th>
                    <th className="px-4 py-3 font-normal">Class flips</th>
                    <th className="px-4 py-3 font-normal">Mean IoU</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {conditions.map((cond, idx) => (
                    <tr key={idx} className="hover:bg-muted/10 transition-colors">
                      <td className="px-4 py-3 font-medium capitalize">{cond.corruption.replace("_", " ")}</td>
                      <td className="px-4 py-3 font-mono text-xs">Level {cond.severity}</td>
                      <td className="px-4 py-3">{cond.metrics.n_clean}</td>
                      <td className="px-4 py-3">{cond.metrics.n_corrupted}</td>
                      <td className="px-4 py-3">{cond.metrics.n_matched}</td>
                      <td className="px-4 py-3 font-semibold text-primary">
                        {cond.metrics.detection_retention != null
                          ? `${(cond.metrics.detection_retention * 100).toFixed(1)}%`
                          : "N/A"}
                      </td>
                      <td className="px-4 py-3 text-rose-300">{cond.metrics.n_class_flips}</td>
                      <td className="px-4 py-3 font-mono text-xs">
                        {cond.metrics.mean_matched_iou != null
                          ? cond.metrics.mean_matched_iou.toFixed(3)
                          : "N/A"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Configuration Manifest */}
          <details className="rounded-lg border border-border bg-card p-5">
            <summary className="cursor-pointer text-sm font-medium">Manifest & Configuration JSON</summary>
            <pre className="mt-4 overflow-x-auto rounded bg-black/40 p-4 font-mono text-xs text-muted-foreground">
              {JSON.stringify(report.config, null, 2)}
            </pre>
          </details>
        </div>
      ) : null}
    </Workspace>
  );
}

// -----------------------------------------------------------------------------
// Failure Analysis & Visual Evidence View (/runs/$id/failures)
// -----------------------------------------------------------------------------

export function Failures({ id }: { id: string }) {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedImageId, setSelectedImageId] = useState<string>("");
  const [selectedConditionIdx, setSelectedConditionIdx] = useState<number>(0);

  const cleanCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const corruptedCanvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([api.getReport(id), api.getArtifacts(id)])
      .then(([repRes, artRes]) => {
        if (!mounted) return;
        setReport(repRes.report);
        setArtifacts(artRes.artifacts);

        const firstImage = repRes.report.clean_predictions?.[0]?.image_id;
        if (firstImage) setSelectedImageId(firstImage);

        setLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.detail || err.message || "Failed to load artifacts and report");
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [id]);

  // Redraw canvas bounding boxes whenever selection changes
  useEffect(() => {
    if (!report || !selectedImageId) return;

    const currentCondition = report.conditions[selectedConditionIdx];
    const corruptionKind = currentCondition?.corruption || "blur";
    const severity = currentCondition?.severity || 1;

    // 1. Draw Clean Image with Green Detections
    const cleanImg = new window.Image();
    cleanImg.crossOrigin = "anonymous";
    cleanImg.src = api.getArtifactUrl(id, `clean_${selectedImageId}`);
    cleanImg.onload = () => {
      const canvas = cleanCanvasRef.current;
      if (!canvas) return;
      canvas.width = cleanImg.naturalWidth;
      canvas.height = cleanImg.naturalHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      ctx.drawImage(cleanImg, 0, 0);

      // Find predictions
      const cleanData = report.clean_predictions.find((p) => p.image_id === selectedImageId);
      const preds = cleanData?.predictions || [];

      preds.forEach((p) => {
        const [x1, y1, x2, y2] = p.bbox_xyxy;
        ctx.strokeStyle = "#10b981"; // Emerald green
        ctx.lineWidth = 3;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

        // Label tag
        const label = `${p.class_name || `Class ${p.class_id}`}: ${(p.confidence * 100).toFixed(0)}%`;
        ctx.font = "bold 14px sans-serif";
        const textWidth = ctx.measureText(label).width;
        ctx.fillStyle = "rgba(16, 185, 129, 0.85)";
        ctx.fillRect(x1, Math.max(0, y1 - 20), textWidth + 8, 20);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(label, x1 + 4, Math.max(15, y1 - 5));
      });
    };

    // 2. Draw Corrupted Image with Orange/Red Detections
    const corrImg = new window.Image();
    corrImg.crossOrigin = "anonymous";
    corrImg.src = api.getArtifactUrl(
      id,
      `corrupted_${corruptionKind}_${severity}_${selectedImageId}`
    );
    corrImg.onload = () => {
      const canvas = corruptedCanvasRef.current;
      if (!canvas) return;
      canvas.width = corrImg.naturalWidth;
      canvas.height = corrImg.naturalHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      ctx.drawImage(corrImg, 0, 0);

      // Find corrupted predictions
      const perImageCond = currentCondition?.per_image.find(
        (pi) => pi.image_id === selectedImageId
      );
      const corrPreds = perImageCond?.predictions || [];

      corrPreds.forEach((p) => {
        const [x1, y1, x2, y2] = p.bbox_xyxy;
        ctx.strokeStyle = "#f97316"; // Orange
        ctx.lineWidth = 3;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

        const label = `${p.class_name || `Class ${p.class_id}`}: ${(p.confidence * 100).toFixed(0)}%`;
        ctx.font = "bold 14px sans-serif";
        const textWidth = ctx.measureText(label).width;
        ctx.fillStyle = "rgba(249, 115, 22, 0.85)";
        ctx.fillRect(x1, Math.max(0, y1 - 20), textWidth + 8, 20);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(label, x1 + 4, Math.max(15, y1 - 5));
      });
    };
  }, [report, selectedImageId, selectedConditionIdx, id]);

  const imagesList = report?.clean_predictions.map((p) => p.image_id) || [];
  const conditionsList = report?.conditions || [];
  const activeCondition = conditionsList[selectedConditionIdx];

  const filteredFailures = (report?.failures || []).filter(
    (f) =>
      (!selectedImageId || f.image_id === selectedImageId) &&
      (!activeCondition ||
        (f.corruption === activeCondition.corruption &&
          f.severity === activeCondition.severity))
  );

  return (
    <Workspace title="Failure Analysis & Visual Evidence">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <Button asChild variant="outline" size="sm">
          <Link to="/runs/$id" params={{ id }}>
            <ArrowLeft size={14} className="mr-1.5" />
            Back to evaluation details
          </Link>
        </Button>
        <span className="text-xs text-muted-foreground font-mono">Run: {id.slice(0, 16)}...</span>
      </div>

      {loading ? (
        <div className="rounded-lg border border-border bg-card p-16 text-center text-muted-foreground">
          <Clock className="mx-auto mb-3 animate-spin text-primary" size={28} />
          <p>Loading visual artifacts and evaluation coordinates...</p>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/40 bg-card p-8 text-center text-rose-300">
          <AlertCircle className="mx-auto mb-3 text-destructive" size={24} />
          <p className="font-medium">{error}</p>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Controls */}
          <div className="grid gap-4 sm:grid-cols-2 rounded-lg border border-border bg-card p-4">
            <label className="vg-label">
              <span>Select benchmark image</span>
              <select
                className="vg-input"
                value={selectedImageId}
                onChange={(e) => setSelectedImageId(e.target.value)}
              >
                {imagesList.map((img) => (
                  <option key={img} value={img}>
                    {img}
                  </option>
                ))}
              </select>
            </label>
            <label className="vg-label">
              <span>Select corruption condition</span>
              <select
                className="vg-input"
                value={selectedConditionIdx}
                onChange={(e) => setSelectedConditionIdx(Number(e.target.value))}
              >
                {conditionsList.map((c, i) => (
                  <option key={i} value={i}>
                    {c.corruption.replace("_", " ")} (Severity {c.severity})
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* Visual Canvas Comparison */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Clean Baseline Canvas */}
            <section className="rounded-lg border border-border bg-card p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-medium text-sm flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                  Clean Baseline Image (Predictions)
                </h3>
                <span className="text-xs text-muted-foreground font-mono">Green: Clean Detections</span>
              </div>
              <div className="overflow-hidden rounded border border-border/60 bg-black/50 aspect-video flex items-center justify-center">
                <canvas ref={cleanCanvasRef} className="max-h-full max-w-full object-contain" />
              </div>
            </section>

            {/* Corrupted Condition Canvas */}
            <section className="rounded-lg border border-border bg-card p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-medium text-sm flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-primary" />
                  Corrupted Condition Image (Predictions)
                </h3>
                <span className="text-xs text-muted-foreground font-mono">Orange: Corrupted Detections</span>
              </div>
              <div className="overflow-hidden rounded border border-border/60 bg-black/50 aspect-video flex items-center justify-center">
                <canvas ref={corruptedCanvasRef} className="max-h-full max-w-full object-contain" />
              </div>
            </section>
          </div>

          <div className="text-xs text-muted-foreground">
            <p>
              * <strong>Client-side Canvas Overlays:</strong> Detections are rendered dynamically on
              browser Canvas from exact bounding box coordinates (<code className="font-mono">bbox_xyxy</code>)
              and confidence scores returned in the evaluation report.
            </p>
          </div>

          {/* Failure Records Table */}
          <div>
            <h3 className="mb-3 font-medium text-lg">Failure evidence records</h3>
            {filteredFailures.length === 0 ? (
              <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground text-sm">
                No failure events recorded for this image and condition.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-border bg-card">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-border bg-muted/20 text-muted-foreground">
                    <tr>
                      <th className="px-4 py-3 font-normal">Image</th>
                      <th className="px-4 py-3 font-normal">Failure Type</th>
                      <th className="px-4 py-3 font-normal">Clean Score</th>
                      <th className="px-4 py-3 font-normal">Corrupted Score</th>
                      <th className="px-4 py-3 font-normal">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filteredFailures.map((f, i) => (
                      <tr key={i} className="hover:bg-muted/10 transition-colors">
                        <td className="px-4 py-3 font-mono text-xs">{f.image_id}</td>
                        <td className="px-4 py-3">
                          <span className="inline-flex rounded bg-rose-950/60 border border-rose-500/30 px-2 py-0.5 text-xs text-rose-300">
                            {f.failure_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-xs">
                          {f.clean_prediction?.confidence != null
                            ? `${(f.clean_prediction.confidence * 100).toFixed(0)}%`
                            : "N/A"}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs">
                          {f.corrupted_prediction?.confidence != null
                            ? `${(f.corrupted_prediction.confidence * 100).toFixed(0)}%`
                            : "N/A"}
                        </td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">
                          {f.details || "Detection degraded under corruption condition."}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </Workspace>
  );
}

// -----------------------------------------------------------------------------
// Settings & Glossary View
// -----------------------------------------------------------------------------

const glossary: [string, string, string][] = [
  ["Retention", "CONSISTENCY", "The fraction of clean-baseline detections successfully retained after image corruption."],
  ["Loss rate", "CONSISTENCY", "The fraction of baseline detections completely lost under a corruption condition."],
  ["IoU", "CONSISTENCY", "Intersection over Union measures spatial overlap between clean and corrupted predicted boxes."],
  ["Confidence delta", "CONSISTENCY", "The difference in prediction confidence scores between matched detections."],
  ["Class flip", "CONSISTENCY", "A matched detection whose predicted class changes under corruption."],
  ["Reference-free", "METHODOLOGY", "Evaluates relative degradation of predictions without requiring ground-truth annotations."],
  ["Precision", "GROUND TRUTH", "The proportion of predicted detections that are correct against ground-truth labels."],
  ["Recall", "GROUND TRUTH", "The proportion of labeled ground-truth objects detected by the model."],
  ["mAP", "GROUND TRUTH", "Mean average precision summarizes detection performance against ground-truth annotations."],
];

export function Settings() {
  return (
    <Workspace title="Settings & Glossary">
      <div className="grid gap-12 lg:grid-cols-[1fr_1.6fr]">
        <section>
          <h2 className="mb-6 text-xl font-medium">Evaluation service parameters</h2>
          <div className="space-y-4 text-sm">
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground">Backend API</p>
              <p className="mt-1 font-mono text-sm">{api.getBaseUrl()}</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground">Database</p>
              <p className="mt-1 text-sm font-medium">PostgreSQL (Neon Serverless)</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground">Supported Models</p>
              <p className="mt-1 font-mono text-xs">fasterrcnn_resnet50_fpn, fasterrcnn_resnet50_fpn_v2</p>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground">Registered Benchmark Datasets</p>
              <p className="mt-1 font-mono text-xs">visionguard_demo (10 images, reference-free)</p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="mb-5 text-xl font-medium">Metric glossary</h2>
          <div className="divide-y divide-border">
            {glossary.map(([name, type, meaning]) => (
              <details key={name} className="py-4">
                <summary className="cursor-pointer text-base font-medium flex items-center justify-between">
                  <span>{name}</span>
                  <span className="text-[10px] tracking-wider rounded border border-primary/40 bg-primary/10 px-2 py-0.5 text-primary">
                    {type}
                  </span>
                </summary>
                <p className="mt-2 text-sm text-muted-foreground">{meaning}</p>
              </details>
            ))}
          </div>

          <h2 className="mb-4 mt-10 text-xl font-medium">Methodology limitations</h2>
          <ul className="space-y-2.5 text-sm text-muted-foreground list-disc pl-5">
            <li>Consistency across corruptions does not establish ground-truth accuracy.</li>
            <li>Ground-truth evaluation metrics (e.g. mAP, precision, recall) require human-labeled bounding box annotations.</li>
            <li>Single-image or few-sample evaluations provide qualitative diagnostics; robust benchmarking requires statistical aggregation.</li>
            <li>Overlays are rendered client-side on canvas using detection coordinates from the JSON report.</li>
          </ul>
        </section>
      </div>
    </Workspace>
  );
}