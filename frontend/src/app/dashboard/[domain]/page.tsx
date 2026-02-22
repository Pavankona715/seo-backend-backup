"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Globe, XCircle } from "lucide-react";
import Link from "next/link";
import { api, ReportResponse } from "@/lib/api";
import { formatDate, getSeverityBg } from "@/lib/utils";
import Sidebar from "@/components/layout/Sidebar";
import ScoreRing from "@/components/ScoreRing";
import ScoreBreakdownChart from "@/components/charts/ScoreBreakdownChart";
import IssuesList from "@/components/IssuesList";
import KeywordTable from "@/components/KeywordTable";

export default function DomainDashboard() {
  const params = useParams();
  const domain = params.domain as string;

  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "issues" | "keywords">("overview");

  useEffect(() => {
    const fetchReport = async () => {
      try {
        setLoading(true);
        const data = await api.getReport(domain);
        setReport(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [domain]);

  if (loading) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-3 text-muted-foreground">
            <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            Loading report...
          </div>
        </main>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <XCircle size={40} className="text-red-400 mx-auto mb-4" />
            <h2 className="font-display text-xl font-semibold mb-2">Report Not Found</h2>
            <p className="text-muted-foreground mb-4 text-sm max-w-sm">{error || "No data found."}</p>
            <Link href="/" className="text-blue-400 hover:text-blue-300 text-sm">Back to dashboard</Link>
          </div>
        </main>
      </div>
    );
  }

  const score = report.score;
  const issueSummary = report.issue_summary;
  const totalIssues = issueSummary.critical + issueSummary.high + issueSummary.medium + issueSummary.low;
  const isRunning = report.recent_job?.status === "running";

  const TABS = [
    { id: "overview" as const, label: "Overview" },
    { id: "issues" as const, label: `Issues (${totalIssues})` },
    { id: "keywords" as const, label: "Keywords" },
  ];

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-6 py-8">

          {/* Header */}
          <div className="flex items-start justify-between mb-8">
            <div>
              <Link href="/" className="text-xs text-muted-foreground hover:text-foreground transition-colors mb-2 block">
                ← All Sites
              </Link>
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                  <Globe size={16} className="text-blue-400" />
                </div>
                <div>
                  <h1 className="font-display text-2xl font-bold">{domain}</h1>
                  <p className="text-xs text-muted-foreground">
                    {report.pages_overview.total_pages} pages · Last crawled {formatDate(report.site.last_crawled_at)}
                  </p>
                </div>
              </div>
            </div>
            {isRunning && (
              <div className="flex items-center gap-2 bg-blue-500/10 text-blue-400 px-3 py-1.5 rounded-full text-sm border border-blue-500/20">
                <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                Crawling in progress
              </div>
            )}
          </div>

          {/* Score Overview */}
          {score && (
            <div className="grid grid-cols-6 gap-4 mb-8">
              <div className="col-span-2 glass-card p-6 flex flex-col items-center justify-center gap-3">
                <ScoreRing score={score.overall_score} size={120} />
                <div className="text-center">
                  <div className="font-display font-bold text-foreground">Overall Score</div>
                  <div className="text-xs text-muted-foreground">Site-wide average</div>
                </div>
              </div>
              {[
                { label: "Technical", value: score.technical_score },
                { label: "Content", value: score.content_score },
                { label: "Authority", value: score.authority_score },
                { label: "Linking", value: score.linking_score },
                { label: "AI Visibility", value: score.ai_visibility_score },
              ].map((s) => (
                <div key={s.label} className="glass-card p-4 flex flex-col items-center gap-2">
                  <ScoreRing score={s.value} size={64} strokeWidth={6} />
                  <div className="text-xs text-muted-foreground text-center">{s.label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Issue Summary */}
          <div className="flex gap-3 mb-6">
            {[
              { severity: "critical", count: issueSummary.critical },
              { severity: "high", count: issueSummary.high },
              { severity: "medium", count: issueSummary.medium },
              { severity: "low", count: issueSummary.low },
            ].map(({ severity, count }) =>
              count > 0 ? (
                <div key={severity} className={`px-3 py-1.5 rounded-full border text-xs font-medium capitalize ${getSeverityBg(severity)}`}>
                  {count} {severity}
                </div>
              ) : null
            )}
          </div>

          {/* Tabs */}
          <div className="flex gap-1 p-1 bg-muted/30 rounded-lg mb-6 w-fit">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? "bg-blue-600 text-white"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab === "overview" && score && (
            <div className="grid grid-cols-2 gap-6">
              <div className="glass-card p-6">
                <h3 className="font-display font-semibold mb-4">Technical Breakdown</h3>
                <ScoreBreakdownChart data={score.technical_breakdown} />
              </div>
              <div className="glass-card p-6">
                <h3 className="font-display font-semibold mb-4">Content Breakdown</h3>
                <ScoreBreakdownChart data={score.content_breakdown} />
              </div>
              {report.top_opportunities.length > 0 && (
                <div className="col-span-2 glass-card p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-display font-semibold">Top Keyword Opportunities</h3>
                    <button onClick={() => setActiveTab("keywords")} className="text-xs text-blue-400 hover:text-blue-300">
                      View all →
                    </button>
                  </div>
                  <KeywordTable keywords={report.top_opportunities.slice(0, 5)} compact={true} />
                </div>
              )}
            </div>
          )}

          {activeTab === "issues" && <IssuesList domain={domain} />}
          {activeTab === "keywords" && <KeywordTable domain={domain} compact={false} />}
        </div>
      </main>
    </div>
  );
}