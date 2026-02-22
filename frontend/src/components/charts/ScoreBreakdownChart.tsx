"use client";

interface BreakdownItem {
  avg_score: number;
  max: number;
  pct: number;
}

interface ScoreBreakdownChartProps {
  data: Record<string, BreakdownItem>;
}

function formatKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function getBarColor(pct: number): string {
  if (pct >= 80) return "bg-green-500";
  if (pct >= 60) return "bg-lime-500";
  if (pct >= 40) return "bg-yellow-500";
  if (pct >= 20) return "bg-orange-500";
  return "bg-red-500";
}

export default function ScoreBreakdownChart({ data }: ScoreBreakdownChartProps) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="text-center py-6 text-muted-foreground text-sm">
        No breakdown data available
      </div>
    );
  }

  const items = Object.entries(data)
    .map(([key, val]) => ({ key, label: formatKey(key), pct: val.pct || 0, avg: val.avg_score, max: val.max }))
    .sort((a, b) => a.pct - b.pct);

  return (
    <div className="space-y-3">
      {items.map(({ key, label, pct, avg, max }) => (
        <div key={key}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-muted-foreground">{label}</span>
            <span className="text-xs font-medium tabular-nums">{Math.round(avg)}/{max}</span>
          </div>
          <div className="h-1.5 bg-muted/30 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${getBarColor(pct)}`}
              style={{ width: `${Math.min(100, pct)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}