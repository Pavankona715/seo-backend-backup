"use client";

import { useEffect, useState } from "react";
import { api, Issue, IssuesResponse } from "@/lib/api";
import { getSeverityBg, truncate, formatDate } from "@/lib/utils";
import { ChevronDown, ChevronUp } from "lucide-react";

interface IssuesListProps {
  domain: string;
}

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"];

export default function IssuesList({ domain }: IssuesListProps) {
  const [data, setData] = useState<IssuesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterSeverity, setFilterSeverity] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        setLoading(true);
        const result = await api.getIssues(domain, { limit: 200 });
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
        Loading issues...
      </div>
    );
  }

  if (!data) return null;

  const issues = data.issues.filter(
    (i) => filterSeverity === "all" || i.severity === filterSeverity
  );

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setFilterSeverity("all")}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            filterSeverity === "all"
              ? "bg-blue-600 text-white"
              : "bg-muted/30 text-muted-foreground hover:text-foreground"
          }`}
        >
          All ({data.total_issues})
        </button>
        {SEVERITY_ORDER.map((sev) => {
          const count = (data.counts_by_severity as any)[sev] || 0;
          if (count === 0) return null;
          return (
            <button
              key={sev}
              onClick={() => setFilterSeverity(sev)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize border ${
                filterSeverity === sev
                  ? getSeverityBg(sev)
                  : "bg-muted/20 text-muted-foreground hover:text-foreground border-transparent"
              }`}
            >
              {sev} ({count})
            </button>
          );
        })}
      </div>

      {/* Issues */}
      <div className="glass-card divide-y divide-border/30 overflow-hidden">
        {issues.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground text-sm">
            No {filterSeverity !== "all" ? filterSeverity : ""} issues found
          </div>
        ) : (
          issues.map((issue) => (
            <IssueRow
              key={issue.id}
              issue={issue}
              expanded={expandedId === issue.id}
              onToggle={() => setExpandedId(expandedId === issue.id ? null : issue.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function IssueRow({
  issue,
  expanded,
  onToggle,
}: {
  issue: Issue;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="transition-colors hover:bg-accent/10">
      <button
        className="w-full flex items-start gap-4 px-5 py-4 text-left"
        onClick={onToggle}
      >
        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium capitalize flex-shrink-0 mt-0.5 border ${getSeverityBg(issue.severity)}`}>
          {issue.severity}
        </span>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm text-foreground">{issue.title}</div>
          {!expanded && (
            <div className="text-xs text-muted-foreground mt-0.5 truncate">
              {issue.description}
            </div>
          )}
        </div>
        <div className="flex-shrink-0 text-muted-foreground">
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-3 text-sm">
          <div>
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Issue</div>
            <p className="text-foreground/80">{issue.description}</p>
          </div>
          {issue.recommendation && (
            <div>
              <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Recommendation</div>
              <p className="text-foreground/80">{issue.recommendation}</p>
            </div>
          )}
          {issue.fix_instructions && (
            <div>
              <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">How to Fix</div>
              <pre className="text-xs bg-muted/20 rounded-lg p-3 whitespace-pre-wrap text-foreground/70 font-mono">
                {issue.fix_instructions}
              </pre>
            </div>
          )}
          {issue.impact_description && (
            <div className="flex gap-2 p-3 bg-blue-500/5 border border-blue-500/15 rounded-lg">
              <span className="text-xs text-blue-400">Impact: {issue.impact_description}</span>
            </div>
          )}
          {issue.affected_element && (
            <div className="text-xs text-muted-foreground">
              Element: <code className="font-mono bg-muted/20 px-1 py-0.5 rounded">{issue.affected_element}</code>
            </div>
          )}
        </div>
      )}
    </div>
  );
}