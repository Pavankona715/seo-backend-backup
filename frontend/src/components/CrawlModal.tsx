"use client";

import { useState } from "react";
import { X, Globe, Zap, Shield, Code } from "lucide-react";
import { api, CrawlRequest, CrawlResponse } from "@/lib/api";

interface CrawlModalProps {
  onClose: () => void;
  onSuccess: (response: CrawlResponse) => void;
}

export default function CrawlModal({ onClose, onSuccess }: CrawlModalProps) {
  const [url, setUrl] = useState("");
  const [maxDepth, setMaxDepth] = useState(5);
  const [maxPages, setMaxPages] = useState(1000);
  const [useJs, setUseJs] = useState(false);
  const [respectRobots, setRespectRobots] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await api.startCrawl({
        url: url.trim(),
        max_depth: maxDepth,
        max_pages: maxPages,
        use_js_rendering: useJs,
        respect_robots: respectRobots,
      });
      onSuccess(response);
    } catch (err: any) {
      setError(err.message || "Failed to start crawl");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md mx-4">
        <div className="glass-card p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                <Globe size={14} className="text-blue-400" />
              </div>
              <div>
                <h2 className="font-display font-semibold text-foreground">Start New Crawl</h2>
                <p className="text-xs text-muted-foreground">Analyze a website's SEO</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* URL Input */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                Website URL *
              </label>
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
                className="w-full bg-muted/20 border border-border/50 rounded-lg px-3 py-2.5 text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:border-blue-500/50 focus:bg-muted/30 transition-colors"
                required
              />
            </div>

            {/* Settings Grid */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                  Max Depth
                </label>
                <input
                  type="number"
                  value={maxDepth}
                  onChange={(e) => setMaxDepth(parseInt(e.target.value))}
                  min={1}
                  max={10}
                  className="w-full bg-muted/20 border border-border/50 rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-blue-500/50 transition-colors"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                  Max Pages
                </label>
                <input
                  type="number"
                  value={maxPages}
                  onChange={(e) => setMaxPages(parseInt(e.target.value))}
                  min={1}
                  max={50000}
                  step={1}
                  className="w-full bg-muted/20 border border-border/50 rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-blue-500/50 transition-colors"
                />
              </div>
            </div>

            {/* Toggles */}
            <div className="space-y-2.5">
              <ToggleOption
                icon={<Code size={14} className="text-cyan-400" />}
                label="JavaScript Rendering"
                description="Use Playwright for JS-heavy sites (slower)"
                checked={useJs}
                onChange={setUseJs}
              />
              <ToggleOption
                icon={<Shield size={14} className="text-green-400" />}
                label="Respect robots.txt"
                description="Follow crawl rules from robots.txt"
                checked={respectRobots}
                onChange={setRespectRobots}
              />
            </div>

            {/* Error */}
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-muted-foreground hover:text-foreground border border-border/50 hover:bg-muted/20 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !url.trim()}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Starting...
                  </>
                ) : (
                  <>
                    <Zap size={14} />
                    Start Crawl
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

function ToggleOption({
  icon, label, description, checked, onChange,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-3 p-3 rounded-lg border border-border/30 hover:bg-muted/10 cursor-pointer transition-colors">
      <div className="w-6 h-6 rounded-md bg-muted/20 flex items-center justify-center flex-shrink-0">
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-foreground">{label}</div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
      <div
        onClick={() => onChange(!checked)}
        className={`relative w-9 h-5 rounded-full transition-colors flex-shrink-0 ${
          checked ? "bg-blue-600" : "bg-muted/40"
        }`}
      >
        <div
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            checked ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </div>
    </label>
  );
}