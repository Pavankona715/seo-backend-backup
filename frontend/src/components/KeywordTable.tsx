"use client";

import { useEffect, useState } from "react";
import { api, Keyword, OpportunitiesResponse } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { TrendingUp, ArrowUp } from "lucide-react";

interface KeywordTableProps {
  domain?: string;
  keywords?: Keyword[];
  compact?: boolean;
}

export default function KeywordTable({ domain, keywords: propKeywords, compact = false }: KeywordTableProps) {
  const [data, setData] = useState<OpportunitiesResponse | null>(null);
  const [loading, setLoading] = useState(!propKeywords);

  useEffect(() => {
    if (propKeywords || !domain) return;
    const fetch = async () => {
      try {
        setLoading(true);
        const result = await api.getOpportunities(domain, { limit: 100 });
        setData(result);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [domain]);

  if (loading) {
    return (
      <div className="glass-card p-8 flex items-center justify-center gap-3 text-muted-foreground">
        <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        Loading keywords...
      </div>
    );
  }

  const keywords = propKeywords || data?.opportunities || [];

  if (keywords.length === 0) {
    return (
      <div className="glass-card p-8 text-center text-muted-foreground text-sm">
        No keyword opportunities found. Run a crawl to discover keywords.
      </div>
    );
  }

  const columns = compact
    ? ["Keyword", "Volume", "Difficulty", "Opportunity"]
    : ["Keyword", "Frequency", "Volume", "Difficulty", "Current Rank", "Rank Gap", "CTR", "Opportunity"];

  return (
    <div className={compact ? "" : "glass-card overflow-hidden"}>
      {!compact && data && (
        <div className="px-5 py-4 border-b border-border/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp size={16} className="text-blue-400" />
            <h3 className="font-display font-semibold">Keyword Opportunities</h3>
          </div>
          <span className="text-xs text-muted-foreground">{data.total_keywords} total keywords</span>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/30">
              {columns.map((col) => (
                <th
                  key={col}
                  className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/20">
            {keywords.map((kw) => (
              <tr key={kw.id} className="hover:bg-accent/10 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">{kw.keyword}</span>
                    {kw.is_opportunity && (
                      <span className="inline-flex items-center gap-1 bg-green-500/10 text-green-400 border border-green-500/20 text-xs px-1.5 py-0.5 rounded-full">
                        <ArrowUp size={10} />
                        Opportunity
                      </span>
                    )}
                  </div>
                </td>
                {!compact && (
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">{kw.frequency}</td>
                )}
                <td className="px-4 py-3 text-muted-foreground tabular-nums">{formatNumber(kw.estimated_volume)}</td>
                <td className="px-4 py-3">
                  <DifficultyBadge difficulty={kw.estimated_difficulty} />
                </td>
                {!compact && (
                  <>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums">
                      {kw.current_rank ? `#${kw.current_rank}` : "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums">
                      {kw.rank_gap ? `+${kw.rank_gap}` : "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums">
                      {(kw.estimated_ctr * 100).toFixed(1)}%
                    </td>
                  </>
                )}
                <td className="px-4 py-3">
                  <OpportunityScore score={kw.opportunity_score} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DifficultyBadge({ difficulty }: { difficulty: number }) {
  let cls = "bg-green-500/10 text-green-400 border-green-500/20";
  let label = "Easy";
  if (difficulty >= 70) { cls = "bg-red-500/10 text-red-400 border-red-500/20"; label = "Hard"; }
  else if (difficulty >= 50) { cls = "bg-orange-500/10 text-orange-400 border-orange-500/20"; label = "Medium"; }
  else if (difficulty >= 30) { cls = "bg-yellow-500/10 text-yellow-400 border-yellow-500/20"; label = "Fair"; }

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${cls}`}>
      {difficulty.toFixed(0)} · {label}
    </span>
  );
}

function OpportunityScore({ score }: { score: number }) {
  const w = Math.min(100, score);
  let color = "bg-red-500";
  if (w >= 60) color = "bg-green-500";
  else if (w >= 40) color = "bg-yellow-500";
  else if (w >= 20) color = "bg-orange-500";

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 bg-muted/30 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${w}%` }} />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">{score.toFixed(1)}</span>
    </div>
  );
}