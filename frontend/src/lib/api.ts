/**
 * バックエンドAPIクライアント
 * 全てのAPIリクエストはここを経由する。
 * 認証トークンの自動付与・エラーハンドリングを一元管理する。
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/** JWTトークンをローカルストレージから取得する */
function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

/** APIリクエスト共通処理 */
async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    // トークン期限切れ → ログインページへ
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    throw new Error("認証が必要です");
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new ApiError(
      errorData.message || `エラー: ${res.status}`,
      res.status,
      errorData.error_code,
      errorData.detail
    );
  }

  // 204 No Content
  if (res.status === 204) return {} as T;

  return res.json();
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public errorCode?: string,
    public detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ─────────────────────────────────────
// 認証
// ─────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    request<{ access_token: string; role: string; email: string; display_name: string; user_id: string }>(
      "/auth/login",
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }
    ),
  me: () => request<{ id: string; email: string; role: string; display_name: string }>("/auth/me"),
};

// ─────────────────────────────────────
// リサーチ候補
// ─────────────────────────────────────
export interface ResearchCandidate {
  id: string;
  title: string;
  brand: string | null;
  model_number: string | null;
  condition: string;
  purchase_price_jpy: number | null;
  target_sale_price_usd: number | null;
  estimated_profit_jpy: number | null;
  estimated_profit_rate: number | null;
  min_profitable_price_usd: number | null;
  total_score: number | null;
  score_override: number | null;
  status: string;
  product_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateResearchCandidateInput {
  title: string;
  brand?: string;
  model_number?: string;
  condition?: string;
  purchase_price_jpy?: number;
  domestic_shipping_jpy?: number;
  international_shipping_usd?: number;
  other_cost_jpy?: number;
  target_sale_price_usd?: number;
  notes?: string;
}

export const researchApi = {
  list: (params?: { status?: string; order_by_score?: boolean; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.order_by_score !== undefined) query.set("order_by_score", String(params.order_by_score));
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.offset) query.set("offset", String(params.offset));
    return request<ResearchCandidate[]>(`/research/?${query}`);
  },
  get: (id: string) => request<ResearchCandidate>(`/research/${id}`),
  create: (data: CreateResearchCandidateInput) =>
    request<ResearchCandidate>("/research/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: Partial<CreateResearchCandidateInput & { status: string; score_override: number; score_override_reason: string }>) =>
    request<ResearchCandidate>(`/research/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  calculateProfit: (id: string, targetPriceUsd: number) =>
    request<Record<string, unknown>>(`/research/${id}/calculate-profit?target_price_usd=${targetPriceUsd}`),
  runScoring: (id: string) =>
    request<ResearchCandidate>(`/research/${id}/score`, { method: "POST" }),
  overrideScore: (id: string, score: number, reason: string) =>
    request<ResearchCandidate>(`/research/${id}/score-override`, {
      method: "POST",
      body: JSON.stringify({ score, reason }),
    }),
};

// ─────────────────────────────────────
// 出品管理
// ─────────────────────────────────────
export interface ListingDraft {
  id: string;
  product_id: string;
  title_candidates: string[] | null;
  title_selected: string | null;
  description_generated: string | null;
  description_edited: string | null;
  item_specifics_candidates: Record<string, string> | null;
  item_specifics_approved: Record<string, string> | null;
  condition: string | null;
  condition_description: string | null;
  listing_price_usd: number | null;
  ebay_category_id: string | null;
  validation_warnings: string[] | null;
  is_valid: boolean;
  status: string;
  submitted_at: string | null;
  reviewed_at: string | null;
  reviewer_note: string | null;
  ebay_offer_id: string | null;
  published_at: string | null;
  ebay_listing_id: string | null;
  created_at: string;
  updated_at: string;
}

export const listingsApi = {
  listDrafts: (status?: string) =>
    request<ListingDraft[]>(`/listings/drafts${status ? `?status=${status}` : ""}`),
  getDraft: (id: string) => request<ListingDraft>(`/listings/drafts/${id}`),
  listPendingApproval: () => request<ListingDraft[]>("/listings/drafts/pending-approval"),
  updateDraft: (id: string, data: Partial<ListingDraft>) =>
    request<ListingDraft>(`/listings/drafts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  submitForReview: (id: string, note?: string) =>
    request<ListingDraft>(`/listings/drafts/${id}/submit-for-review`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  reviewApproval: (approvalId: string, action: "approve" | "reject", note?: string) =>
    request(`/listings/approvals/${approvalId}/review`, {
      method: "POST",
      body: JSON.stringify({ action, note }),
    }),
  generate: (data: {
    product_title: string;
    brand?: string;
    model_number?: string;
    condition?: string;
    features?: string;
    category_hint?: string;
  }) =>
    request<{
      title_candidates: string[];
      description: string;
      item_specifics: Record<string, string>;
      condition_description: string;
      warnings: string[];
      is_valid: boolean;
    }>("/listings/generate", { method: "POST", body: JSON.stringify(data) }),
};

// ─────────────────────────────────────
// ジョブ・監査ログ
// ─────────────────────────────────────
export interface Job {
  id: string;
  job_type: string;
  status: string;
  retry_count: number;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
  is_dry_run: boolean;
}

export const jobsApi = {
  list: (params?: { status?: string; job_type?: string }) => {
    const query = new URLSearchParams(params as Record<string, string>);
    return request<Job[]>(`/jobs/?${query}`);
  },
  getAuditLogs: (resourceType?: string, resourceId?: string) => {
    const query = new URLSearchParams();
    if (resourceType) query.set("resource_type", resourceType);
    if (resourceId) query.set("resource_id", resourceId);
    return request<unknown[]>(`/jobs/audit-logs?${query}`);
  },
};
