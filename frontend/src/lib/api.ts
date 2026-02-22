/**
 * API client for the SEO Intelligence Platform backend.
 * All communication with the FastAPI backend happens through this module.
 */

import axios, { AxiosInstance, AxiosError } from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const message =
      (error.response?.data as any)?.error ||
      (error.response?.data as any)?.detail ||
      error.message ||
      "An unexpected error occurred";
    return Promise.reject(new Error(message));
  }
);

// ============================================================
// Type Definitions
// ============================================================

export interface CrawlRequest {
  url: string;
  max_depth?: number;
  max_pages?: number;
  use_js_rendering?: boolean;
  respect_robots?: boolean;
  rate_limit_rps?: number;
}

export interface CrawlResponse {
  job_id: string;
  site_id: string;
  status: string;
  message: string;
  domain: string;
}

export interface CrawlJob {
  id: string;
  site_id: string;
  celery_task_id: string | null;
  status: "pending" | "running" | "paused" | "completed" | "failed" | "cancelled";
  max_depth: number;
  max_pages: number;
  use_js_rendering: boolean;
  respect_robots: boolean;
  pages_crawled: number;
  pages_failed: number;
  pages_queued: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface Site {
  id: string;
  domain: string;
  root_url: string;
  sitemap_url: string | null;
  last_crawled_at: string | null;
  total_pages: number;
  is_active: boolean;
  created_at: string;
}

export interface Score {
  id: string;
  site_id: string;
  page_id: string | null;
  overall_score: number;
  technical_score: number;
  content_score: number;
  authority_score: number;
  linking_score: number;
  ai_visibility_score: number;
  technical_breakdown: Record<string, any>;
  content_breakdown: Record<string, any>;
  linking_breakdown: Record<string, any>;
  scored_at: string;
}

export interface Issue {
  id: string;
  site_id: string;
  page_id: string | null;
  issue_type: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  title: string;
  description: string;
  recommendation: string | null;
  fix_instructions: string | null;
  impact_description: string | null;
  affected_element: string | null;
  is_resolved: boolean;
  created_at: string;
}

export interface IssueSeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface IssuesResponse {
  domain: string;
  total_issues: number;
  counts_by_severity: IssueSeverityCounts;
  issues: Issue[];
}

export interface Keyword {
  id: string;
  keyword: string;
  frequency: number;
  density: number;
  estimated_volume: number;
  estimated_difficulty: number;
  estimated_ctr: number;
  current_rank: number | null;
  rank_gap: number | null;
  opportunity_score: number;
  is_opportunity: boolean;
}

export interface OpportunitiesResponse {
  domain: string;
  total_keywords: number;
  opportunities: Keyword[];
}

export interface PageSummary {
  id: string;
  url: string;
  status_code: number | null;
  title: string | null;
  word_count: number;
  depth: number;
  is_indexable: boolean;
  internal_links_count: number;
  crawled_at: string | null;
}

export interface ReportResponse {
  domain: string;
  site: Site;
  score: Score | null;
  issue_summary: IssueSeverityCounts;
  recent_job: CrawlJob | null;
  top_opportunities: Keyword[];
  pages_overview: {
    total_pages: number;
    last_crawled: string | null;
  };
}

// ============================================================
// API Functions
// ============================================================

export const api = {
  // Crawl
  startCrawl: async (request: CrawlRequest): Promise<CrawlResponse> => {
    const { data } = await apiClient.post("/crawl", request);
    return data;
  },

  getCrawlJob: async (jobId: string): Promise<CrawlJob> => {
    const { data } = await apiClient.get(`/crawl/job/${jobId}`);
    return data;
  },

  // Reports
  getReport: async (domain: string): Promise<ReportResponse> => {
    const { data } = await apiClient.get(`/report/${domain}`);
    return data;
  },

  // Pages
  getPages: async (
    domain: string,
    params?: { skip?: number; limit?: number; status_code?: number }
  ) => {
    const { data } = await apiClient.get(`/pages/${domain}`, { params });
    return data;
  },

  getPage: async (pageId: string) => {
    const { data } = await apiClient.get(`/page/${pageId}`);
    return data;
  },

  // Issues
  getIssues: async (
    domain: string,
    params?: { severity?: string; resolved?: boolean; skip?: number; limit?: number }
  ): Promise<IssuesResponse> => {
    const { data } = await apiClient.get(`/issues/${domain}`, { params });
    return data;
  },

  // Opportunities
  getOpportunities: async (
    domain: string,
    params?: { min_score?: number; limit?: number }
  ): Promise<OpportunitiesResponse> => {
    const { data } = await apiClient.get(`/opportunities/${domain}`, { params });
    return data;
  },

  // Sites
  getSites: async (params?: { skip?: number; limit?: number }): Promise<Site[]> => {
    const { data } = await apiClient.get("/sites", { params });
    return data;
  },

  getSite: async (siteId: string): Promise<Site> => {
    const { data } = await apiClient.get(`/sites/${siteId}`);
    return data;
  },

  // Scores
  getScores: async (domain: string): Promise<Score> => {
    const { data } = await apiClient.get(`/scores/${domain}`);
    return data;
  },
};

export default api;