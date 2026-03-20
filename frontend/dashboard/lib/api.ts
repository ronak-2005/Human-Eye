// ============================================================
// HumanEye — API Client
// Central fetch wrapper. All hooks go through this.
// Auth token stored in httpOnly cookie — this wrapper just
// sets Content-Type and handles errors uniformly.
// ============================================================

import { ApiError } from './types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export class HumanEyeApiError extends Error {
  constructor(
    public code: string,
    public message: string,
    public status: number,
  ) {
    super(message)
    this.name = 'HumanEyeApiError'
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorBody: ApiError = { error: 'unknown', message: res.statusText, code: String(res.status) }
    try {
      errorBody = await res.json()
    } catch {
      // ignore parse failures
    }
    throw new HumanEyeApiError(errorBody.code, errorBody.message, res.status)
  }
  // Handle 204 No Content
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

function buildHeaders(extra?: Record<string, string>): Headers {
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...extra,
  })
  return headers
}

export const api = {
  get: <T>(path: string): Promise<T> =>
    fetch(`${BASE_URL}${path}`, {
      method: 'GET',
      headers: buildHeaders(),
      credentials: 'include',   // send httpOnly session cookie
    }).then(handleResponse<T>),

  post: <T>(path: string, body?: unknown): Promise<T> =>
    fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: buildHeaders(),
      credentials: 'include',
      body: body ? JSON.stringify(body) : undefined,
    }).then(handleResponse<T>),

  delete: <T>(path: string): Promise<T> =>
    fetch(`${BASE_URL}${path}`, {
      method: 'DELETE',
      headers: buildHeaders(),
      credentials: 'include',
    }).then(handleResponse<T>),

  patch: <T>(path: string, body?: unknown): Promise<T> =>
    fetch(`${BASE_URL}${path}`, {
      method: 'PATCH',
      headers: buildHeaders(),
      credentials: 'include',
      body: body ? JSON.stringify(body) : undefined,
    }).then(handleResponse<T>),
}

// ── Specific API calls (typed) ────────────────────────────────

import type {
  DashboardStats,
  VerificationListResponse,
  Verification,
  TrustScore,
  ApiKey,
  CreateApiKeyResponse,
  AnalyticsResponse,
  LoginRequest,
  LoginResponse,
  Customer,
  WebhookConfig,
} from './types'

export const authApi = {
  login: (body: LoginRequest) =>
    api.post<LoginResponse>('/api/v1/auth/login', body),
  logout: () =>
    api.post<void>('/api/v1/auth/logout'),
  me: () =>
    api.get<Customer>('/api/v1/auth/me'),
  register: (body: { email: string; password: string; company_name: string }) =>
    api.post<void>("/api/v1/auth/register", body),
}

export const verificationsApi = {
  list: (params?: {
    page?: number
    page_size?: number
    verdict?: string
    min_score?: number
    max_score?: number
    action_type?: string
    date_from?: string
    date_to?: string
    search?: string
  }) => {
    const qs = new URLSearchParams()
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== '') qs.set(k, String(v))
      })
    }
    const query = qs.toString() ? `?${qs.toString()}` : ''
    return api.get<VerificationListResponse>(`/api/v1/verifications${query}`)
  },
  get: (id: string) =>
    api.get<Verification>(`/api/v1/verifications/${id}`),
}

export const scoresApi = {
  get: (userId: string) =>
    api.get<TrustScore>(`/api/v1/scores/${userId}`),
}

export const statsApi = {
  dashboard: () =>
    api.get<DashboardStats>('/api/v1/stats/dashboard'),
  analytics: (params?: { period?: '7d' | '30d' | '90d' }) => {
    const qs = params?.period ? `?period=${params.period}` : ''
    return api.get<AnalyticsResponse>(`/api/v1/stats/analytics${qs}`)
  },
}

export const apiKeysApi = {
  list: () =>
    api.get<ApiKey[]>('/api/v1/keys'),
  create: (name: string) =>
    api.post<CreateApiKeyResponse>('/api/v1/keys', { name }),
  revoke: (id: string) =>
    api.delete<void>(`/api/v1/keys/${id}`),
}

export const settingsApi = {
  getWebhook: () =>
    api.get<WebhookConfig | null>('/api/v1/settings/webhook'),
  saveWebhook: (config: Partial<WebhookConfig>) =>
    api.patch<WebhookConfig>('/api/v1/settings/webhook', config),
  getCustomer: () =>
    api.get<Customer>('/api/v1/settings/account'),
  updateCustomer: (data: Partial<Pick<Customer, 'company_name'>>) =>
    api.patch<Customer>('/api/v1/settings/account', data),
}