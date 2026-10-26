import { useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type Det = { label: string; conf: number; box: number[] }
type Fail = { kind: 'lost' | 'class_changed' | 'spurious'; label: string; conf: number; box: number[]; to?: string }
type Level = {
  severity: number; image: string; detections: Det[]; retention: number | null; conf_change: number | null
  lost: number; class_changes: number; spurious: number; latency_ms: number; failures: Fail[]
}
type Run = { id: string; model: string; config: { corruption: string; iou: number; filename: string }; levels: Level[] }

const KINDS = [
  ['blur', 'Blur'], ['brightness', 'Low light'], ['noise', 'Noise'],
  ['rotation', 'Rotation'], ['jpeg', 'Compression'], ['occlusion', 'Occlusion'],
]
const STYLE = {
  lost: ['border-lost border-dashed', 'text-lost', 'Lost'],
  class_changed: ['border-swap', 'text-swap', 'Class changed'],
  spurious: ['border-lost', 'text-lost', 'Spurious'],
} as const
const pct = (v: number | null) => (v === null ? '–' : `${Math.round(v * 100)}%`)

function Box({ b, cls, text }: { b: number[]; cls: string; text: string }) {
  return (
    <div className={`absolute border-2 ${cls}`}
      style={{ left: `${b[0] * 100}%`, top: `${b[1] * 100}%`, width: `${(b[2] - b[0]) * 100}%`, height: `${(b[3] - b[1]) * 100}%` }}>
      <span className="absolute -top-5 left-[-2px] bg-ink px-1 text-xs text-white whitespace-nowrap">{text}</span>
    </div>
  )
}

function Frame({ level, title, showFails }: { level: Level; title: string; showFails: boolean }) {
  return (
    <figure className="min-w-0">
      <figcaption className="mb-2 text-sm font-medium">{title}</figcaption>
      <div className="relative overflow-hidden rounded bg-ink">
        <img src={level.image} alt={title} className="block w-full" />
        {level.detections.map((d, i) => (
          <Box key={i} b={d.box} cls="border-clean" text={`${d.label} ${d.conf.toFixed(2)}`} />
        ))}
        {showFails && level.failures.filter((f) => f.kind !== 'spurious').map((f, i) => (
          <Box key={'f' + i} b={f.box} cls={STYLE[f.kind][0]} text={f.kind === 'lost' ? `lost ${f.label}` : `${f.label} → ${f.to}`} />
        ))}
      </div>
    </figure>
  )
}

const Stat = ({ k, v, sub }: { k: string; v: string; sub?: string }) => (
  <div className="rounded border border-ink/15 bg-white/60 p-3">
    <div className="text-sm text-ink/70">{k}</div>
    <div className="text-2xl font-bold">{v}</div>
    {sub && <div className="text-xs text-ink/60">{sub}</div>}
  </div>
)

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [kind, setKind] = useState('blur')
  const [iou, setIou] = useState(0.5)
  const [run, setRun] = useState<Run | null>(null)
  const [idx, setIdx] = useState(2)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function analyze() {
    if (!file) return
    setBusy(true); setError('')
    const fd = new FormData()
    fd.append('file', file); fd.append('corruption', kind); fd.append('iou', String(iou))
    try {
      const r = await fetch('/api/analyze', { method: 'POST', body: fd })
      if (!r.ok) throw new Error((await r.json()).detail ?? 'The analysis failed.')
      const data: Run = await r.json()
      setRun(data); setIdx(Math.min(2, data.levels.length - 1))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not reach the API. Is the backend running on port 8000?')
    } finally { setBusy(false) }
  }

  const cur = run?.levels[idx]
  const base = run?.levels[0]
  const chart = run?.levels.map((l) => ({
    severity: `${Math.round(l.severity * 100)}%`,
    'Detection retention (%)': l.retention === null ? null : Math.round(l.retention * 100),
    'Confidence change (pts)': l.conf_change === null ? null : Math.round(l.conf_change * 100),
  }))

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">VisionGuard</h1>
        <p className="mt-1 max-w-xl text-ink/75">Stress-test an object detector with degraded images and see exactly where it breaks.</p>
      </header>

      <section className="mb-8 grid gap-4 rounded border border-ink/15 bg-white/60 p-4 md:grid-cols-[1fr_auto_auto_auto] md:items-end">
        <label className="block text-sm font-medium">Image
          <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-ink file:px-3 file:py-2 file:text-white" />
        </label>
        <label className="block text-sm font-medium">Condition
          <select value={kind} onChange={(e) => setKind(e.target.value)} className="mt-1 block rounded border border-ink/30 bg-white px-2 py-2">
            {KINDS.map(([k, n]) => <option key={k} value={k}>{n}</option>)}
          </select>
        </label>
        <label className="block text-sm font-medium">Match threshold (IoU) {iou.toFixed(2)}
          <input type="range" min={0.3} max={0.9} step={0.05} value={iou} onChange={(e) => setIou(+e.target.value)} className="mt-1 block w-full" />
        </label>
        <button onClick={analyze} disabled={!file || busy}
          className="rounded bg-clean px-5 py-2 font-medium text-white disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2">
          {busy ? 'Testing…' : 'Run test'}
        </button>
        {error && <p role="alert" className="text-sm font-medium text-lost md:col-span-4">{error}</p>}
      </section>

      {!run && <p className="py-16 text-center text-ink/60">Choose an image and a condition, then run the test. You will get a clean baseline and five degraded versions.</p>}

      {run && cur && base && (
        <>
          <div className="mb-3 flex items-center gap-4">
            <label className="flex flex-1 items-center gap-3 text-sm font-medium">Severity {Math.round(cur.severity * 100)}%
              <input type="range" min={1} max={run.levels.length - 1} value={Math.max(idx, 1)} onChange={(e) => setIdx(+e.target.value)} className="flex-1" />
            </label>
            <a href={`/api/runs/${run.id}/report`} download={`visionguard-${run.id}.md`} className="rounded border border-ink px-3 py-2 text-sm font-medium">Export report</a>
          </div>
          <div className="mb-6 grid gap-4 md:grid-cols-2">
            <Frame level={base} title={`Clean · ${base.detections.length} detections`} showFails={false} />
            <Frame level={cur} title={`${KINDS.find((k) => k[0] === run.config.corruption)?.[1]} ${Math.round(cur.severity * 100)}% · ${cur.detections.length} detections`} showFails />
          </div>

          <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat k="Detection retention" v={pct(cur.retention)} sub="of baseline objects still found" />
            <Stat k="Confidence change" v={cur.conf_change === null ? '–' : `${cur.conf_change >= 0 ? '+' : ''}${(cur.conf_change * 100).toFixed(0)} pts`} sub="on matched objects" />
            <Stat k="Failures" v={String(cur.lost + cur.class_changes + cur.spurious)} sub={`${cur.lost} lost, ${cur.class_changes} changed, ${cur.spurious} spurious`} />
            <Stat k="Latency" v={`${cur.latency_ms.toFixed(0)} ms`} sub={`clean: ${base.latency_ms.toFixed(0)} ms`} />
            <Stat k="Model" v={run.model} sub={`run ${run.id}`} />
          </div>

          <div className="mb-8 grid gap-6 md:grid-cols-2">
            <section>
              <h2 className="mb-2 text-lg font-bold">Reliability by severity</h2>
              <div className="h-64 rounded border border-ink/15 bg-white/60 p-2">
                <ResponsiveContainer>
                  <LineChart data={chart}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#10282f22" />
                    <XAxis dataKey="severity" /><YAxis /><Tooltip /><Legend />
                    <Line type="monotone" dataKey="Detection retention (%)" stroke="#1f5fa8" strokeWidth={2} />
                    <Line type="monotone" dataKey="Confidence change (pts)" stroke="#c2255c" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-bold">Failure explorer at {Math.round(cur.severity * 100)}%</h2>
              <ul className="max-h-64 space-y-2 overflow-auto">
                {cur.failures.length === 0 && <li className="rounded border border-ok/40 bg-white/60 p-3 text-ok">No failures at this severity: every baseline object was matched and nothing new appeared.</li>}
                {cur.failures.map((f, i) => (
                  <li key={i} className="rounded border border-ink/15 bg-white/60 p-3 text-sm">
                    <span className={`font-bold ${STYLE[f.kind][1]}`}>{STYLE[f.kind][2]}</span>{' '}
                    {f.kind === 'class_changed' ? `${f.label} was read as ${f.to}` : f.kind === 'lost' ? `${f.label} (${f.conf.toFixed(2)} on clean) is no longer detected` : `${f.label} (${f.conf.toFixed(2)}) appeared that was not in the baseline`}
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </>
      )}
    </div>
  )
}
