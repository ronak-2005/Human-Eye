// ============================================================
// HumanEye Browser SDK — Types
// ============================================================

export interface HumanEyeConfig {
  /** Your HumanEye API key (he_live_... or he_test_...) */
  apiKey: string
  /** Override API base URL. Defaults to https://api.humaneye.io */
  apiBase?: string
  /** Context about the current action being verified */
  context?: ActionContext
  /** Enable console debug logging */
  debug?: boolean
  /** Max mouse capture rate in Hz. Default: 50. Higher = more bandwidth. */
  sampleRate?: number
  /** How often (ms) to flush signal batches to server. Default: 500 */
  batchInterval?: number
  /** Called when a non-fatal error occurs (e.g. network failure) */
  onError?: (err: Error) => void
}

export interface ActionContext {
  action_type?: ActionType
  [key: string]: unknown
}

export type ActionType =
  | 'job_application'
  | 'review_submission'
  | 'account_creation'
  | 'financial_transaction'
  | 'exam_submission'
  | 'general'

export interface VerifyOptions {
  /**
   * Free-form text to analyze (resume, cover letter, review body, etc.)
   * Enables text analysis layer.
   */
  text_content?: string
  /** Your platform's user ID for this person */
  platform_user_id?: string
}

export interface VerifyResult {
  verification_id: string | null
  /** 0–100. null on error (graceful degradation). */
  score: number | null
  verdict: 'human' | 'likely_human' | 'uncertain' | 'suspicious' | 'blocked' | 'error'
  confidence: 'high' | 'medium' | 'low' | null
  flags: Array<{
    code: string
    severity: 'low' | 'medium' | 'high' | 'critical'
    message: string
  }>
  processing_time_ms: number | null
  signals_analyzed: string[]
}

// ── Internal signal types ──────────────────────────────────────

/**
 * SECURITY NOTE: key field contains ONLY the KeyboardEvent.code value
 * (e.g. "KeyA", "Space", "Enter") — NEVER the actual character typed.
 * The character value (KeyboardEvent.key) is intentionally NOT captured.
 */
export interface KeystrokeEvent {
  /** KeyboardEvent.code — physical key position (NOT the character) */
  code: string
  /** Performance.now() timestamp when key was pressed */
  down: number
  /** Performance.now() timestamp when key was released */
  up: number
}

export interface MouseEvent {
  x: number
  y: number
  /** Performance.now() */
  t: number
  /** 'm'=move, 'c'=click, 'e'=enter, 'l'=leave */
  type: 'm' | 'c' | 'e' | 'l'
}

export interface ScrollEvent {
  /** scrollY position */
  y: number
  /** Performance.now() */
  t: number
  /** 'd'=down, 'u'=up */
  dir: 'd' | 'u'
  /** px/ms velocity */
  v: number
}

export interface SDKSignals {
  keystrokes: KeystrokeEvent[]
  mouseEvents: MouseEvent[]
  scrollEvents: ScrollEvent[]
}

export interface SessionMetadata {
  viewport_width: number
  viewport_height: number
  screen_width: number
  screen_height: number
  device_pixel_ratio: number
  timezone_offset: number
  page_load_time: number
  connection_type: string | null
  touch_support: boolean
  language: string
}

// ── Batch sender types ─────────────────────────────────────────

export interface BatchSenderConfig {
  apiBase: string
  apiKey: string
  batchInterval: number
  debug: boolean
  onError: (err: Error) => void
}

export interface CollectorConfig {
  sampleRate: number
  debug: boolean
  onBatch: (signals: SDKSignals) => void
}
