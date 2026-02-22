"use client";

import { useState, useEffect } from "react";
import { Globe, Plus, TrendingUp, AlertTriangle, FileText, Key } from "lucide-react";
import Link from "next/link";
import { api, Site } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import CrawlModal from "@/components/CrawlModal";
import ScoreRing from "@/components/ScoreRing";
import Sidebar from "@/components/layout/Sidebar";

export default function DashboardPage() {
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCrawlModal, setShowCrawlModal] = useState(false);

  const fetchSites = async () => {
    try {
      const data = await api.getSites({ limit: 20 });
      setSites(data);
    } catch (err) {
      console.error("Failed to fetch sites:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSites();
    const interval = setInterval(fetchSites, 15000); // Refresh every 15s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar />

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-6 py-8">

          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="font-display text-3xl font-bold text-foreground">
                SEO Intelligence
              </h1>
              <p className="text-muted-foreground mt-1">
                Monitor, analyze, and optimize your websites
              </p>
            </div>
            <button
              onClick={() => setShowCrawlModal(true)}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2.5 rounded-lg font-medium transition-colors"
            >
              <Plus size={16} />
              New Crawl
            </button>
          </div>

          {/* Stats Overview */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <StatCard
              icon={<Globe size={18} className="text-blue-400" />}
              label="Sites Tracked"
              value={sites.length.toString()}
              sublabel="Active domains"
            />
            <StatCard
              icon={<FileText size={18} className="text-cyan-400" />}
              label="Total Pages"
              value={sites.reduce((sum, s) => sum + s.total_pages, 0).toLocaleString()}
              sublabel="Crawled pages"
            />
            <StatCard
              icon={<TrendingUp size={18} className="text-green-400" />}
              label="Avg Score"
              value="—"
              sublabel="Portfolio average"
            />
            <StatCard
              icon={<AlertTriangle size={18} className="text-orange-400" />}
              label="Open Issues"
              value="—"
              sublabel="Across all sites"
            />
          </div>

          {/* Sites Table */}
          <div className="glass-card overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border/50">
              <h2 className="font-display font-semibold text-foreground">
                Tracked Sites
              </h2>
              <span className="text-xs text-muted-foreground">{sites.length} sites</span>
            </div>

            {loading ? (
              <div className="p-8 text-center">
                <div className="flex items-center justify-center gap-3 text-muted-foreground">
                  <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  Loading sites...
                </div>
              </div>
            ) : sites.length === 0 ? (
              <EmptyState onCrawl={() => setShowCrawlModal(true)} />
            ) : (
              <div className="divide-y divide-border/30">
                {sites.map((site) => (
                  <SiteRow key={site.id} site={site} />
                ))}
              </div>
            )}
          </div>
        </div>
      </main>

      {showCrawlModal && (
        <CrawlModal
          onClose={() => setShowCrawlModal(false)}
          onSuccess={() => {
            setShowCrawlModal(false);
            fetchSites();
          }}
        />
      )}
    </div>
  );
}

function StatCard({
  icon, label, value, sublabel,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sublabel: string;
}) {
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{label}</span>
        {icon}
      </div>
      <div className="text-2xl font-display font-bold text-foreground">{value}</div>
      <div className="text-xs text-muted-foreground">{sublabel}</div>
    </div>
  );
}

function SiteRow({ site }: { site: Site }) {
  return (
    <div className="flex items-center gap-4 px-6 py-4 hover:bg-accent/20 transition-colors group">
      <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center flex-shrink-0">
        <Globe size={14} className="text-blue-400" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Link
            href={`/dashboard/${site.domain}`}
            className="font-medium text-foreground hover:text-blue-400 transition-colors truncate"
          >
            {site.domain}
          </Link>
          <span className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${site.is_active ? "bg-green-500" : "bg-gray-500"}`} />
        </div>
        <div className="text-xs text-muted-foreground truncate mt-0.5">{site.root_url}</div>
      </div>

      <div className="text-right text-xs text-muted-foreground flex-shrink-0">
        <div className="font-medium text-foreground">{site.total_pages.toLocaleString()} pages</div>
        <div>{formatDate(site.last_crawled_at)}</div>
      </div>

      <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
        <Link
          href={`/dashboard/${site.domain}`}
          className="text-xs bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 px-3 py-1.5 rounded-md transition-colors"
        >
          View Report
        </Link>
      </div>
    </div>
  );
}

function EmptyState({ onCrawl }: { onCrawl: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mb-4">
        <Globe size={28} className="text-blue-400" />
      </div>
      <h3 className="font-display font-semibold text-foreground mb-2">No sites tracked yet</h3>
      <p className="text-sm text-muted-foreground max-w-xs mb-6">
        Start your first crawl to analyze a website's SEO performance.
      </p>
      <button
        onClick={onCrawl}
        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition-colors text-sm"
      >
        <Plus size={14} />
        Start First Crawl
      </button>
    </div>
  );
}