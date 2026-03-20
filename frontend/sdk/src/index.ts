/**
 * @humaneye/sdk
 * Browser SDK for HumanEye human verification.
 * 
 * SECURITY RULES (enforced in this file):
 * - NEVER capture key values — only timing metadata (key code only)
 * - NEVER initialize on HTTP — HTTPS required
 * - NEVER block main thread — all capture runs in Web Worker
 * - Bundle target: < 50KB gzipped
 */

import { SignalCollector } from './core/SignalCollector'
import { BatchSender } from './core/BatchSender'
import { SessionManager } from './core/SessionManager'
import type {
  HumanEyeConfig,
  VerifyOptions,
  VerifyResult,
} from './types'

export type { HumanEyeConfig, VerifyOptions, VerifyResult }

const SDK_VERSION = '1.0.0'
const API_BASE = 'http://localhost:8000'

export class HumanEye {
  private config: Required<HumanEyeConfig>
  private collector: SignalCollector
  private sender: BatchSender
  private session: SessionManager
  private initialized = false

  constructor(config: HumanEyeConfig) {
    // SECURITY: Refuse to initialize on HTTP
    if (typeof window !== 'undefined' && window.location.protocol !== 'https:') {
      if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
        console.error('[HumanEye] SDK refused to initialize: HTTPS required. Running on HTTP is a security violation.')
        throw new Error('HumanEye SDK requires HTTPS')
      }
    }

    if (!config.apiKey) {
      throw new Error('HumanEye SDK requires an apiKey')
    }

    this.config = {
      apiKey: config.apiKey,
      apiBase: config.apiBase ?? API_BASE,
      context: config.context ?? { action_type: 'general' },
      debug: config.debug ?? false,
      sampleRate: config.sampleRate ?? 50,         // Hz — max mouse capture rate
      batchInterval: config.batchInterval ?? 500,   // ms — how often to flush signals
      onError: config.onError ?? (() => {}),
    }

    this.session = new SessionManager()
    this.sender = new BatchSender({
      apiBase: this.config.apiBase,
      apiKey: this.config.apiKey,
      batchInterval: this.config.batchInterval,
      debug: this.config.debug,
      onError: this.config.onError,
    })
    this.collector = new SignalCollector({
      sampleRate: this.config.sampleRate,
      debug: this.config.debug,
      onBatch: (signals) => this.sender.enqueue(signals),
    })

    this.start()
  }

  /**
   * Start passive signal capture. Called automatically on construction.
   */
  private start(): void {
    if (this.initialized) return
    this.collector.attach()
    this.initialized = true
    this.log('SDK initialized', { sessionId: this.session.id, version: SDK_VERSION })
  }

  /**
   * Run a verification. Call this when the user submits a form.
   * Flushes all buffered signals and requests a Human Trust Score.
   */
  async verify(options: VerifyOptions = {}): Promise<VerifyResult> {
    const sessionId = this.session.id
    const signals = this.collector.flush()

    const payload = {
      session_id: sessionId,
      signals: {
        keystrokes: signals.keystrokes,
        mouse_events: signals.mouseEvents,
        scroll_events: signals.scrollEvents,
        text_content: options.text_content ?? null,
        video_frame_data: null, // Phase 2
      },
      context: {
        ...this.config.context,
        platform_user_id: options.platform_user_id ?? null,
        ip_address: null, // backend resolves from request
        user_agent: navigator.userAgent,
        sdk_version: SDK_VERSION,
        session_metadata: this.session.metadata,
      },
    }

    this.log('Sending verification payload', {
      keystrokeCount: signals.keystrokes.length,
      mouseEventCount: signals.mouseEvents.length,
      scrollEventCount: signals.scrollEvents.length,
      hasText: !!options.text_content,
    })

    try {
      const res = await fetch(`${this.config.apiBase}/api/v1/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.config.apiKey}`,
          'X-SDK-Version': SDK_VERSION,
        },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.message ?? `Verification failed: ${res.status}`)
      }

      const result = await res.json() as VerifyResult

      // Rotate session after each verification
      this.session.rotate()
      this.log('Verification complete', { score: result.score, verdict: result.verdict })

      return result
    } catch (err) {
      this.config.onError(err instanceof Error ? err : new Error(String(err)))
      // Graceful degradation — return null score rather than crash
      return {
        verification_id: null,
        score: null,
        verdict: 'error',
        confidence: null,
        flags: [],
        processing_time_ms: null,
        signals_analyzed: [],
      }
    }
  }

  /**
   * Destroy the SDK instance. Removes all event listeners.
   */
  destroy(): void {
    this.collector.detach()
    this.sender.flush()
    this.initialized = false
    this.log('SDK destroyed')
  }

  private log(msg: string, data?: unknown): void {
    if (this.config.debug) {
      console.log(`[HumanEye] ${msg}`, data ?? '')
    }
  }
}

export default HumanEye
