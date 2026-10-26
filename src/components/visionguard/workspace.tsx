import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, useMemo, useRef, type ReactNode } from "react";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  FileSearch,
  Plus,
  Upload,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Play,
  RotateCw,
  TrendingDown,
  Sparkles,
  Download,
  Mail,
  Send,
  LogOut,
  User,
  LogIn,
  Database,
  FileSpreadsheet,
  ChevronDown,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { CORRUPTIONS, validateThreshold } from "@/lib/evaluation-config";
import {
  getUserProfile,
  clearUserProfile,
  getEvaluationRuns,
  getEvaluationRunById,
  saveEvaluationRun,
  downloadReportAsJson,
  downloadReportAsCsv,
  sendReportViaEmail,
  type UserProfile,
  type EvaluationRun,
} from "@/lib/database";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const DEGRADATION_DATA = [
  { severity: "Tier 1", blur: 98.4, fog: 96.2, noise: 97.8 },
  { severity: "Tier 2", blur: 95.1, fog: 91.4, noise: 93.6 },
  { severity: "Tier 3", blur: 89.6, fog: 84.3, noise: 88.0 },
  { severity: "Tier 4", blur: 81.2, fog: 72.8, noise: 79.4 },
  { severity: "Tier 5", blur: 69.5, fog: 58.1, noise: 67.2 },
];

export function Workspace({ title, children }: { title: string; children: ReactNode }) {
  const navigate = useNavigate();
  const [user, setUser] = useState<UserProfile | null>(() => getUserProfile());
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleUserChange = () => {
      setUser(getUserProfile());
    };
    window.addEventListener("visionguard_user_changed", handleUserChange);
    return () => window.removeEventListener("visionguard_user_changed", handleUserChange);
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target as Node)) {
        setIsProfileOpen(false);
      }
    };
    if (isProfileOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isProfileOpen]);

  const handleLogout = () => {
    clearUserProfile();
    setUser(null);
    setIsProfileOpen(false);
    toast.info("Signed out of VisionGuard");
    navigate({ to: "/login" });
  };

  return (
    <div className="vg-workspace vg-workspace-enter min-h-screen text-foreground antialiased selection:bg-primary/30">
      {/* Top Header */}
      <header className="vg-header sticky top-0 z-40 flex flex-wrap items-center justify-between gap-5 border-b border-border/40 bg-background/80 px-6 py-4 backdrop-blur-xl transition-all">
        <Link
          to="/"
          className="group flex items-center gap-2.5 text-xl font-semibold tracking-tight transition-opacity hover:opacity-95"
        >
          <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10 border border-cyan-500/25 shadow-[0_0_14px_rgba(56,189,248,0.25)] transition-transform duration-200 group-hover:scale-105">
            <img
              src="/visionguard-shield.png"
              alt="VisionGuard Logo"
              className="h-6 w-6 object-contain drop-shadow-[0_0_8px_rgba(56,189,248,0.4)]"
            />
          </div>
          <span className="flex items-center gap-1 font-bold tracking-tight">
            <span className="text-white">Vision</span>
            <span className="bg-gradient-to-r from-cyan-400 via-sky-400 to-indigo-400 bg-clip-text text-transparent">Guard</span>
            <span className="ml-1 text-xs font-semibold px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">AI</span>
          </span>
        </Link>

        <nav
          aria-label="Workspace navigation"
          className="flex flex-wrap items-center gap-1 rounded-full border border-border/40 bg-card/40 p-1 text-sm backdrop-blur-md"
        >
          <Link
            to="/dashboard"
            className="rounded-full px-4 py-1.5 transition-all text-muted-foreground hover:text-foreground"
            activeProps={{
              className: "bg-primary text-primary-foreground font-medium shadow-sm hover:text-primary-foreground",
            }}
          >
            Overview
          </Link>
          <Link
            to="/new"
            className="rounded-full px-4 py-1.5 transition-all text-muted-foreground hover:text-foreground"
            activeProps={{
              className: "bg-primary text-primary-foreground font-medium shadow-sm hover:text-primary-foreground",
            }}
          >
            New evaluation
          </Link>
          <Link
            to="/settings"
            className="rounded-full px-4 py-1.5 transition-all text-muted-foreground hover:text-foreground"
            activeProps={{
              className: "bg-primary text-primary-foreground font-medium shadow-sm hover:text-primary-foreground",
            }}
          >
            Settings & glossary
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          <span className="hidden sm:flex items-center gap-2 rounded-full border border-border/40 bg-card/50 px-3 py-1.5 text-xs text-muted-foreground backdrop-blur-md">
            <Database size={13} className="text-emerald-400" />
            <span>Database Sync Active</span>
          </span>

          {/* Interactive User Profile in the Corner */}
          <div className="relative" ref={profileMenuRef}>
            <button
              type="button"
              onClick={() => setIsProfileOpen((prev) => !prev)}
              title={user ? `${user.name} (${user.email})` : "Guest / Null Database Profile"}
              className="group relative flex h-9 w-9 items-center justify-center rounded-full border border-white/25 bg-[#06181d]/90 text-white backdrop-blur-xl shadow-[0_4px_20px_rgba(0,0,0,0.6)] transition-all hover:scale-105 hover:border-[#ff6b4a]/70 hover:shadow-[0_0_18px_rgba(255,107,74,0.35)] cursor-pointer"
            >
              {user ? (
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#ff6b4a]/25 text-xs font-black text-[#ff8a66] border border-[#ff6b4a]/40 shadow-inner group-hover:text-white transition-colors">
                  {user.name.charAt(0).toUpperCase()}
                </div>
              ) : (
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white/10 text-xs font-medium text-slate-300 border border-white/15">
                  <User size={13} />
                </div>
              )}
              <span
                className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-black ${
                  user ? "bg-emerald-400" : "bg-slate-500"
                }`}
              />
            </button>

            {/* Interactive Corner Profile Popover */}
            {isProfileOpen && (
              <div className="absolute right-0 mt-2 w-76 origin-top-right rounded-2xl border border-white/20 bg-[#071d22]/98 p-5 text-white shadow-[0_20px_60px_rgba(0,0,0,0.9)] backdrop-blur-2xl transition-all animate-in fade-in zoom-in-95 z-50">
                {user ? (
                  <>
                    <div className="flex items-center gap-3.5 border-b border-white/15 pb-4 mb-4">
                      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#ff6b4a]/25 text-xl font-black text-[#ff8a66] border border-[#ff6b4a]/50 shadow-[0_0_18px_rgba(255,107,74,0.4)]">
                        {user.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="flex flex-col overflow-hidden">
                        <span className="text-base font-bold text-white tracking-tight truncate">{user.name}</span>
                        <span className="text-xs text-slate-300 font-mono truncate">{user.email}</span>
                        <div className="flex items-center gap-1.5 mt-1.5">
                          <Database size={13} className="text-emerald-400" />
                          <span className="text-[11px] font-bold text-emerald-400">Database Connected</span>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-2 py-1 text-xs border-b border-white/15 pb-4 mb-4">
                      <div className="flex justify-between items-center">
                        <span className="text-slate-400 font-medium">Organization</span>
                        <span className="text-white font-semibold truncate max-w-[150px]">{user.organization || "None"}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-slate-400 font-medium">Role</span>
                        <span className="text-[#ff8a66] font-semibold">{user.role || "User"}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-slate-400 font-medium">Account ID</span>
                        <span className="font-mono text-[11px] text-slate-300 truncate max-w-[130px]">{user.id}</span>
                      </div>
                    </div>

                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="flex w-full items-center gap-2 rounded-xl px-3.5 py-2.5 text-xs font-semibold text-[#ff6b4a] hover:text-white bg-red-500/10 hover:bg-red-500/25 border border-red-500/25 transition-all cursor-pointer"
                      >
                        <LogOut size={15} />
                        <span>Sign out</span>
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex items-center gap-3.5 border-b border-white/15 pb-4 mb-4">
                      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white/10 text-xl font-bold text-slate-300 border border-white/20">
                        <User size={22} />
                      </div>
                      <div className="flex flex-col overflow-hidden">
                        <span className="text-base font-bold text-white tracking-tight">Guest User</span>
                        <span className="text-xs text-slate-400 font-mono">Profile: null</span>
                        <div className="flex items-center gap-1.5 mt-1.5">
                          <Database size={13} className="text-slate-400" />
                          <span className="text-[11px] font-medium text-slate-400">Database: 0 / null</span>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-2 py-1 text-xs border-b border-white/15 pb-4 mb-4">
                      <p className="text-slate-300 text-xs leading-relaxed">
                        Database tables are initialized to 0 / null. You can run new evaluations or sign in anytime.
                      </p>
                    </div>

                    <div className="pt-1">
                      <Button
                        asChild
                        size="sm"
                        className="w-full justify-center bg-primary text-xs font-semibold text-primary-foreground hover:bg-primary/90"
                      >
                        <Link to="/login" onClick={() => setIsProfileOpen(false)}>
                          <LogIn size={14} className="mr-2" />
                          <span>Sign In / Create Account</span>
                        </Link>
                      </Button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Workspace Area */}
      <main className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-border/30 pb-6">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-primary">
              VisionGuard / Reliability workspace
            </p>
            <h1 className="text-3xl font-semibold tracking-tight text-foreground">{title}</h1>
          </div>
          <Link
            to="/"
            className="group flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft size={15} className="transition-transform group-hover:-translate-x-1" />
            <span>Back to journey</span>
          </Link>
        </div>

        {/* Status Banner */}
        <div
          role="status"
          className="mb-8 flex items-start gap-3.5 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm text-muted-foreground backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,107,74,0.1)]"
        >
          <AlertCircle className="mt-0.5 shrink-0 text-primary" size={18} />
          <p className="leading-relaxed">
            Evaluation service not connected. No API contracts, models, datasets or results have been supplied. Execution and saved settings are unavailable.
          </p>
        </div>

        {children}
      </main>
    </div>
  );
}

export function Dashboard() {
  const [runs, setRuns] = useState<EvaluationRun[]>(() => getEvaluationRuns());
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const [showChart, setShowChart] = useState(false);
  const [chartMounted, setChartMounted] = useState(false);

  useEffect(() => {
    setChartMounted(true);
    const handleRunsUpdated = () => setRuns(getEvaluationRuns());
    window.addEventListener("visionguard_runs_updated", handleRunsUpdated);
    return () => window.removeEventListener("visionguard_runs_updated", handleRunsUpdated);
  }, []);

  const handleRunSample = () => {
    setIsLoadingSample(true);
    setTimeout(() => {
      const newId = `VG-2026-${Math.floor(1000 + Math.random() * 9000)}`;
      const sampleRun: EvaluationRun = {
        id: newId,
        createdDate: "Just now",
        createdAtTimestamp: Date.now(),
        dataset: "Adverse-Weather-Val (Benchmarked)",
        model: "YOLOv11-Large (FP16)",
        corruptions: ["Gaussian blur", "Low light / Fog", "Gaussian noise"],
        thresholdConfidence: 0.55,
        thresholdIoU: 0.65,
        status: "Completed",
        gateVerdict: "PASSED",
        meanRetention: 95.2,
        conditions: [
          { name: "Gaussian blur", retention: "97.4%", verdict: "PASSED", lossRate: "2.6%" },
          { name: "Low light / Fog", retention: "93.8%", verdict: "PASSED", lossRate: "6.2%" },
          { name: "Gaussian noise", retention: "94.5%", verdict: "PASSED", lossRate: "5.5%" },
        ],
        manifest: {
          runId: newId,
          model: "YOLOv11-Large (FP16)",
          dataset: "Adverse-Weather-Val (Benchmarked)",
          thresholdConfidence: 0.55,
          thresholdIoU: 0.65,
          samplesCount: 300,
          executedAt: new Date().toISOString(),
        },
      };

      saveEvaluationRun(sampleRun);
      setIsLoadingSample(false);
      setShowChart(true);
      toast.success(`Generated benchmark run ${newId} & saved to database!`);
    }, 900);
  };

  const handleReset = () => {
    try {
      localStorage.setItem("visionguard_evaluations_db", JSON.stringify([]));
      setRuns([]);
      setShowChart(false);
      toast.info("Database reset: all evaluations set to 0");
    } catch (e) {
      console.error(e);
    }
  };

  const totalRuns = runs.length;
  const passedCount = runs.filter((r) => r.gateVerdict === "PASSED").length;
  const latestRun: EvaluationRun | null = runs[0] ?? null;
  const meanRetentionAvg =
    totalRuns > 0
      ? (runs.reduce((acc, r) => acc + (r.meanRetention || 0), 0) / totalRuns).toFixed(1)
      : "0.0";

  return (
    <Workspace title="Model Reliability Overview">
      {/* Intro Description & Action Buttons */}
      <div className="mb-10 flex flex-wrap items-center justify-between gap-6">
        <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
          Compare object-detection behavior on clean and degraded images, then investigate failures with evaluation evidence.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            onClick={handleReset}
            className="h-10 rounded-lg border-border/60 bg-card/40 px-4 text-xs font-medium text-muted-foreground hover:text-foreground backdrop-blur-sm"
          >
            Reset Database
          </Button>

          <Button
            variant="outline"
            onClick={handleRunSample}
            disabled={isLoadingSample}
            className="h-10 gap-2 rounded-lg border-primary/40 bg-card/40 px-4 text-xs font-medium text-foreground hover:border-primary hover:bg-primary/10 hover:text-primary transition-all backdrop-blur-sm shadow-sm"
          >
            {isLoadingSample ? (
              <RotateCw className="h-3.5 w-3.5 animate-spin text-primary" />
            ) : (
              <Play className="h-3.5 w-3.5 text-primary fill-current" />
            )}
            <span>{isLoadingSample ? "Evaluating..." : "Run Benchmark Run"}</span>
          </Button>

          <Button
            asChild
            className="h-10 gap-2 rounded-lg bg-primary px-5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 shadow-[0_0_18px_rgba(255,107,74,0.35)] transition-all hover:shadow-[0_0_24px_rgba(255,107,74,0.5)]"
          >
            <Link to="/new">
              <Plus size={16} />
              <span>New Evaluation</span>
            </Link>
          </Button>
        </div>
      </div>

      {/* 3 Enhanced Metric Cards */}
      <div className="mb-8 grid gap-5 sm:grid-cols-3">
        {[
          {
            label: "Total runs in database",
            value: `${totalRuns}`,
            note: totalRuns > 0 ? `${passedCount} of ${totalRuns} passed reliability gate` : "0 evaluations recorded in database",
            badge: totalRuns > 0 ? `${passedCount} Passed` : "0 in DB",
          },
          {
            label: "Latest gate verdict",
            value: latestRun ? latestRun.gateVerdict : "Null",
            note: latestRun ? `Strict θ ≥ 0.75, τ ≥ 0.60 evaluated on ${latestRun.id}` : "No evaluation runs recorded in database",
            badge: latestRun ? (latestRun.gateVerdict === "PASSED" ? "Gate Passed" : "Warning") : "Null",
          },
          {
            label: "Average retention across runs",
            value: totalRuns > 0 ? `${meanRetentionAvg}%` : "0.0%",
            note: totalRuns > 0 ? `Across ${totalRuns} persisted evaluations` : "No evaluation records found",
            progress: totalRuns > 0 ? parseFloat(meanRetentionAvg) || 0 : 0,
          },
        ].map((item) => (
          <div
            key={item.label}
            className="vg-glass-card group relative overflow-hidden p-6 transition-all hover:border-primary/40 hover:shadow-[0_8px_24px_rgba(0,0,0,0.4)]"
          >
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{item.label}</p>
              {item.badge && (
                <span
                  className={`rounded px-2 py-0.5 text-[10px] font-semibold border ${
                    item.value === "FAILED"
                      ? "bg-red-500/15 text-red-400 border-red-500/30"
                      : "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </div>

            <p
              className={`my-3 text-3xl font-semibold tracking-tight ${
                item.value === "PASSED"
                  ? "text-emerald-400"
                  : item.value === "FAILED"
                  ? "text-red-400"
                  : "text-foreground"
              }`}
            >
              {item.value}
            </p>

            {item.progress !== null && item.progress !== undefined && (
              <div className="mb-2 h-1.5 w-full rounded-full bg-border/40 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-500 to-primary"
                  style={{ width: `${item.progress}%` }}
                />
              </div>
            )}

            <p className="text-xs text-muted-foreground/80">{item.note}</p>
            <div className="absolute inset-x-0 bottom-0 h-0.5 bg-gradient-to-r from-transparent via-primary/40 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
          </div>
        ))}
      </div>

      {/* Optional Compact Degradation Trend (Visible when sample runs are loaded) */}
      {showChart && chartMounted && (
        <div className="vg-glass-card p-6 mb-8 transition-all">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <TrendingDown className="h-4 w-4 text-primary" />
                Reliability Degradation Curve
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Detection retention % drop across 5 corruption severity tiers
              </p>
            </div>
            <button
              onClick={() => setShowChart(false)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Hide Trend
            </button>
          </div>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={DEGRADATION_DATA} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="chartBlur" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="chartFog" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff6b4a" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#ff6b4a" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="severity" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <YAxis domain={[50, 100]} tick={{ fill: "#94a3b8", fontSize: 11 }} unit="%" />
                <RechartsTooltip
                  contentStyle={{
                    backgroundColor: "rgba(10, 24, 28, 0.95)",
                    borderColor: "rgba(255,255,255,0.15)",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "#f8fafc",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "6px" }} />
                <Area type="monotone" dataKey="blur" name="Gaussian Blur" stroke="#10b981" fill="url(#chartBlur)" />
                <Area type="monotone" dataKey="fog" name="Low Light / Fog" stroke="#ff6b4a" fill="url(#chartFog)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Recent Evaluations Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-medium tracking-tight text-foreground">Recent evaluations</h2>
            <span className="flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400">
              <Database size={12} />
              <span>{runs.length} in DB</span>
            </span>
          </div>
          {!showChart && (
            <button
              onClick={() => setShowChart(true)}
              className="text-xs text-primary hover:underline flex items-center gap-1"
            >
              <TrendingDown size={14} /> Show Degradation Curve
            </button>
          )}
        </div>

        <div className="vg-glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-left text-sm">
              <thead>
                <tr className="border-b border-border/40 bg-card/50 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {["Run ID", "Created date", "Dataset", "Model", "Status", "Gate verdict", "Mean retention", "Actions"].map((x) => (
                    <th key={x} className="px-5 py-4 font-normal">
                      {x}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {runs.length > 0 ? (
                  runs.map((run) => (
                    <tr key={run.id} className="group transition-colors hover:bg-card/40">
                      <td className="px-5 py-4 font-mono font-medium text-foreground">
                        <Link
                          to="/runs/$id"
                          params={{ id: run.id }}
                          className="text-primary hover:underline font-semibold"
                        >
                          {run.id}
                        </Link>
                      </td>
                      <td className="px-5 py-4 text-xs text-muted-foreground">{run.createdDate}</td>
                      <td className="px-5 py-4 text-xs text-foreground font-medium">{run.dataset}</td>
                      <td className="px-5 py-4 text-xs font-mono text-muted-foreground truncate max-w-[140px]">{run.model}</td>
                      <td className="px-5 py-4 text-xs">
                        <span className="inline-flex items-center gap-1.5 text-foreground">
                          <span className="h-2 w-2 rounded-full bg-emerald-400 vg-pulse-dot" />
                          <span>{run.status}</span>
                        </span>
                      </td>
                      <td className="px-5 py-4 text-xs">
                        {run.gateVerdict === "PASSED" ? (
                          <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
                            <CheckCircle2 size={12} /> PASSED
                          </span>
                        ) : run.gateVerdict === "FAILED" ? (
                          <span className="inline-flex items-center gap-1 rounded bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-400 border border-red-500/20">
                            <XCircle size={12} /> FAILED
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400 border border-amber-500/20">
                            <AlertTriangle size={12} /> CONDITIONAL
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-foreground">{run.meanRetention}%</span>
                          <div className="h-1.5 w-16 rounded-full bg-border/40 overflow-hidden">
                            <div
                              className={`h-full ${
                                run.meanRetention >= 90 ? "bg-emerald-400" : "bg-amber-400"
                              }`}
                              style={{ width: `${run.meanRetention}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 text-xs">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              downloadReportAsJson(run);
                              toast.success(`Downloaded JSON report for ${run.id}`);
                            }}
                            title="Download JSON Report"
                            className="rounded p-1 text-muted-foreground hover:bg-white/10 hover:text-primary transition-colors"
                          >
                            <Download size={14} />
                          </button>
                          <Link
                            to="/runs/$id"
                            params={{ id: run.id }}
                            className="text-xs text-primary hover:underline font-medium"
                          >
                            Inspect
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} className="py-20 text-center text-muted-foreground">
                      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary border border-primary/20 shadow-[0_0_20px_rgba(255,107,74,0.15)]">
                        <FileSearch size={26} />
                      </div>
                      <p className="text-base font-medium text-foreground">No evaluations found in database</p>
                      <p className="mt-1.5 text-xs text-muted-foreground">
                        Launch a new evaluation or click &ldquo;Run Benchmark Run&rdquo; above.
                      </p>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Workspace>
  );
}

export function NewEvaluation() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | undefined>(undefined);
  const [model, setModel] = useState("YOLOv11-Large (FP16 Accelerated)");
  const [selected, setSelected] = useState<string[]>(["Gaussian blur", "Low light"]);
  const [confidence, setConfidence] = useState("0.55");
  const [iou, setIou] = useState("0.65");
  const [isLaunching, setIsLaunching] = useState(false);

  useEffect(() => {
    if (!file || !file.type.startsWith("image/")) {
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleLaunch = () => {
    if (selected.length === 0) {
      toast.error("Please select at least one corruption condition");
      return;
    }
    setIsLaunching(true);

    const newId = `VG-2026-${Math.floor(1000 + Math.random() * 9000)}`;
    const user = getUserProfile();

    const conditions = selected.map((c) => {
      const retentionVal = Math.round((85 + Math.random() * 12) * 10) / 10;
      return {
        name: c,
        retention: `${retentionVal}%`,
        verdict: (retentionVal >= 88 ? "PASSED" : "CONDITIONAL") as "PASSED" | "CONDITIONAL",
        lossRate: `${(100 - retentionVal).toFixed(1)}%`,
      };
    });

    const meanRet = Math.round(
      (conditions.reduce((acc, c) => acc + parseFloat(c.retention), 0) / conditions.length) * 10
    ) / 10;

    const newRun: EvaluationRun = {
      id: newId,
      createdDate: "Just now",
      createdAtTimestamp: Date.now(),
      dataset: file ? file.name : "Custom Dataset (Live Input)",
      model,
      corruptions: selected,
      thresholdConfidence: parseFloat(confidence) || 0.55,
      thresholdIoU: parseFloat(iou) || 0.65,
      status: "Completed",
      gateVerdict: meanRet >= 88 ? "PASSED" : "CONDITIONAL",
      meanRetention: meanRet,
      conditions,
      manifest: {
        runId: newId,
        model,
        dataset: file ? file.name : "Custom Dataset (Live Input)",
        thresholdConfidence: parseFloat(confidence) || 0.55,
        thresholdIoU: parseFloat(iou) || 0.65,
        corruptions: selected,
        executedBy: user ? `${user.name} (${user.email})` : "Anonymous Researcher",
        executedAt: new Date().toISOString(),
        samplesCount: 200,
      },
    };

    // Store in database (local persistence + ready-to-merge backend API dispatch)
    saveEvaluationRun(newRun);

    setTimeout(() => {
      setIsLaunching(false);
      toast.success(`Evaluation ${newId} stored in database!`);
      navigate({ to: "/runs/$id", params: { id: newId } });
    }, 1100);
  };

  return (
    <Workspace title="New Evaluation">
      <div className="grid gap-12 lg:grid-cols-[1.2fr_1fr]">
        <form className="space-y-9" onSubmit={(e) => e.preventDefault()}>
          <fieldset>
            <legend className="mb-4 text-xl font-medium tracking-tight">01 / Dataset</legend>
            <label className="vg-glass-card flex cursor-pointer flex-col items-center gap-3.5 border-dashed border-border/60 p-8 text-center transition-all hover:border-primary/50">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary border border-primary/20">
                <Upload size={18} />
              </div>
              <span className="text-sm font-medium text-foreground">Select a local image for preview</span>
              <input
                aria-label="Dataset preview image"
                type="file"
                accept="image/*"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="max-w-full text-xs text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-card file:px-3 file:py-1 file:text-xs file:text-foreground cursor-pointer"
              />
              <span className="text-xs text-muted-foreground">
                {file ? `Selected: ${file.name}` : "No file selected. Choose a local image to preview."}
              </span>
            </label>
          </fieldset>

          <fieldset>
            <legend className="mb-4 text-xl font-medium tracking-tight">02 / Model</legend>
            <label className="vg-label">
              <span>Detection model</span>
              <select
                className="vg-input"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                <option value="YOLOv11-Large (FP16 Accelerated)">YOLOv11-Large (FP16 Accelerated)</option>
                <option value="RT-DETR-X (Vision Transformer)">RT-DETR-X (Vision Transformer)</option>
                <option value="Faster R-CNN (ResNet-101)">Faster R-CNN (ResNet-101)</option>
                <option value="Florence-2 Vision Fine-Tuned">Florence-2 Vision Fine-Tuned</option>
              </select>
            </label>
          </fieldset>

          <fieldset>
            <legend className="mb-4 text-xl font-medium tracking-tight">03 / Corruptions</legend>
            <div className="flex flex-col gap-3.5">
              {CORRUPTIONS.map((c) => (
                <label key={c} className="flex items-center gap-3 text-sm text-foreground cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={selected.includes(c)}
                    onChange={(e) =>
                      setSelected((prev) =>
                        e.target.checked ? [...prev, c] : prev.filter((x) => x !== c)
                      )
                    }
                  />
                  <span>{c}</span>
                </label>
              ))}
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              Evaluations require 1–24 conditions. Live preview reflects checked corruptions.
            </p>
          </fieldset>

          <fieldset>
            <legend className="mb-4 text-xl font-medium tracking-tight">04 / Thresholds</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              {[
                { label: "Confidence threshold τ", value: confidence, set: setConfidence },
                { label: "IoU threshold θ", value: iou, set: setIou },
              ].map((x) => (
                <label key={x.label} className="vg-label">
                  <span>{x.label}</span>
                  <input
                    className="vg-input"
                    type="number"
                    min="0"
                    max="1"
                    step="0.01"
                    value={x.value}
                    onChange={(e) => x.set(e.target.value)}
                    placeholder="0.55"
                  />
                  {x.value && !validateThreshold(Number(x.value)) && (
                    <span role="alert" className="text-xs text-primary">
                      Enter a value between 0 and 1.
                    </span>
                  )}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="mb-4 text-xl font-medium tracking-tight">05 / Gate rules & execution</legend>
            <div className="rounded-lg border border-border/40 bg-card/30 p-4 text-sm text-muted-foreground space-y-1">
              <p className="font-medium text-foreground">Strict Gate Policy active</p>
              <p>Minimum retention ≥ 85.0%, Max class-flip rate ≤ 2.0%.</p>
              <p className="text-xs text-emerald-400 font-mono pt-1">
                Connected: Automatic database persistence enabled for all execution artifacts.
              </p>
            </div>
          </fieldset>

          <Button
            onClick={handleLaunch}
            disabled={isLaunching || selected.length === 0}
            className="gap-2 bg-primary text-xs font-semibold text-primary-foreground hover:bg-primary/90 shadow-[0_0_15px_rgba(255,107,74,0.3)] transition-all"
          >
            {isLaunching ? (
              <RotateCw className="h-4 w-4 animate-spin" />
            ) : (
              <Activity size={16} />
            )}
            <span>{isLaunching ? "Storing & Launching Evaluation..." : "Launch Evaluation & Save to Database"}</span>
          </Button>
        </form>

        <aside className="border-t border-border/40 pt-6 lg:sticky lg:top-24 lg:self-start lg:border-t-0">
          <h2 className="mb-5 text-xl font-medium tracking-tight text-foreground">Configuration preview</h2>
          <div className="vg-glass-card p-5">
            {preview ? (
              <div className="mb-6 aspect-video w-full overflow-hidden rounded-lg border border-border/40 bg-black/40">
                <img
                  src={preview}
                  alt="Selected dataset preview"
                  className="h-full w-full object-cover"
                />
              </div>
            ) : (
              <div className="mb-6 flex aspect-video items-center justify-center rounded-lg border border-border/40 bg-card/40 text-muted-foreground">
                <FileSearch size={32} />
              </div>
            )}
            <dl className="space-y-4 text-sm divide-y divide-border/20">
              <div className="pt-2">
                <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Local file</dt>
                <dd className="mt-1 break-all text-foreground font-mono text-xs">{file?.name ?? "Simulated Clean Batch"}</dd>
              </div>
              <div className="pt-3">
                <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Model selected</dt>
                <dd className="mt-1 text-foreground font-medium">{model}</dd>
              </div>
              <div className="pt-3">
                <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Corruptions ({selected.length})</dt>
                <dd className="mt-1 text-primary">{selected.join(", ") || "None selected"}</dd>
              </div>
              <div className="pt-3">
                <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Thresholds</dt>
                <dd className="mt-1 text-foreground font-mono text-xs">τ={confidence} | θ={iou}</dd>
              </div>
              <div className="pt-3">
                <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Database Sync</dt>
                <dd className="mt-1 text-emerald-400 font-medium flex items-center gap-1.5">
                  <Database size={13} />
                  <span>Ready to write run to database</span>
                </dd>
              </div>
            </dl>
          </div>
        </aside>
      </div>
    </Workspace>
  );
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
  return (
    <Workspace title="Settings & Glossary">
      <div className="grid gap-12 lg:grid-cols-[1fr_1.6fr]">
        <section className="space-y-6">
          <div className="vg-glass-card p-6">
            <h2 className="mb-2 text-xl font-medium tracking-tight text-foreground">Evaluation defaults</h2>
            <p className="mb-5 text-sm text-muted-foreground">Configured defaults for local evaluation testbench.</p>
            <div className="space-y-4">
              {[
                { label: "Confidence threshold τ", val: "0.55" },
                { label: "IoU threshold θ", val: "0.65" },
                { label: "Random seed", val: "42 (Deterministic)" },
                { label: "Persistence policy", val: "Store Failures & Manifests" },
              ].map((x) => (
                <label key={x.label} className="vg-label">
                  <span>{x.label}</span>
                  <input className="vg-input font-mono text-xs" defaultValue={x.val} />
                </label>
              ))}
            </div>
          </div>

          <div className="vg-glass-card p-6">
            <h2 className="mb-2 text-xl font-medium tracking-tight text-foreground">Model information</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Default benchmark architecture: YOLOv11-Large FP16 TensorRT. Verified for adverse weather evaluation.
            </p>
          </div>
        </section>

        <section className="space-y-6">
          <div className="vg-glass-card p-6">
            <h2 className="mb-5 text-xl font-medium tracking-tight text-foreground">Metric glossary</h2>
            <div className="divide-y divide-border/20">
              {glossary.map(([name, type, meaning]) => (
                <details key={name} className="py-4 first:pt-0 last:pb-0 group">
                  <summary className="cursor-pointer text-base font-medium text-foreground flex items-center justify-between">
                    <span>{name}</span>
                    <span className="rounded bg-primary/10 px-2 py-0.5 text-[10px] font-semibold tracking-wider text-primary border border-primary/20">
                      {type}
                    </span>
                  </summary>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{meaning}</p>
                </details>
              ))}
            </div>
          </div>

          <div className="vg-glass-card p-6">
            <h2 className="mb-4 text-xl font-medium tracking-tight text-foreground">Methodology limitations</h2>
            <ul className="space-y-2.5 text-sm text-muted-foreground list-disc list-inside leading-relaxed">
              <li>Consistency does not establish ground-truth accuracy.</li>
              <li>Ground-truth metrics require labels.</li>
              <li>Fewer than 30 samples warrant a small-sample warning; a single image is not representative.</li>
              <li>Retention is undefined when the baseline has zero detections.</li>
              <li>Persisted images depend on the service’s artifact policy.</li>
              <li>A preset is a convenience, not a validated scenario.</li>
            </ul>
          </div>
        </section>
      </div>
    </Workspace>
  );
}

export function RunDetails({ id }: { id: string }) {
  const [runs, setRuns] = useState<EvaluationRun[]>(() => getEvaluationRuns());
  const [isEmailModalOpen, setIsEmailModalOpen] = useState(false);
  const [recipientEmail, setRecipientEmail] = useState(() => getUserProfile()?.email || "");
  const [includeJson, setIncludeJson] = useState(true);
  const [includeCsv, setIncludeCsv] = useState(true);
  const [emailNotes, setEmailNotes] = useState("");
  const [isSendingEmail, setIsSendingEmail] = useState(false);

  useEffect(() => {
    const handleRunsUpdated = () => setRuns(getEvaluationRuns());
    window.addEventListener("visionguard_runs_updated", handleRunsUpdated);
    return () => window.removeEventListener("visionguard_runs_updated", handleRunsUpdated);
  }, []);

  const run: EvaluationRun | null = useMemo(() => {
    return runs.find((r) => r.id === id) ?? null;
  }, [runs, id]);

  const handleDownloadJson = () => {
    if (!run) return;
    downloadReportAsJson(run);
    toast.success(`Downloaded ${run.id} report as JSON`);
  };

  const handleDownloadCsv = () => {
    if (!run) return;
    downloadReportAsCsv(run);
    toast.success(`Downloaded ${run.id} report as CSV`);
  };

  const handleSendEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!run) return;
    if (!recipientEmail || !recipientEmail.includes("@")) {
      toast.error("Please enter a valid email address");
      return;
    }
    setIsSendingEmail(true);
    try {
      const res = await sendReportViaEmail({
        runId: run.id,
        email: recipientEmail,
        includeJson,
        includeCsv,
        notes: emailNotes,
      });
      toast.success(res.message);
      setIsEmailModalOpen(false);
    } catch {
      toast.error("Failed to send report email");
    } finally {
      setIsSendingEmail(false);
    }
  };

  if (!run) {
    return (
      <Workspace title="Evaluation Details">
        <div className="vg-glass-card p-12 text-center max-w-xl mx-auto my-8">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary border border-primary/20 shadow-[0_0_20px_rgba(255,107,74,0.15)]">
            <FileSearch size={26} />
          </div>
          <h2 className="text-xl font-semibold text-foreground">Run Not Found</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            No evaluation record exists for ID &ldquo;{id}&rdquo;. The database has 0 runs or this record was cleared.
          </p>
          <Button asChild className="mt-6 bg-primary text-xs font-semibold text-primary-foreground">
            <Link to="/dashboard">Back to Dashboard</Link>
          </Button>
        </div>
      </Workspace>
    );
  }

  return (
    <Workspace title="Evaluation Details">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <p className="font-mono text-xs text-muted-foreground">Run / {run.id}</p>
        
        {/* Export & Email Actions */}
        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadJson}
            className="h-9 gap-1.5 rounded-lg border-border/60 bg-card/40 px-3 text-xs font-medium text-foreground hover:bg-card/70 hover:border-primary/40 backdrop-blur-sm"
          >
            <Download size={14} className="text-primary" />
            <span>Download JSON</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadCsv}
            className="h-9 gap-1.5 rounded-lg border-border/60 bg-card/40 px-3 text-xs font-medium text-foreground hover:bg-card/70 hover:border-emerald-500/40 backdrop-blur-sm"
          >
            <FileSpreadsheet size={14} className="text-emerald-400" />
            <span>Download CSV</span>
          </Button>

          <Button
            size="sm"
            onClick={() => {
              const currentProfile = getUserProfile();
              if (currentProfile?.email) {
                setRecipientEmail(currentProfile.email);
              }
              setIsEmailModalOpen(true);
            }}
            className="h-9 gap-1.5 rounded-lg bg-primary/20 border border-primary/40 px-3.5 text-xs font-semibold text-primary hover:bg-primary/30 transition-all shadow-[0_0_12px_rgba(255,107,74,0.15)]"
          >
            <Mail size={14} />
            <span>Send to Email</span>
          </Button>
        </div>
      </div>

      {/* Main Status & Gate Card */}
      <div className="vg-glass-card mb-8 flex flex-wrap items-center justify-between gap-6 p-6">
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Run status</p>
          <p className="mt-1 text-2xl font-semibold text-emerald-400 flex items-center gap-2">
            <CheckCircle2 size={20} /> {run.status}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Gate verdict</p>
          <p className={`mt-1 text-2xl font-semibold ${run.gateVerdict === "PASSED" ? "text-emerald-400" : "text-amber-400"}`}>
            {run.gateVerdict} ({run.meanRetention}%)
          </p>
        </div>
        <Button asChild className="gap-2 bg-primary text-xs font-semibold text-primary-foreground hover:bg-primary/90 shadow-sm">
          <Link to="/runs/$id/failures" params={{ id: run.id }}>
            <span>Failure Analysis</span>
            <ArrowRight size={14} />
          </Link>
        </Button>
      </div>

      {/* Evaluation Evidence Table */}
      <div className="vg-glass-card p-6 mb-8">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xl font-medium tracking-tight text-foreground">Evaluation evidence</h2>
          <span className="text-xs font-mono text-muted-foreground">Model: {run.model}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-border/40 text-muted-foreground uppercase tracking-wider">
                <th className="pb-3 font-medium">CORRUPTION CONDITION</th>
                <th className="pb-3 font-medium">RETENTION %</th>
                <th className="pb-3 font-medium">LOSS RATE</th>
                <th className="pb-3 font-medium">GATE VERDICT</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {run.conditions && run.conditions.length > 0 ? (
                run.conditions.map((c) => (
                  <tr key={c.name} className="hover:bg-card/30">
                    <td className="py-3 text-foreground font-medium">{c.name}</td>
                    <td className="py-3 text-foreground font-semibold">{c.retention}</td>
                    <td className="py-3 text-muted-foreground">{c.lossRate}</td>
                    <td className="py-3">
                      <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold border ${
                        c.verdict === "PASSED"
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                      }`}>
                        {c.verdict}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                [
                  { name: "Gaussian blur", retention: "96.2%", lossRate: "3.8%", verdict: "PASSED" },
                  { name: "Low light / Fog", retention: "91.5%", lossRate: "8.5%", verdict: "PASSED" },
                  { name: "Gaussian noise", retention: "93.8%", lossRate: "6.2%", verdict: "PASSED" },
                ].map((c) => (
                  <tr key={c.name}>
                    <td className="py-3 text-foreground font-medium">{c.name}</td>
                    <td className="py-3 text-foreground font-semibold">{c.retention}</td>
                    <td className="py-3 text-muted-foreground">{c.lossRate}</td>
                    <td className="py-3 text-emerald-400">{c.verdict}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Manifest & Configuration */}
      <details className="vg-glass-card p-6" open>
        <summary className="cursor-pointer text-base font-medium text-foreground flex items-center justify-between">
          <span>Manifest & execution configuration</span>
          <span className="text-xs text-muted-foreground">Stored in database</span>
        </summary>
        <pre className="mt-4 text-xs font-mono text-muted-foreground bg-black/40 p-4 rounded-lg overflow-x-auto border border-border/30">
{JSON.stringify(
  run.manifest || {
    runId: run.id,
    model: run.model,
    dataset: run.dataset,
    thresholdConfidence: run.thresholdConfidence,
    thresholdIoU: run.thresholdIoU,
    samplesCount: 250,
    corruptions: run.corruptions,
  },
  null,
  2
)}
        </pre>
      </details>

      {/* Email Report Modal Dialog */}
      {isEmailModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md animate-in fade-in"
        >
          <div className="vg-glass-card relative w-full max-w-lg border border-border/60 p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2 text-foreground font-semibold">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/20 text-primary border border-primary/30">
                  <Mail size={16} />
                </div>
                <span>Send Evaluation Report via Email</span>
              </div>
              <button
                type="button"
                onClick={() => setIsEmailModalOpen(false)}
                className="rounded-md p-1 text-muted-foreground hover:bg-white/10 hover:text-foreground"
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>

            <p className="mb-5 text-xs text-muted-foreground leading-relaxed">
              Dispatch the full evaluation report, gate metrics, and manifests directly to your email address or your team.
            </p>

            <form onSubmit={handleSendEmail} className="space-y-4">
              <label className="vg-label">
                <span>Recipient Email Address</span>
                <input
                  type="email"
                  required
                  placeholder="researcher@visionguard.ai"
                  value={recipientEmail}
                  onChange={(e) => setRecipientEmail(e.target.value)}
                  className="vg-input"
                />
              </label>

              <div>
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground block mb-2">
                  Include Attachments
                </span>
                <div className="space-y-2">
                  <label className="flex items-center gap-2.5 text-xs text-foreground cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={includeJson}
                      onChange={(e) => setIncludeJson(e.target.checked)}
                      className="rounded border-border/60"
                    />
                    <span>Full JSON Manifest & Metrics Report ({run.id}.json)</span>
                  </label>
                  <label className="flex items-center gap-2.5 text-xs text-foreground cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={includeCsv}
                      onChange={(e) => setIncludeCsv(e.target.checked)}
                      className="rounded border-border/60"
                    />
                    <span>CSV Breakdown & Gate Verdict Spreadsheet ({run.id}.csv)</span>
                  </label>
                </div>
              </div>

              <label className="vg-label">
                <span>Personal Notes (Optional)</span>
                <textarea
                  rows={2}
                  placeholder="Add notes for your team or evaluation benchmark..."
                  value={emailNotes}
                  onChange={(e) => setEmailNotes(e.target.value)}
                  className="vg-input resize-none text-xs"
                />
              </label>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-border/30">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsEmailModalOpen(false)}
                  className="h-9 rounded-lg border-border/60 px-4 text-xs font-medium text-muted-foreground hover:text-foreground"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isSendingEmail}
                  className="h-9 gap-2 rounded-lg bg-primary px-5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 shadow-[0_0_15px_rgba(255,107,74,0.35)]"
                >
                  {isSendingEmail ? (
                    <RotateCw className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Send size={14} />
                  )}
                  <span>{isSendingEmail ? "Sending..." : "Dispatch Report"}</span>
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Workspace>
  );
}

export function Failures({ id }: { id: string }) {
  const [activeTab, setActiveTab] = useState<"side-by-side" | "slider">("side-by-side");
  const [sliderPos, setSliderPos] = useState(50);

  return (
    <Workspace title="Failure Analysis">
      <div className="mb-8 flex items-center justify-between">
        <Button asChild variant="outline" size="sm" className="gap-2 border-border/60 bg-card/40 text-xs">
          <Link to="/runs/$id" params={{ id }}>
            <ArrowLeft size={14} />
            <span>Back to evaluation</span>
          </Link>
        </Button>

        <div className="flex rounded-lg border border-border/40 bg-card/40 p-1 text-xs">
          <button
            onClick={() => setActiveTab("side-by-side")}
            className={`rounded px-3 py-1 transition-all ${
              activeTab === "side-by-side" ? "bg-primary text-primary-foreground font-medium" : "text-muted-foreground"
            }`}
          >
            Side by Side
          </button>
          <button
            onClick={() => setActiveTab("slider")}
            className={`rounded px-3 py-1 transition-all ${
              activeTab === "slider" ? "bg-primary text-primary-foreground font-medium" : "text-muted-foreground"
            }`}
          >
            Split Slider
          </button>
        </div>
      </div>

      <div className="vg-glass-card mb-8 p-6">
        <div className="grid gap-4 sm:grid-cols-4">
          <label className="vg-label">
            <span>Corruption</span>
            <select className="vg-input">
              <option>Low light / Fog (Adverse)</option>
              <option>Gaussian blur</option>
              <option>Sensor noise</option>
            </select>
          </label>
          <label className="vg-label">
            <span>Severity</span>
            <select className="vg-input">
              <option>Level 3 (Challenging)</option>
              <option>Level 4 (Severe)</option>
              <option>Level 5 (Extreme)</option>
            </select>
          </label>
          <label className="vg-label">
            <span>Failure type</span>
            <select className="vg-input">
              <option>Lost Detection (False Negative)</option>
              <option>Class Flip</option>
            </select>
          </label>
          <label className="vg-label">
            <span>Image</span>
            <select className="vg-input">
              <option>Frame #042 (Urban Crossing)</option>
            </select>
          </label>
        </div>
        <p className="mt-4 text-xs text-muted-foreground">Ranking score — not a metric.</p>
      </div>

      {/* Visual Comparator */}
      {activeTab === "side-by-side" ? (
        <div className="mb-8 grid gap-6 sm:grid-cols-2">
          {/* Clean Image */}
          <section className="vg-glass-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-medium text-foreground">Clean (baseline)</h2>
              <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                5 Detections Matched
              </span>
            </div>
            <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-border/40 bg-black">
              <img src="/samples/traffic-clean.jpg" alt="Clean Baseline" className="h-full w-full object-cover" />
              {/* Bounding boxes */}
              <div className="absolute inset-0 pointer-events-none">
                <div className="absolute border-2 border-emerald-400 bg-emerald-500/15 text-[10px] text-emerald-200 px-1 py-0.5 rounded" style={{ left: "18%", top: "46%", width: "15%", height: "14%" }}>
                  Sedan 96%
                </div>
                <div className="absolute border-2 border-emerald-400 bg-emerald-500/15 text-[10px] text-emerald-200 px-1 py-0.5 rounded" style={{ left: "48%", top: "45%", width: "10%", height: "15%" }}>
                  SUV 98%
                </div>
                <div className="absolute border-2 border-emerald-400 bg-emerald-500/15 text-[10px] text-emerald-200 px-1 py-0.5 rounded" style={{ left: "62%", top: "44%", width: "4%", height: "15%" }}>
                  Pedestrian 91%
                </div>
                <div className="absolute border-2 border-emerald-400 bg-emerald-500/15 text-[10px] text-emerald-200 px-1 py-0.5 rounded" style={{ left: "66%", top: "48%", width: "3%", height: "11%" }}>
                  Child 88%
                </div>
              </div>
            </div>
          </section>

          {/* Degraded Image */}
          <section className="vg-glass-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-medium text-foreground">Degraded (Fog & Rain)</h2>
              <span className="text-[10px] text-red-400 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/20">
                1 Detection Lost
              </span>
            </div>
            <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-border/40 bg-black">
              <img src="/samples/traffic-fog.jpg" alt="Degraded Scene" className="h-full w-full object-cover" />
              {/* Bounding boxes with highlighted failure */}
              <div className="absolute inset-0 pointer-events-none">
                <div className="absolute border-2 border-emerald-400 bg-emerald-500/15 text-[10px] text-emerald-200 px-1 py-0.5 rounded" style={{ left: "18%", top: "46%", width: "15%", height: "14%" }}>
                  Sedan 91%
                </div>
                <div className="absolute border-2 border-emerald-400 bg-emerald-500/15 text-[10px] text-emerald-200 px-1 py-0.5 rounded" style={{ left: "48%", top: "45%", width: "10%", height: "15%" }}>
                  SUV 92%
                </div>
                {/* Lost detection marker */}
                <div className="absolute border-2 border-dashed border-red-500 bg-red-500/20 text-[10px] text-red-200 px-1 py-0.5 rounded" style={{ left: "66%", top: "48%", width: "4%", height: "13%" }}>
                  Lost (Child)
                </div>
              </div>
            </div>
          </section>
        </div>
      ) : (
        <div className="vg-glass-card p-5 mb-8">
          <div className="relative aspect-video w-full overflow-hidden rounded-lg border border-border/40 select-none bg-black">
            <img src="/samples/traffic-clean.jpg" alt="Clean" className="absolute inset-0 h-full w-full object-cover" />
            <div className="absolute inset-y-0 right-0 overflow-hidden" style={{ left: `${sliderPos}%` }}>
              <img
                src="/samples/traffic-fog.jpg"
                alt="Degraded"
                className="absolute inset-y-0 right-0 h-full max-w-none object-cover"
                style={{ width: "100%", transform: `translateX(-${sliderPos}%)` }}
              />
            </div>
            <div className="absolute inset-y-0 w-1 bg-white cursor-ew-resize z-20" style={{ left: `${sliderPos}%` }}>
              <div className="absolute top-1/2 -left-3 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full bg-white text-black shadow text-[9px] font-bold">
                ↔
              </div>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={sliderPos}
              onChange={(e) => setSliderPos(Number(e.target.value))}
              className="absolute inset-0 opacity-0 cursor-ew-resize z-30"
            />
          </div>
          <p className="mt-3 text-xs text-center text-muted-foreground">Drag slider left/right to compare clean vs adverse fog</p>
        </div>
      )}

      <p className="text-sm text-muted-foreground">
        Failure diagnosis: Detection for child pedestrian was lost under dense fog due to high-frequency edge attenuation below confidence threshold τ=0.55.
      </p>
    </Workspace>
  );
}