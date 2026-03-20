// ============================================================
// HumanEye — Shared TypeScript Types
// These must match the backend FastAPI Pydantic schemas exactly.
// Coordinate with backend engineer before changing anything here.
// ============================================================

export type Verdict = 'human' | 'likely_human' | 'uncertain' | 'suspicious' | 'blocked'
export type Confidence = 'high' | 'medium' | 'low'
export type ActionType =
  | 'job_application'
  | 'review_submission'
  | 'account_creation'
  | 'financial_transaction'
  | 'exam_submission'
  | 'general'

// ── Verification ─────────────────────────────────────────────

export interface SignalAnalysis {
  signal: 'keystroke' | 'mouse' | 'scroll' | 'text' | 'face' | 'voice'
  score: number        // 0-1
  confidence: Confidence
  anomalies: string[]
}

export interface Flag {
  code: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  message: string
  detail: string
}

export interface Verification {
  id: string
  session_id: string
  platform_user_id: string
  score: number          // 0-100
  verdict: Verdict
  confidence: Confidence
  flags: Flag[]
  signals_analyzed: SignalAnalysis[]
  action_type: ActionType
  ip_address: string
  user_agent: string
  processing_time_ms: number
  created_at: string     // ISO 8601
}

export interface VerificationListItem {
  id: string
  platform_user_id: string
  score: number
  verdict: Verdict
  action_type: ActionType
  flags_count: number
  processing_time_ms: number
  created_at: string
}

export interface VerificationListResponse {
  items: VerificationListItem[]
  total: number
  page: number
  page_size: number
  has_next: boolean
}

// ── Trust Score ───────────────────────────────────────────────

export interface TrustScore {
  user_id: string
  current_score: number
  trend: 'up' | 'down' | 'stable'
  total_verifications: number
  last_verified: string
}

// ── API Keys ──────────────────────────────────────────────────

export interface ApiKey {
  id: string
  name: string
  key_preview: string   // e.g. "he_live_xxxx...xxxx"
  created_at: string
  last_used_at: string | null
  usage_count: number
  is_active: boolean
}

export interface CreateApiKeyResponse {
  id: string
  name: string
  key: string           // Full key — shown ONCE only, never again
  created_at: string
}

// ── Dashboard Stats ───────────────────────────────────────────

export interface DashboardStats {
  verifications_today: number
  verifications_this_month: number
  average_score: number
  flag_rate: number           // percentage 0-100
  blocked_rate: number        // percentage 0-100
  human_rate: number          // percentage 0-100
  trend_vs_yesterday: number  // delta
}

// ── Analytics ─────────────────────────────────────────────────

export interface DailyVolume {
  date: string   // YYYY-MM-DD
  count: number
  avg_score: number
}

export interface ScoreDistributionBucket {
  range: string   // e.g. "0-10"
  count: number
}

export interface FlagTypeBreakdown {
  flag_code: string
  label: string
  count: number
  percentage: number
}

export interface AnalyticsResponse {
  daily_volumes: DailyVolume[]
  score_distribution: ScoreDistributionBucket[]
  flag_breakdown: FlagTypeBreakdown[]
  verdict_breakdown: Record<Verdict, number>
}

// ── Auth ──────────────────────────────────────────────────────

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  customer_id: string
  email: string
  company_name: string
}

export interface Customer {
  id: string
  email: string
  company_name: string
  plan: 'starter' | 'growth' | 'scale' | 'enterprise'
  verifications_used: number
  verifications_limit: number
  webhook_url: string | null
  created_at: string
}

// ── Webhooks ──────────────────────────────────────────────────

export interface WebhookConfig {
  url: string
  secret: string
  events: ('verification.complete' | 'score.low' | 'flag.critical')[]
  is_active: boolean
}

// ── WebSocket ─────────────────────────────────────────────────

export interface WSVerificationEvent {
  type: 'verification.complete'
  data: VerificationListItem
}

export interface WSConnectionEvent {
  type: 'connected'
  customer_id: string
}

export type WSEvent = WSVerificationEvent | WSConnectionEvent

// ── API Error ─────────────────────────────────────────────────

export interface ApiError {
  error: string
  message: string
  code: string
}
