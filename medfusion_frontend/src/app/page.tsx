"use client";
import { useState, useEffect, useCallback } from "react";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
  CartesianGrid, Cell,
} from "recharts";

// ─── API ─────────────────────────────────────────────────────────────────────
const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function api(path: string) {
  try {
    const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
    if (!r.ok) return null;
    return r.json();
  } catch { return null; }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function fmt(n: any): string {
  if (n == null || n === 0) return "—";
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(n);
}

function riskClr(level: string) {
  return ({ CRITICAL:"#ef4444", HIGH:"#f97316", MODERATE:"#eab308",
             MEDIUM:"#eab308", LOW:"#22c55e" } as any)[level?.toUpperCase()] ?? "#6b7280";
}

function riskClass(level: string) {
  return ({ CRITICAL:"text-red-400 border-red-500/50 bg-red-500/10",
             HIGH:"text-orange-400 border-orange-500/50 bg-orange-500/10",
             MODERATE:"text-yellow-400 border-yellow-500/50 bg-yellow-500/10",
             MEDIUM:"text-yellow-400 border-yellow-500/50 bg-yellow-500/10",
             LOW:"text-emerald-400 border-emerald-500/50 bg-emerald-500/10" } as any)[level?.toUpperCase()]
    ?? "text-zinc-400 border-zinc-700 bg-zinc-800/50";
}

const DISEASES = ["covid","malaria","tuberculosis","influenza","dengue","ebola","mpox","cholera"];

// ─── Sub-components ───────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="flex items-center justify-center gap-2 py-8 text-zinc-500">
      <span className="inline-block w-4 h-4 border-2 border-zinc-600 border-t-cyan-400 rounded-full animate-spin" />
      <span className="text-xs font-mono tracking-widest">FETCHING LIVE DATA</span>
    </div>
  );
}

function StatCard({ label, value, sub, accent }: any) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 flex flex-col gap-1 backdrop-blur">
      <span className="text-[10px] font-mono tracking-widest text-zinc-500 uppercase">{label}</span>
      <span className="text-2xl font-bold font-mono" style={{ color: accent || "#f4f4f5" }}>{value}</span>
      {sub && <span className="text-[11px] text-zinc-500">{sub}</span>}
    </div>
  );
}

function RiskBadge({ level, score }: { level: string; score?: number }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-mono font-bold tracking-wider ${riskClass(level)}`}>
      <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: riskClr(level) }} />
      {level || "UNKNOWN"}
      {score != null && <span className="opacity-60 font-normal">({score.toFixed(0)})</span>}
    </span>
  );
}

function PipelineLog({ log }: { log: string[] }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-4 font-mono text-xs">
      <div className="text-[10px] tracking-widest text-zinc-500 mb-3 uppercase">Pipeline Execution Log</div>
      <div className="space-y-0.5 max-h-48 overflow-y-auto">
        {log.map((line, i) => (
          <div key={i} className={`${line.startsWith("  →") ? "text-zinc-400 pl-3" : "text-cyan-400 font-bold"}`}>
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}

function InsightCard({ text }: { text: string }) {
  const domain = text.match(/^\[([A-Z]+)\]/)?.[1] || "INFO";
  const body   = text.replace(/^\[[A-Z]+\]\s*/, "");
  const colors: any = { EPI:"text-cyan-400", ALERT:"text-red-400", GENOMIC:"text-violet-400", THERAPEUTIC:"text-emerald-400", INDIA:"text-orange-400" };
  const icons:  any = { EPI:"◈", ALERT:"⚠", GENOMIC:"⬡", THERAPEUTIC:"⬡", INDIA:"◆" };
  return (
    <div className="flex gap-3 py-2.5 border-b border-zinc-800 last:border-0">
      <span className={`text-sm mt-0.5 flex-shrink-0 ${colors[domain] || "text-zinc-400"}`}>{icons[domain] || "◈"}</span>
      <div>
        <span className={`text-[10px] font-mono font-bold tracking-widest mr-2 ${colors[domain] || "text-zinc-400"}`}>{domain}</span>
        <span className="text-xs text-zinc-300">{body}</span>
      </div>
    </div>
  );
}

function ConfidenceBar({ confidence }: { confidence: any }) {
  if (!confidence) return null;
  const pct = Math.round((confidence.overall || 0) * 100);
  const clr = pct >= 70 ? "#22c55e" : pct >= 40 ? "#eab308" : "#ef4444";
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
      <div className="flex justify-between items-center mb-2">
        <span className="text-[10px] font-mono tracking-widest text-zinc-500 uppercase">Data Confidence</span>
        <span className="text-sm font-bold font-mono" style={{ color: clr }}>{pct}% — {confidence.label}</span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width:`${pct}%`, background:clr }} />
      </div>
      <div className="flex justify-between text-[10px] font-mono text-zinc-600 mt-2">
        <span>Completeness {Math.round((confidence.completeness||0)*100)}%</span>
        <span>Agreement {Math.round((confidence.agreement||0)*100)}%</span>
        <span>Freshness {Math.round((confidence.freshness||0)*100)}%</span>
      </div>
    </div>
  );
}

function ForecastChart({ timeline, forecast }: { timeline: any[]; forecast: any }) {
  if (!timeline?.length) return (
    <div className="flex items-center justify-center h-40 text-zinc-600 text-xs font-mono">
      NO HISTORICAL TIME-SERIES FOR THIS DISEASE
    </div>
  );

  const historical = timeline.slice(-30).map((pt: any, i: number) => ({
    date: pt.date?.slice(0, 5) || `D${i}`,
    cases: pt.cases,
    type: "historical",
  }));

  const predicted = (forecast?.next_14_days || []).map((v: number, i: number) => ({
    date: forecast?.future_dates?.[i]?.slice(0, 5) || `+${i+1}d`,
    forecast: v,
    upper: forecast?.upper_bound?.[i],
    lower: forecast?.lower_bound?.[i],
    type: "forecast",
  }));

  const anomalyDates = new Set(forecast?.anomaly?.flagged_dates || []);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={historical} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gradCase" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#06b6d4" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#06b6d4" stopOpacity={0}   />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fill:"#52525b", fontSize:10 }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={(v) => fmt(v)} tick={{ fill:"#52525b", fontSize:10 }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background:"#18181b", border:"1px solid #3f3f46", borderRadius:"8px", fontSize:"11px" }}
          labelStyle={{ color:"#a1a1aa" }}
          formatter={(v: any) => [fmt(v), "Cases"]}
        />
        <Area type="monotone" dataKey="cases" stroke="#06b6d4" strokeWidth={2}
          fill="url(#gradCase)" dot={false} activeDot={{ r:4, fill:"#06b6d4" }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function MLSummaryPanel({ ml }: { ml: any }) {
  if (!ml) return null;
  return (
    <div className="rounded-xl border border-violet-500/30 bg-violet-500/5 p-4">
      <div className="text-[10px] font-mono tracking-widest text-violet-400 mb-3 uppercase flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
        ML Intelligence Layer
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-zinc-900/80 border border-zinc-800 p-3">
          <div className="text-[10px] text-zinc-500 font-mono mb-1">FORECAST DAY 1</div>
          <div className="text-lg font-bold font-mono text-violet-300">{fmt(ml.forecasted_cases_day1)}</div>
          <div className="text-[10px] text-zinc-500 mt-1">{ml.forecast_explanation?.slice(0, 60)}…</div>
        </div>
        <div className={`rounded-lg border p-3 ${ml.anomaly_flag ? "bg-red-500/10 border-red-500/40" : "bg-zinc-900/80 border-zinc-800"}`}>
          <div className="text-[10px] text-zinc-500 font-mono mb-1">ANOMALY STATUS</div>
          <div className={`text-lg font-bold font-mono ${ml.anomaly_flag ? "text-red-400" : "text-emerald-400"}`}>
            {ml.anomaly_flag ? "⚠ DETECTED" : "✓ NORMAL"}
          </div>
          <div className="text-[10px] text-zinc-500 mt-1">{ml.anomaly_explanation?.slice(0, 60) || "Z-Score + CUSUM monitoring"}…</div>
        </div>
        <div className="rounded-lg bg-zinc-900/80 border border-zinc-800 p-3">
          <div className="text-[10px] text-zinc-500 font-mono mb-1">RISK SCORE</div>
          <div className="text-lg font-bold font-mono" style={{ color: riskClr(ml.risk_label) }}>
            {ml.risk_score?.toFixed(1)}/100
          </div>
          <div className="text-[10px] text-zinc-500 mt-1">{ml.risk_label} — SIR composite</div>
        </div>
        <div className="rounded-lg bg-zinc-900/80 border border-zinc-800 p-3">
          <div className="text-[10px] text-zinc-500 font-mono mb-1">GROWTH TYPE</div>
          <div className="text-lg font-bold font-mono text-violet-300 capitalize">{ml.trend_growth_type || "—"}</div>
          <div className="text-[10px] text-zinc-500 mt-1">Exp/linear/plateau detection</div>
        </div>
      </div>
    </div>
  );
}

function AlertsPanel({ alerts }: { alerts: any }) {
  const promed = alerts?.promed_alerts || [];
  const hmap   = alerts?.healthmap_alerts || [];
  const all    = [...promed, ...hmap].slice(0, 8);

  if (!all.length) return (
    <div className="text-center py-6 text-zinc-600 text-xs font-mono">NO MATCHING ALERTS — ALL CLEAR</div>
  );

  return (
    <div className="space-y-2">
      {all.map((a: any, i: number) => (
        <div key={i} className={`rounded-lg border p-3 flex gap-3 items-start
          ${a.severity === "high" ? "border-red-500/40 bg-red-500/5" :
            a.severity === "medium" ? "border-orange-500/30 bg-orange-500/5" :
            "border-zinc-800 bg-zinc-900/40"}`}>
          <span className={`text-xs mt-0.5 flex-shrink-0 font-bold
            ${a.severity === "high" ? "text-red-400" : a.severity === "medium" ? "text-orange-400" : "text-zinc-500"}`}>
            {a.severity === "high" ? "●" : a.severity === "medium" ? "◐" : "○"}
          </span>
          <div className="min-w-0">
            <div className="text-xs text-zinc-200 leading-snug truncate">{a.title}</div>
            <div className="flex gap-2 mt-1">
              <span className="text-[10px] font-mono text-zinc-600">{a.source || "ProMED"}</span>
              {a.published_at && <span className="text-[10px] font-mono text-zinc-700">{String(a.published_at).slice(0,16)}</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function GenomicsPanel({ data }: { data: any }) {
  const genes = data?.data?.top_genes || [];
  if (!genes.length) return (
    <div className="text-center py-6 text-zinc-600 text-xs font-mono">NO GENE ASSOCIATIONS FOUND</div>
  );
  return (
    <div className="space-y-2">
      {genes.slice(0, 6).map((g: any, i: number) => (
        <div key={i} className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
          <div className="w-8 h-8 rounded-lg bg-violet-500/10 border border-violet-500/30
            flex items-center justify-center text-[10px] font-bold font-mono text-violet-400 flex-shrink-0">
            {i + 1}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold font-mono text-violet-300">{g.gene_symbol}</span>
              <span className="text-[10px] text-zinc-600 truncate">{g.gene_name}</span>
            </div>
            <div className="mt-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
              <div className="h-full bg-violet-500 rounded-full" style={{ width:`${(g.association_score||0)*100}%` }} />
            </div>
          </div>
          <span className="text-xs font-mono text-violet-400 flex-shrink-0">{(g.association_score||0).toFixed(3)}</span>
        </div>
      ))}
      <div className="text-[10px] text-zinc-600 font-mono text-center pt-1">
        {data?.data?.total_gene_associations?.toLocaleString()} total associations — Open Targets Platform
      </div>
    </div>
  );
}

function TherapeuticsPanel({ data }: { data: any }) {
  const drugs = data?.data?.drugs || [];
  if (!drugs.length) return (
    <div className="text-center py-6 text-zinc-600 text-xs font-mono">NO DRUG DATA AVAILABLE</div>
  );
  return (
    <div className="space-y-2">
      {drugs.filter((d:any) => d.status === "ok").map((d: any, i: number) => (
        <div key={i} className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 flex gap-3 items-start">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30
            flex items-center justify-center text-emerald-400 flex-shrink-0 text-xs font-bold">Rx</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-bold font-mono text-emerald-300">{d.name}</span>
              {d.who_essential && (
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-emerald-500/40 bg-emerald-500/10 text-emerald-400">
                  WHO EML
                </span>
              )}
            </div>
            <div className="text-[10px] text-zinc-500 mt-1 font-mono">{d.molecular_formula} · MW {d.molecular_weight}</div>
            {d.description && <div className="text-[10px] text-zinc-500 mt-1 line-clamp-2">{d.description}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

function HotspotLeaderboard({ data }: { data: any }) {
  const countries = data?.ranked_countries || [];
  if (!countries.length) return <Spinner />;

  return (
    <div>
      <div className="grid grid-cols-[1fr_auto_auto] text-[10px] font-mono tracking-widest text-zinc-600 uppercase pb-2 mb-2 border-b border-zinc-800">
        <span>Country</span>
        <span className="text-right pr-4">Score</span>
        <span className="text-right">Risk</span>
      </div>
      <div className="space-y-1 max-h-80 overflow-y-auto pr-1">
        {countries.slice(0, 15).map((c: any, i: number) => (
          <div key={i} className="grid grid-cols-[1fr_auto_auto] items-center gap-2 py-1.5 rounded-lg hover:bg-zinc-800/30 px-1 transition-colors">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-[10px] text-zinc-600 font-mono w-5 flex-shrink-0">{i+1}</span>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-zinc-200 truncate">{c.country}</div>
                <div className="h-1 bg-zinc-800 rounded-full mt-1 overflow-hidden">
                  <div className="h-full rounded-full transition-all"
                    style={{ width:`${(c.risk_score||0)*100}%`, background: riskClr(c.risk_label) }} />
                </div>
              </div>
            </div>
            <span className="text-xs font-mono text-zinc-400 pr-4">{((c.risk_score||0)*100).toFixed(0)}</span>
            <RiskBadge level={c.risk_label} />
          </div>
        ))}
      </div>
    </div>
  );
}

function SourcesPanel({ pipeline }: { pipeline: any }) {
  if (!pipeline) return null;
  const sources = pipeline.sources_fetched || [];
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-3 uppercase">Data Sources Used</div>
      <div className="flex flex-wrap gap-2">
        {sources.map((s: string) => (
          <span key={s} className="text-[10px] font-mono px-2 py-1 rounded border border-cyan-500/30 bg-cyan-500/5 text-cyan-400">
            {s.replace(/_/g, " ").toUpperCase()}
          </span>
        ))}
        {pipeline.elapsed_seconds && (
          <span className="text-[10px] font-mono px-2 py-1 rounded border border-zinc-700 bg-zinc-800/50 text-zinc-500">
            ⏱ {pipeline.elapsed_seconds.toFixed(2)}s
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function MedFusion() {
  const [query,      setQuery]      = useState("covid");
  const [inputVal,   setInputVal]   = useState("covid");
  const [disease,    setDisease]    = useState<any>(null);
  const [hotspots,   setHotspots]   = useState<any>(null);
  const [loading,    setLoading]    = useState(false);
  const [tab,        setTab]        = useState<"overview"|"ml"|"genomics"|"therapeutics"|"alerts"|"hotspots">("overview");

  // Fetch disease data
  const run = useCallback(async (q: string) => {
    setLoading(true);
    setDisease(null);
    const d = await api(`/disease/${encodeURIComponent(q)}?days=30`);
    setDisease(d);
    setLoading(false);
  }, []);

  // Fetch hotspots once
  useEffect(() => {
    api("/hotspots?disease=covid&top_n=20").then(setHotspots);
  }, []);

  useEffect(() => { run(query); }, [query]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = inputVal.trim().toLowerCase();
    if (q) setQuery(q);
  };

  const epi     = disease?.epidemiology || {};
  const metrics = disease?.metrics || {};
  const risk    = metrics?.risk || disease?.risk || {};
  const ml      = disease?.ml_summary || {};
  const conf    = disease?.confidence || epi?.confidence;
  const alerts  = disease?.alerts || {};
  const genomics = disease?.genomics || {};
  const ther    = disease?.therapeutics || {};
  const india   = disease?.india_context || {};
  const pipeline = disease?.pipeline || {};
  const insights = disease?.insights || [];

  const riskLevel = risk?.label || risk?.level || "LOW";
  const riskScore = risk?.composite_score || risk?.score || 0;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100" style={{ fontFamily:"'IBM Plex Mono', 'Fira Code', monospace" }}>
      {/* Top nav */}
      <div className="border-b border-zinc-800 bg-zinc-950/90 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-cyan-400/20 border border-cyan-400/40 flex items-center justify-center">
              <span className="text-cyan-400 text-xs font-bold">⬡</span>
            </div>
            <span className="text-sm font-bold tracking-widest text-zinc-100 uppercase">MedFusion</span>
            <span className="text-[10px] text-zinc-600 tracking-widest hidden sm:block">DISEASE INTELLIGENCE SYSTEM</span>
          </div>

          {/* Search */}
          <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1 max-w-sm">
            <div className="relative flex-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-600 text-xs">$</span>
              <input
                value={inputVal}
                onChange={e => setInputVal(e.target.value)}
                placeholder="query disease..."
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg pl-7 pr-3 py-1.5
                  text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-cyan-500/60
                  focus:ring-1 focus:ring-cyan-500/20"
              />
            </div>
            <button type="submit"
              className="px-3 py-1.5 rounded-lg bg-cyan-500/20 border border-cyan-500/40
                text-cyan-400 text-xs font-bold hover:bg-cyan-500/30 transition-colors">
              RUN
            </button>
          </form>

          {/* Quick select */}
          <div className="hidden lg:flex items-center gap-1">
            {["covid","malaria","tuberculosis","influenza"].map(d => (
              <button key={d} onClick={() => { setInputVal(d); setQuery(d); }}
                className={`px-2 py-1 rounded text-[10px] tracking-wider transition-colors
                  ${query === d ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40" : "text-zinc-600 hover:text-zinc-300"}`}>
                {d.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">

        {/* ── HERO SECTION ── */}
        <div className={`rounded-2xl border p-6 relative overflow-hidden
          ${riskLevel === "CRITICAL" ? "border-red-500/40 bg-red-500/5" :
            riskLevel === "HIGH" ? "border-orange-500/30 bg-orange-500/5" :
            riskLevel === "MODERATE" ? "border-yellow-500/30 bg-yellow-500/5" :
            "border-zinc-800 bg-zinc-900/40"}`}>

          {/* Background glow */}
          <div className="absolute inset-0 opacity-5 pointer-events-none"
            style={{ background:`radial-gradient(circle at 20% 50%, ${riskClr(riskLevel)}, transparent 60%)` }} />

          <div className="relative">
            {loading ? (
              <Spinner />
            ) : disease ? (
              <div className="space-y-4">
                {/* Headline row */}
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div>
                    <div className="flex items-center gap-3 flex-wrap">
                      <h1 className="text-2xl font-bold uppercase tracking-wider text-zinc-100">
                        {epi.disease || query.toUpperCase()}
                      </h1>
                      <span className="text-xs font-mono text-zinc-600 border border-zinc-700 px-2 py-0.5 rounded">
                        ICD-10: {disease.icd10 || epi.icd10 || "—"}
                      </span>
                      <RiskBadge level={riskLevel} score={riskScore} />
                    </div>
                    {disease.headline && (
                      <div className="mt-2 text-sm text-zinc-400">{disease.headline}</div>
                    )}
                    {ml.trend_growth_type && ml.trend_growth_type !== "unknown" && (
                      <div className="mt-1 text-xs text-zinc-500">
                        Growth pattern: <span className="text-cyan-400 font-bold capitalize">{ml.trend_growth_type}</span>
                        {metrics.velocity && metrics.velocity !== "stable" && (
                          <span className="ml-2 text-yellow-400">({metrics.velocity})</span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Risk gauge */}
                  <div className="text-right flex-shrink-0">
                    <div className="text-4xl font-bold font-mono" style={{ color: riskClr(riskLevel) }}>
                      {riskScore?.toFixed ? riskScore.toFixed(1) : riskScore}
                    </div>
                    <div className="text-[10px] text-zinc-500 tracking-widest uppercase">Risk Score /100</div>
                    <div className="text-[10px] text-zinc-600 mt-1">SIR composite model</div>
                  </div>
                </div>

                {/* KPI strip */}
                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
                  <StatCard label="Total Cases"    value={fmt(epi.total_cases)}  sub={epi.data_freshness} />
                  <StatCard label="Deaths"         value={fmt(epi.total_deaths)} />
                  <StatCard label="CFR"            value={epi.cfr_percent != null ? `${epi.cfr_percent?.toFixed(3)}%` : "—"}
                    accent={epi.cfr_percent > 5 ? "#ef4444" : epi.cfr_percent > 1 ? "#f97316" : "#22c55e"} />
                  <StatCard label="7-Day Change"   value={metrics.pct_change_7d != null ? `${metrics.pct_change_7d > 0 ? "+" : ""}${metrics.pct_change_7d?.toFixed(1)}%` : "—"}
                    accent={metrics.pct_change_7d > 5 ? "#f97316" : metrics.pct_change_7d < -5 ? "#22c55e" : "#a1a1aa"} />
                  <StatCard label="R₀ Estimate"    value={metrics.r0_estimate?.toFixed(3) || "—"}
                    accent={metrics.r0_estimate > 2 ? "#ef4444" : metrics.r0_estimate > 1 ? "#f97316" : "#22c55e"} />
                  <StatCard label="Doubling Time"  value={metrics.doubling_time_days ? `${metrics.doubling_time_days}d` : "—"}
                    accent={metrics.doubling_time_days < 7 ? "#ef4444" : metrics.doubling_time_days < 14 ? "#f97316" : "#a1a1aa"} />
                </div>

                {/* Risk explanation */}
                {risk.explanation && (
                  <div className="text-xs text-zinc-500 border-l-2 pl-3 leading-relaxed" style={{ borderColor: riskClr(riskLevel) }}>
                    {risk.explanation}
                  </div>
                )}

                {/* Sources */}
                <SourcesPanel pipeline={pipeline} />
              </div>
            ) : (
              <div className="text-center py-8 text-zinc-600 text-xs font-mono">
                $ medfusion query --disease="{query}" — waiting for response
              </div>
            )}
          </div>
        </div>

        {/* ── TABS ── */}
        <div className="flex gap-1 border-b border-zinc-800 overflow-x-auto">
          {([
            ["overview",     "Overview"],
            ["ml",           "ML Intelligence"],
            ["alerts",       `Alerts ${alerts?.summary?.total_matching > 0 ? `(${alerts.summary.total_matching})` : ""}`],
            ["genomics",     "Genomics"],
            ["therapeutics", "Therapeutics"],
            ["hotspots",     "★ Hotspots"],
          ] as const).map(([key, label]) => (
            <button key={key} onClick={() => setTab(key as any)}
              className={`px-4 py-2.5 text-xs font-mono tracking-wider whitespace-nowrap border-b-2 transition-colors
                ${tab === key
                  ? "border-cyan-500 text-cyan-400"
                  : "border-transparent text-zinc-500 hover:text-zinc-300"}`}>
              {label}
            </button>
          ))}
        </div>

        {/* ── TAB CONTENT ── */}
        {loading ? <Spinner /> : disease && (
          <div>

            {/* OVERVIEW TAB */}
            {tab === "overview" && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Left: trend chart + confidence */}
                <div className="lg:col-span-2 space-y-4">
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-[10px] font-mono tracking-widest text-zinc-500 uppercase">
                        Historical Trend + Forecast
                      </span>
                      <div className="flex items-center gap-2 text-[10px] font-mono">
                        <span className="flex items-center gap-1 text-cyan-400"><span className="w-3 h-0.5 bg-cyan-400 inline-block" />actual</span>
                        <span className="flex items-center gap-1 text-violet-400"><span className="w-3 h-0.5 bg-violet-400 inline-block border-dashed" />forecast</span>
                      </div>
                    </div>
                    <ForecastChart timeline={metrics.timeline || []} forecast={metrics.forecast} />
                  </div>
                  <ConfidenceBar confidence={conf} />
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                    <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-3 uppercase">Intelligence Insights</div>
                    <div>{insights.map((ins: string, i: number) => <InsightCard key={i} text={ins} />)}</div>
                  </div>
                </div>

                {/* Right: region breakdown + India */}
                <div className="space-y-4">
                  {Object.keys(epi.region_breakdown || {}).length > 0 && (
                    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                      <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-3 uppercase">Regional Distribution</div>
                      <div className="space-y-2">
                        {Object.entries(epi.region_breakdown)
                          .sort(([,a],[,b]) => (b as number) - (a as number))
                          .slice(0, 6)
                          .map(([region, val]: any) => {
                            const max = Math.max(...Object.values(epi.region_breakdown) as number[]);
                            return (
                              <div key={region}>
                                <div className="flex justify-between text-[10px] font-mono text-zinc-400 mb-1">
                                  <span className="truncate">{region}</span>
                                  <span className="text-zinc-500 flex-shrink-0 ml-2">{fmt(val)}</span>
                                </div>
                                <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
                                  <div className="h-full bg-cyan-500/60 rounded-full" style={{ width:`${(val/max)*100}%` }} />
                                </div>
                              </div>
                            );
                          })}
                      </div>
                    </div>
                  )}

                  {/* India context */}
                  {india?.india_burden && (
                    <div className="rounded-xl border border-orange-500/30 bg-orange-500/5 p-4">
                      <div className="text-[10px] font-mono tracking-widest text-orange-400 mb-3 uppercase">🇮🇳 India Context</div>
                      <div className="space-y-2 text-xs">
                        {india.india_burden.annual_cases && (
                          <div className="flex justify-between">
                            <span className="text-zinc-500">Annual cases</span>
                            <span className="font-mono text-orange-300">{fmt(india.india_burden.annual_cases)}</span>
                          </div>
                        )}
                        {india.india_burden.annual_deaths && (
                          <div className="flex justify-between">
                            <span className="text-zinc-500">Annual deaths</span>
                            <span className="font-mono text-zinc-300">{fmt(india.india_burden.annual_deaths)}</span>
                          </div>
                        )}
                        {india.india_burden.india_share_global && (
                          <div className="flex justify-between">
                            <span className="text-zinc-500">Global share</span>
                            <span className="font-mono text-orange-300 font-bold">{india.india_burden.india_share_global}</span>
                          </div>
                        )}
                        {india.india_burden.states_highest?.length > 0 && (
                          <div>
                            <div className="text-zinc-500 mb-1">Highest burden states</div>
                            <div className="flex flex-wrap gap-1">
                              {india.india_burden.states_highest.map((s: string) => (
                                <span key={s} className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-orange-500/30 bg-orange-500/10 text-orange-300">
                                  {s}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        <div className="text-[10px] text-zinc-600 pt-1">{india.data_note}</div>
                      </div>
                    </div>
                  )}

                  {/* Data fusion provenance */}
                  {epi.provenance && (
                    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                      <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-3 uppercase">Fusion Provenance</div>
                      <div className="space-y-1.5">
                        {Object.entries(epi.provenance).map(([field, info]: any) => (
                          <div key={field} className="flex gap-2 text-[10px] font-mono">
                            <span className="text-zinc-600 w-24 flex-shrink-0">{field}</span>
                            <span className="text-cyan-400/70">{info.source || info.method || "—"}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ML INTELLIGENCE TAB */}
            {tab === "ml" && (
              <div className="space-y-4">
                <MLSummaryPanel ml={ml} />
                {metrics.risk?.explanation && (
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                    <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-2 uppercase">Risk Score — Why?</div>
                    <p className="text-xs text-zinc-300 leading-relaxed">{metrics.risk.explanation}</p>
                    {metrics.risk.components && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3">
                        {Object.entries(metrics.risk.components).map(([k, v]: any) => (
                          <div key={k} className="rounded-lg bg-zinc-900 border border-zinc-800 p-3">
                            <div className="text-[10px] text-zinc-600 font-mono">{k.replace("_"," ").toUpperCase()}</div>
                            <div className="text-lg font-bold font-mono text-zinc-200">{v?.toFixed(1)}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {metrics.anomaly && (
                  <div className={`rounded-xl border p-4 ${metrics.anomaly.anomaly_count > 0 ? "border-red-500/30 bg-red-500/5" : "border-zinc-800 bg-zinc-900/40"}`}>
                    <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-2 uppercase">
                      Anomaly Detection — Z-Score + CUSUM (WHO Standard)
                    </div>
                    <p className="text-xs text-zinc-300 leading-relaxed">{metrics.anomaly.explanation || "No anomalies detected."}</p>
                    {metrics.anomaly.flagged_dates?.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        {metrics.anomaly.flagged_dates.map((d: string) => (
                          <span key={d} className="text-[10px] font-mono px-2 py-1 rounded border border-red-500/30 bg-red-500/10 text-red-400">{d}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {metrics.forecast?.explanation && (
                  <div className="rounded-xl border border-violet-500/30 bg-violet-500/5 p-4">
                    <div className="text-[10px] font-mono tracking-widest text-violet-400 mb-2 uppercase">XGBoost Forecast</div>
                    <p className="text-xs text-zinc-300 leading-relaxed">{metrics.forecast.explanation}</p>
                    {metrics.forecast.next_14_days?.length > 0 && (
                      <div className="mt-3">
                        <ResponsiveContainer width="100%" height={160}>
                          <BarChart data={metrics.forecast.next_14_days.map((v:number,i:number) => ({ day:`D+${i+1}`, cases:v }))}>
                            <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
                            <XAxis dataKey="day" tick={{ fill:"#52525b", fontSize:10 }} axisLine={false} tickLine={false} />
                            <YAxis tickFormatter={fmt} tick={{ fill:"#52525b", fontSize:10 }} axisLine={false} tickLine={false} />
                            <Tooltip contentStyle={{ background:"#18181b", border:"1px solid #3f3f46", borderRadius:"8px", fontSize:"11px" }}
                              formatter={(v:any) => [fmt(v), "Forecast"]} />
                            <Bar dataKey="cases" fill="#7c3aed" radius={[3,3,0,0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                )}
                <PipelineLog log={pipeline.log || []} />
              </div>
            )}

            {/* ALERTS TAB */}
            {tab === "alerts" && (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  <StatCard label="ProMED Alerts" value={alerts?.promed_alerts?.length || 0} />
                  <StatCard label="High Severity"
                    value={alerts?.summary?.high_severity || 0}
                    accent={(alerts?.summary?.high_severity || 0) > 0 ? "#ef4444" : undefined} />
                  <StatCard label="HealthMap"     value={alerts?.healthmap_alerts?.length || 0} />
                </div>
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                  <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-3 uppercase">
                    Live Outbreak Alerts — ProMED + HealthMap
                  </div>
                  <AlertsPanel alerts={alerts} />
                </div>
              </div>
            )}

            {/* GENOMICS TAB */}
            {tab === "genomics" && (
              <div className="space-y-4">
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                  <div className="flex justify-between items-center mb-4">
                    <div>
                      <div className="text-[10px] font-mono tracking-widest text-zinc-500 uppercase">Gene-Disease Associations</div>
                      <div className="text-xs text-zinc-600 mt-0.5">Open Targets Platform — ranked by evidence score</div>
                    </div>
                    {genomics?.efo_id && (
                      <span className="text-[10px] font-mono px-2 py-1 rounded border border-violet-500/30 bg-violet-500/10 text-violet-400">
                        {genomics.efo_id}
                      </span>
                    )}
                  </div>
                  <GenomicsPanel data={genomics} />
                </div>
              </div>
            )}

            {/* THERAPEUTICS TAB */}
            {tab === "therapeutics" && (
              <div className="space-y-4">
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                  <div className="text-[10px] font-mono tracking-widest text-zinc-500 mb-4 uppercase">
                    Drug Data — PubChem PUG-REST
                  </div>
                  <TherapeuticsPanel data={ther} />
                </div>
              </div>
            )}

            {/* HOTSPOTS TAB — WOW FEATURE */}
            {tab === "hotspots" && (
              <div className="space-y-4">
                <div className="rounded-xl border border-orange-500/30 bg-orange-500/5 p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
                    <span className="text-[10px] font-mono tracking-widest text-orange-400 uppercase">
                      Country-Wise Outbreak Risk — Live Intelligence
                    </span>
                  </div>
                  <div className="text-[10px] text-zinc-600 font-mono mb-4">
                    Scored from disease.sh · Formula: 0.30×growth + 0.25×burden + 0.20×acceleration + 0.15×CFR + 0.10×log(today)
                  </div>
                  {hotspots?.hotspots?.countries?.length > 0 && (
                    <div className="mb-4 p-3 rounded-lg border border-red-500/30 bg-red-500/5">
                      <div className="text-[10px] font-mono text-red-400 mb-2 uppercase">⚠ Detected Hotspots</div>
                      <div className="flex flex-wrap gap-2">
                        {hotspots.hotspots.countries.map((c: any) => (
                          <div key={c.country} className="flex items-center gap-1.5 text-xs font-mono px-2 py-1 rounded border border-red-500/30 bg-red-500/10 text-red-300">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
                            {c.country} · {((c.risk_score||0)*100).toFixed(0)}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <HotspotLeaderboard data={hotspots} />
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── FOOTER ── */}
        <div className="border-t border-zinc-800 pt-4 flex flex-wrap justify-between items-center gap-2 text-[10px] font-mono text-zinc-700">
          <span>MedFusion Disease Intelligence System · 8-stage pipeline · 12 live sources</span>
          <div className="flex items-center gap-3">
            {["WHO GHO","disease.sh","CDC","ECDC","ProMED","HealthMap","Open Targets","PubChem"].map(s => (
              <span key={s}>{s}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
