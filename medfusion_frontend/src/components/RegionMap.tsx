"use client";
import { useState } from "react";

// WHO region → approximate SVG path coordinates on a simplified world map
// Using a flat 800x400 equirectangular projection
const WHO_REGIONS: Record<string, {
  label: string;
  cx: number; cy: number;   // circle center
  rx: number; ry: number;   // ellipse radii (approximate coverage)
  shortLabel: string;
}> = {
  "Africa": {
    label: "Africa", shortLabel: "AFR",
    cx: 490, cy: 240, rx: 65, ry: 75,
  },
  "Americas": {
    label: "Americas", shortLabel: "AMR",
    cx: 195, cy: 210, rx: 80, ry: 90,
  },
  "South-East Asia": {
    label: "South-East Asia", shortLabel: "SEARO",
    cx: 645, cy: 215, rx: 50, ry: 50,
  },
  "Europe": {
    label: "Europe", shortLabel: "EUR",
    cx: 490, cy: 130, rx: 65, ry: 45,
  },
  "Eastern Mediterranean": {
    label: "Eastern Mediterranean", shortLabel: "EMRO",
    cx: 545, cy: 185, rx: 45, ry: 35,
  },
  "Western Pacific": {
    label: "Western Pacific", shortLabel: "WPRO",
    cx: 715, cy: 195, rx: 60, ry: 55,
  },
  // disease.sh continent names
  "North America": {
    label: "North America", shortLabel: "NA",
    cx: 170, cy: 165, rx: 65, ry: 50,
  },
  "South America": {
    label: "South America", shortLabel: "SA",
    cx: 225, cy: 280, rx: 50, ry: 60,
  },
  "Asia": {
    label: "Asia", shortLabel: "ASIA",
    cx: 650, cy: 185, rx: 80, ry: 65,
  },
  "Oceania": {
    label: "Oceania", shortLabel: "OCN",
    cx: 730, cy: 295, rx: 45, ry: 35,
  },
  "Unknown": {
    label: "Unknown", shortLabel: "?",
    cx: 400, cy: 350, rx: 20, ry: 20,
  },
};

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toLocaleString();
}

function getColor(value: number, max: number): string {
  const ratio = value / max;
  if (ratio > 0.7) return "#ef4444";   // red — highest burden
  if (ratio > 0.4) return "#f97316";   // orange
  if (ratio > 0.2) return "#eab308";   // yellow
  return "#22c55e";                     // green — low burden
}

interface RegionMapProps {
  regionBreakdown: Record<string, number>;
  disease: string;
  dataSource?: string;
}

export default function RegionMap({ regionBreakdown, disease, dataSource }: RegionMapProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  const entries = Object.entries(regionBreakdown || {});
  if (!entries.length) return null;

  const maxVal = Math.max(...entries.map(([, v]) => v));
  const total  = entries.reduce((s, [, v]) => s + v, 0);

  // Match region breakdown keys to WHO_REGIONS
  const mapped = entries
    .map(([region, value]) => {
      // Try exact match first, then partial
      const key = Object.keys(WHO_REGIONS).find(
        k => region.toLowerCase().includes(k.toLowerCase()) ||
             k.toLowerCase().includes(region.toLowerCase())
      ) || region;
      return { region, key, value, config: WHO_REGIONS[key] };
    })
    .filter(r => r.config);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
      {/* Header */}
      <div className="px-4 pt-4 pb-2 flex items-center justify-between">
        <div>
          <div className="text-[10px] font-mono tracking-widest text-zinc-500 uppercase">
            Regional Distribution
          </div>
          <div className="text-[10px] text-zinc-600 font-mono mt-0.5">
            {disease} · {dataSource || "WHO GHO"} · {fmt(total)} total
          </div>
        </div>
        <div className="flex items-center gap-3 text-[9px] font-mono text-zinc-600">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 inline-block"/>High</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-orange-500 inline-block"/>Med</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"/>Low</span>
        </div>
      </div>

      {/* SVG Map */}
      <div className="relative px-2 pb-2">
        <svg
          viewBox="0 0 800 400"
          className="w-full"
          style={{ maxHeight: "280px" }}
        >
          {/* ── Ocean background ── */}
          <rect width="800" height="400" fill="#0a0a0f" rx="8" />

          {/* ── Grid lines (latitude/longitude feel) ── */}
          {[0,1,2,3,4,5,6,7,8].map(i => (
            <line key={`v${i}`} x1={i*100} y1="0" x2={i*100} y2="400"
              stroke="#1a1a2e" strokeWidth="0.5" />
          ))}
          {[0,1,2,3,4].map(i => (
            <line key={`h${i}`} x1="0" y1={i*100} x2="800" y2={i*100}
              stroke="#1a1a2e" strokeWidth="0.5" />
          ))}

          {/* ── Simplified continent outlines (decorative) ── */}
          {/* North America */}
          <path d="M120,90 L240,80 L270,180 L230,260 L160,270 L110,200 Z"
            fill="#16213e" stroke="#1e2d4a" strokeWidth="1" opacity="0.8" />
          {/* South America */}
          <path d="M175,270 L255,260 L275,360 L230,385 L175,370 L155,320 Z"
            fill="#16213e" stroke="#1e2d4a" strokeWidth="1" opacity="0.8" />
          {/* Europe */}
          <path d="M420,80 L560,75 L580,160 L510,175 L430,165 Z"
            fill="#16213e" stroke="#1e2d4a" strokeWidth="1" opacity="0.8" />
          {/* Africa */}
          <path d="M430,165 L560,160 L570,325 L490,350 L420,320 L415,220 Z"
            fill="#16213e" stroke="#1e2d4a" strokeWidth="1" opacity="0.8" />
          {/* Middle East */}
          <path d="M560,155 L620,150 L640,220 L580,230 Z"
            fill="#16213e" stroke="#1e2d4a" strokeWidth="1" opacity="0.8" />
          {/* Asia */}
          <path d="M560,75 L760,70 L780,200 L720,260 L630,240 L580,230 L560,155 Z"
            fill="#16213e" stroke="#1e2d4a" strokeWidth="1" opacity="0.8" />
          {/* Oceania */}
          <path d="M680,280 L780,270 L785,340 L700,355 Z"
            fill="#16213e" stroke="#1e2d4a" strokeWidth="1" opacity="0.8" />

          {/* ── Equator line ── */}
          <line x1="0" y1="210" x2="800" y2="210"
            stroke="#1e3a5f" strokeWidth="0.8" strokeDasharray="4,4" opacity="0.5" />
          <text x="4" y="208" fill="#1e3a5f" fontSize="8" fontFamily="monospace" opacity="0.6">0°</text>

          {/* ── Region overlays ── */}
          {mapped.map(({ region, value, config }, i) => {
            const color  = getColor(value, maxVal);
            const isHov  = hovered === region;
            const ratio  = value / maxVal;
            const pulseR = config.rx * 0.35;

            return (
              <g key={region}
                onMouseEnter={() => setHovered(region)}
                onMouseLeave={() => setHovered(null)}
                style={{ cursor: "pointer" }}>

                {/* Outer glow ring (animated) */}
                <ellipse
                  cx={config.cx} cy={config.cy}
                  rx={config.rx * (isHov ? 1.15 : 1)}
                  ry={config.ry * (isHov ? 1.15 : 1)}
                  fill={color}
                  opacity={isHov ? 0.12 : 0.06}
                  style={{ transition: "all 0.3s ease" }}
                />

                {/* Middle ring */}
                <ellipse
                  cx={config.cx} cy={config.cy}
                  rx={config.rx * 0.65}
                  ry={config.ry * 0.65}
                  fill={color}
                  opacity={isHov ? 0.18 : 0.10}
                  style={{ transition: "all 0.3s ease" }}
                />

                {/* Pulse animation circle */}
                <circle cx={config.cx} cy={config.cy} r={pulseR}
                  fill="none" stroke={color} strokeWidth="1.5"
                  opacity={0.4}>
                  <animate attributeName="r"
                    values={`${pulseR};${pulseR * 1.8};${pulseR}`}
                    dur={`${2 + i * 0.3}s`} repeatCount="indefinite" />
                  <animate attributeName="opacity"
                    values="0.4;0;0.4" dur={`${2 + i * 0.3}s`} repeatCount="indefinite" />
                </circle>

                {/* Core dot */}
                <circle
                  cx={config.cx} cy={config.cy}
                  r={isHov ? 8 : 5 + ratio * 6}
                  fill={color}
                  opacity={isHov ? 1 : 0.85}
                  style={{ transition: "all 0.25s ease" }}
                />

                {/* Inner white dot */}
                <circle cx={config.cx} cy={config.cy} r={2}
                  fill="white" opacity={0.8} />

                {/* Label */}
                <text
                  x={config.cx} y={config.cy - (isHov ? 14 : 12)}
                  textAnchor="middle"
                  fill={color}
                  fontSize={isHov ? "9" : "8"}
                  fontFamily="monospace"
                  fontWeight="bold"
                  opacity={isHov ? 1 : 0.75}
                  style={{ transition: "all 0.25s ease", pointerEvents: "none" }}>
                  {config.shortLabel}
                </text>

                {/* Value label (shown on hover) */}
                {isHov && (
                  <text
                    x={config.cx} y={config.cy + 20}
                    textAnchor="middle"
                    fill={color}
                    fontSize="9"
                    fontFamily="monospace"
                    fontWeight="bold">
                    {fmt(value)}
                  </text>
                )}
              </g>
            );
          })}

          {/* ── Tooltip box ── */}
          {hovered && (() => {
            const entry = mapped.find(m => m.region === hovered);
            if (!entry) return null;
            const { value, config } = entry;
            const color   = getColor(value, maxVal);
            const pct     = ((value / total) * 100).toFixed(1);
            const tx      = Math.min(config.cx + 15, 660);
            const ty      = Math.max(config.cy - 50, 10);
            return (
              <g>
                <rect x={tx} y={ty} width="120" height="52" rx="6"
                  fill="#18181b" stroke={color} strokeWidth="1" opacity="0.95" />
                <text x={tx + 8} y={ty + 14} fill={color}
                  fontSize="9" fontFamily="monospace" fontWeight="bold">
                  {hovered.toUpperCase()}
                </text>
                <text x={tx + 8} y={ty + 27} fill="#e4e4e7"
                  fontSize="10" fontFamily="monospace" fontWeight="bold">
                  {fmt(value)}
                </text>
                <text x={tx + 8} y={ty + 42} fill="#71717a"
                  fontSize="9" fontFamily="monospace">
                  {pct}% of total
                </text>
              </g>
            );
          })()}
        </svg>
      </div>

      {/* ── Region list below map ── */}
      <div className="px-4 pb-4 grid grid-cols-2 gap-x-4 gap-y-1.5">
        {entries
          .sort(([, a], [, b]) => b - a)
          .map(([region, value]) => {
            const color = getColor(value, maxVal);
            const pct   = ((value / total) * 100).toFixed(1);
            return (
              <div key={region}
                className={`flex items-center gap-2 py-1 px-2 rounded-lg transition-colors cursor-default
                  ${hovered === region ? "bg-zinc-800/60" : "hover:bg-zinc-800/30"}`}
                onMouseEnter={() => setHovered(region)}
                onMouseLeave={() => setHovered(null)}>
                <span className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: color }} />
                <span className="text-[10px] text-zinc-400 truncate flex-1">{region}</span>
                <span className="text-[10px] font-mono flex-shrink-0"
                  style={{ color }}>{fmt(value)}</span>
                <span className="text-[9px] font-mono text-zinc-600 flex-shrink-0 w-8 text-right">
                  {pct}%
                </span>
              </div>
            );
          })}
      </div>
    </div>
  );
}
