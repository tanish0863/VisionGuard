import { Link } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";
import { Activity, ArrowLeft, ArrowRight, FileSearch, Plus, Upload, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CORRUPTIONS, validateThreshold } from "@/lib/evaluation-config";

export function Workspace({ title, children }: { title: string; children: ReactNode }) {
  return <div className="vg-workspace min-h-screen bg-background text-foreground">
    <header className="vg-header flex flex-wrap items-center justify-between gap-5 border-b border-border px-6 py-5">
      <Link to="/" className="flex items-center gap-2 text-xl font-semibold"><Activity className="text-primary" />VisionGuard <span className="font-normal text-muted-foreground">AI</span></Link>
      <nav aria-label="Workspace navigation" className="flex flex-wrap items-center gap-5 text-sm">
        <Link to="/dashboard" activeProps={{ className: "text-primary" }}>Overview</Link>
        <Link to="/new" activeProps={{ className: "text-primary" }}>New evaluation</Link>
        <Link to="/settings" activeProps={{ className: "text-primary" }}>Settings & glossary</Link>
      </nav>
      <span className="flex items-center gap-2 text-xs text-muted-foreground"><AlertCircle size={15} />Model unavailable</span>
    </header>
    <main className="mx-auto max-w-6xl px-6 py-12">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-4"><div><p className="mb-3 text-xs uppercase text-primary">VisionGuard / Reliability workspace</p><h1 className="text-3xl font-medium">{title}</h1></div><Link to="/" className="flex items-center gap-2 text-sm text-muted-foreground"><ArrowLeft size={15} />Back to journey</Link></div>
      <div role="status" className="mb-8 flex gap-3 border-y border-border py-4 text-sm text-muted-foreground"><AlertCircle className="shrink-0 text-primary" size={18} /><p>Evaluation service not connected. No API contracts, models, datasets or results have been supplied. Execution and saved settings are unavailable.</p></div>
      {children}
    </main>
  </div>;
}

export function Dashboard() {
  return <Workspace title="Model Reliability Overview">
    <div className="mb-10 flex flex-wrap items-center justify-between gap-6"><p className="max-w-xl text-muted-foreground">Compare object-detection behavior on clean and degraded images, then investigate failures with evaluation evidence.</p><div className="flex flex-wrap gap-3"><Button variant="outline" disabled>Run Sample Evaluation</Button><Button asChild><Link to="/new"><Plus />New Evaluation</Link></Button></div></div>
    <div className="mb-12 grid gap-5 sm:grid-cols-3">{["Total runs", "Latest gate verdict", "Latest mean relative retention"].map(label => <div key={label} className="border-t border-border py-6"><p className="text-sm text-muted-foreground">{label}</p><p className="my-3 text-3xl">N/A</p><p className="text-xs text-muted-foreground">Evaluation service unavailable</p></div>)}</div>
    <h2 className="mb-5 text-xl">Recent evaluations</h2>
    <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="border-y border-border text-muted-foreground"><tr>{["Run ID", "Created date", "Dataset", "Model", "Status", "Gate verdict", "Mean retention"].map(x => <th key={x} className="px-3 py-4 font-normal">{x}</th>)}</tr></thead><tbody><tr><td colSpan={7} className="py-16 text-center text-muted-foreground"><FileSearch className="mx-auto mb-4" /><p>Run history unavailable</p><p className="mt-2 text-xs">Connect the evaluation service to retrieve your runs.</p></td></tr></tbody></table></div>
  </Workspace>;
}

export function NewEvaluation() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string>();
  const [selected, setSelected] = useState<string[]>([]);
  const [confidence, setConfidence] = useState("");
  const [iou, setIou] = useState("");
  useEffect(() => { if (!file || !file.type.startsWith("image/")) { setPreview(undefined); return; } const url = URL.createObjectURL(file); setPreview(url); return () => URL.revokeObjectURL(url); }, [file]);
  return <Workspace title="New Evaluation"><div className="grid gap-12 lg:grid-cols-[1.2fr_1fr]">
    <form className="space-y-9" onSubmit={e => e.preventDefault()}>
      <fieldset><legend className="mb-4 text-xl">01 / Dataset</legend><label className="flex cursor-pointer flex-col items-center gap-3 rounded-lg border border-dashed border-border bg-card p-8 text-center"><Upload className="text-primary" /><span>Select a local image for preview</span><input aria-label="Dataset preview image" type="file" accept="image/*" onChange={e => setFile(e.target.files?.[0] ?? null)} className="max-w-full text-xs" /><span className="text-xs text-muted-foreground">Not uploaded. Dataset formats and limits require the service contract.</span></label></fieldset>
      <fieldset><legend className="mb-4 text-xl">02 / Model</legend><label className="vg-label">Detection model<select disabled className="vg-input"><option>No models available</option></select></label></fieldset>
      <fieldset><legend className="mb-4 text-xl">03 / Corruptions</legend><div className="flex flex-col gap-4">{CORRUPTIONS.map(c => <label key={c} className="flex items-center gap-3"><input type="checkbox" checked={selected.includes(c)} onChange={e => setSelected(prev => e.target.checked ? [...prev, c] : prev.filter(x => x !== c))} />{c}</label>)}</div><p className="mt-4 text-xs text-muted-foreground">Severity options and presets unavailable until the service is connected. Evaluations require 1–24 conditions.</p></fieldset>
      <fieldset><legend className="mb-4 text-xl">04 / Thresholds</legend><div className="grid gap-4 sm:grid-cols-2">{[{ label: "Confidence threshold τ", value: confidence, set: setConfidence }, { label: "IoU threshold θ", value: iou, set: setIou }].map(x => <label key={x.label} className="vg-label">{x.label}<input className="vg-input" type="number" min="0" max="1" step="0.01" value={x.value} onChange={e => x.set(e.target.value)} placeholder="Service default unavailable" />{x.value && !validateThreshold(Number(x.value)) && <span role="alert" className="text-primary">Enter a value between 0 and 1.</span>}</label>)}</div></fieldset>
      <fieldset><legend className="mb-4 text-xl">05 / Gate rules & execution</legend><p className="text-sm text-muted-foreground">Supported gate rules, random-seed defaults and image-persistence policies have not been supplied.</p></fieldset>
      <Button disabled><Activity />Launch Evaluation</Button>
    </form>
    <aside className="border-t border-border pt-6 lg:sticky lg:top-8 lg:self-start"><h2 className="mb-5 text-xl">Configuration preview</h2>{preview ? <img src={preview} alt="Selected dataset preview, without detection results" className="mb-6 max-h-80 w-full rounded-lg object-contain" /> : <div className="mb-6 flex aspect-video items-center justify-center border border-border bg-card text-muted-foreground"><FileSearch size={32} /></div>}<dl className="space-y-4 text-sm"><div><dt className="text-muted-foreground">Local file</dt><dd className="mt-1 break-all">{file?.name ?? "Not selected"}</dd></div><div><dt className="text-muted-foreground">Corruptions to configure</dt><dd className="mt-1">{selected.join(", ") || "None selected"}</dd></div><div><dt className="text-muted-foreground">Labels</dt><dd className="mt-1">Unknown — not evaluated</dd></div><div><dt className="text-muted-foreground">Execution</dt><dd className="mt-1">Unavailable — no evaluation service</dd></div></dl></aside>
  </div></Workspace>;
}

const glossary = [
  ["Retention", "CONSISTENCY", "The fraction of clean-baseline detections retained after corruption."],
  ["Loss rate", "CONSISTENCY", "The fraction of baseline detections lost under a condition."],
  ["IoU", "CONSISTENCY", "Intersection over Union measures how much two bounding boxes overlap."],
  ["Confidence delta", "CONSISTENCY", "The change in prediction confidence between matched detections."],
  ["Class flip", "CONSISTENCY", "A matched detection changes its predicted class."],
  ["Precision", "GROUND TRUTH", "The proportion of predicted detections that are correct against labels."],
  ["Recall", "GROUND TRUTH", "The proportion of labeled objects detected by the model."],
  ["F1", "GROUND TRUTH", "The harmonic mean of precision and recall."],
  ["mAP", "GROUND TRUTH", "Mean average precision summarizes detection performance against labels."],
];
export function Settings() {
  return <Workspace title="Settings & Glossary"><div className="grid gap-12 lg:grid-cols-[1fr_1.6fr]"><section><h2 className="mb-6 text-xl">Evaluation defaults</h2><p className="mb-6 text-sm text-muted-foreground">Defaults are not available from a connected service.</p>{["Confidence threshold τ", "IoU threshold θ", "Random seed", "Persistence policy"].map(x => <label key={x} className="vg-label mb-5">{x}<input className="vg-input" disabled placeholder="Unavailable" /></label>)}<h2 className="mb-4 mt-10 text-xl">Model information</h2><p className="text-sm text-muted-foreground">No model information supplied. Model readiness and mock-model status are unknown.</p></section><section><h2 className="mb-5 text-xl">Metric glossary</h2>{glossary.map(([name, type, meaning]) => <details key={name} className="border-b border-border py-4"><summary className="cursor-pointer text-base">{name}<span className="ml-3 text-[10px] text-primary">{type}</span></summary><p className="mt-3 text-sm text-muted-foreground">{meaning}</p></details>)}<h2 className="mb-4 mt-10 text-xl">Methodology limitations</h2><ul className="space-y-3 text-sm text-muted-foreground"><li>Consistency does not establish ground-truth accuracy.</li><li>Ground-truth metrics require labels.</li><li>Fewer than 30 samples warrant a small-sample warning; a single image is not representative.</li><li>Retention is undefined when the baseline has zero detections.</li><li>Persisted images depend on the service’s artifact policy.</li><li>A preset is a convenience, not a validated scenario.</li></ul></section></div></Workspace>;
}

export function RunDetails({ id }: { id: string }) {
  return <Workspace title="Evaluation Details"><p className="mb-8 break-all font-mono text-sm text-muted-foreground">Run / {id}</p><div className="flex flex-wrap justify-between gap-4 border-y border-border py-6"><div><p className="text-sm text-muted-foreground">Run status</p><p className="mt-2 text-xl">Unavailable</p></div><div><p className="text-sm text-muted-foreground">Gate verdict</p><p className="mt-2 text-xl">N/A</p></div><Button asChild variant="outline"><Link to="/runs/$id/failures" params={{ id }}>Failure Analysis<ArrowRight /></Link></Button></div><h2 className="mb-6 mt-10 text-xl">Evaluation evidence</h2><p className="text-muted-foreground">The run and report cannot be retrieved without the evaluation service. No verdict, charts, condition metrics or progress can be shown.</p><details className="mt-10 border-y border-border py-5"><summary className="cursor-pointer">Manifest & configuration</summary><p className="mt-4 text-sm text-muted-foreground">No manifest supplied for this run.</p></details></Workspace>;
}

export function Failures({ id }: { id: string }) {
  return <Workspace title="Failure Analysis"><Button asChild variant="outline" className="mb-8"><Link to="/runs/$id" params={{ id }}><ArrowLeft />Back to evaluation</Link></Button><div className="mb-10 grid gap-4 sm:grid-cols-4">{["Corruption", "Severity", "Failure type", "Image"].map(x => <label key={x} className="vg-label">{x}<select disabled className="vg-input"><option>Unavailable</option></select></label>)}</div><p className="mb-8 text-xs text-muted-foreground">Ranking score — not a metric.</p><div className="grid gap-6 sm:grid-cols-2">{["Clean (baseline)", "Degraded"].map(x => <section key={x}><h2 className="mb-4 text-lg">{x}</h2><div className="flex aspect-video items-center justify-center border border-border bg-card text-sm text-muted-foreground">Artifact unavailable</div></section>)}</div><p className="mt-8 text-muted-foreground">Failure records and images have not been retrieved. Detection overlays and comparison require actual run artifacts.</p></Workspace>;
}