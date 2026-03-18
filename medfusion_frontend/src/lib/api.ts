const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

// GET /disease/{name}  — full 8-stage pipeline
export const fetchDisease = (name: string, days = 30) =>
  get<any>(`/disease/${encodeURIComponent(name)}?days=${days}`);

// GET /trends/{disease}
export const fetchTrends = (disease: string, days = 90) =>
  get<any>(`/trends/${encodeURIComponent(disease)}?days=${days}`);

// GET /alerts?disease=X
export const fetchAlerts = (disease = "") =>
  get<any>(`/alerts${disease ? `?disease=${encodeURIComponent(disease)}` : ""}`);

// GET /hotspots  — WOW feature: country risk leaderboard
export const fetchHotspots = (disease = "covid", topN = 20) =>
  get<any>(`/hotspots?disease=${encodeURIComponent(disease)}&top_n=${topN}`);

// GET /compare/{d1}/{d2}
export const fetchCompare = (d1: string, d2: string) =>
  get<any>(`/compare/${encodeURIComponent(d1)}/${encodeURIComponent(d2)}`);

// GET /genomics/{disease}
export const fetchGenomics = (disease: string) =>
  get<any>(`/genomics/${encodeURIComponent(disease)}`);

// GET /therapeutics/{disease}
export const fetchTherapeutics = (disease: string) =>
  get<any>(`/therapeutics/${encodeURIComponent(disease)}`);

// GET /india/{disease}
export const fetchIndia = (disease: string) =>
  get<any>(`/india/${encodeURIComponent(disease)}`);

// GET /spread
export const fetchSpread = () => get<any>("/spread");

// GET /sources
export const fetchSources = () => get<any>("/sources");

// Helpers
export const RELIABLE_DISEASES = ["covid", "malaria", "tuberculosis", "influenza"] as const;
export const ALL_DISEASES = ["covid", "malaria", "tuberculosis", "influenza", "dengue", "ebola", "mpox", "cholera", "h5n1"] as const;

export function riskColor(level: string): string {
  return {
    CRITICAL: "#ef4444",
    HIGH:     "#f97316",
    MODERATE: "#eab308",
    MEDIUM:   "#eab308",
    LOW:      "#22c55e",
  }[level?.toUpperCase()] ?? "#6b7280";
}

export function riskBg(level: string): string {
  return {
    CRITICAL: "bg-red-500/15 border-red-500/40 text-red-400",
    HIGH:     "bg-orange-500/15 border-orange-500/40 text-orange-400",
    MODERATE: "bg-yellow-500/15 border-yellow-500/40 text-yellow-400",
    MEDIUM:   "bg-yellow-500/15 border-yellow-500/40 text-yellow-400",
    LOW:      "bg-green-500/15 border-green-500/40 text-green-400",
  }[level?.toUpperCase()] ?? "bg-zinc-500/15 border-zinc-500/40 text-zinc-400";
}

export function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000)     return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000)         return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}
