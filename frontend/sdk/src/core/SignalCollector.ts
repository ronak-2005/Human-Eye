/**
 * SignalCollector
 * 
 * Attaches event listeners to the document and collects behavioral signals.
 * All capture is carefully scoped:
 *   - Keystrokes: code (physical key) + timing only. NEVER key.key (character value).
 *   - Mouse: x/y coordinates + timestamp + event type. Throttled to sampleRate Hz.
 *   - Scroll: position + velocity + direction. Debounced.
 * 
 * SECURITY: No PII captured. No characters captured. No passwords captured.
 */

import type {
  CollectorConfig,
  KeystrokeEvent,
  MouseEvent,
  ScrollEvent,
  SDKSignals,
} from '../types'

export class SignalCollector {
  private keystrokes: KeystrokeEvent[] = []
  private mouseEvents: MouseEvent[] = []
  private scrollEvents: ScrollEvent[] = []

  private pendingKeys = new Map<string, number>() // code → keydown timestamp
  private lastMouseTime = 0
  private lastScrollY = 0
  private lastScrollTime = 0
  private mouseMoveInterval: number

  private config: CollectorConfig
  private attached = false

  // Bound handler references (needed for removeEventListener)
  private _onKeyDown: (e: KeyboardEvent) => void
  private _onKeyUp: (e: KeyboardEvent) => void
  private _onMouseMove: (e: globalThis.MouseEvent) => void
  private _onClick: (e: globalThis.MouseEvent) => void
  private _onMouseEnter: () => void
  private _onMouseLeave: () => void
  private _onScroll: () => void

  // Batch flush timer
  private flushTimer: ReturnType<typeof setInterval> | null = null

  constructor(config: CollectorConfig) {
    this.config = config
    this.mouseMoveInterval = 1000 / config.sampleRate // ms between mouse captures

    this._onKeyDown = this.onKeyDown.bind(this)
    this._onKeyUp = this.onKeyUp.bind(this)
    this._onMouseMove = this.onMouseMove.bind(this)
    this._onClick = this.onMouseClick.bind(this)
    this._onMouseEnter = this.onMouseEnter.bind(this)
    this._onMouseLeave = this.onMouseLeave.bind(this)
    this._onScroll = this.onScroll.bind(this)
  }

  attach(): void {
    if (this.attached || typeof window === 'undefined') return

    document.addEventListener('keydown', this._onKeyDown, { passive: true })
    document.addEventListener('keyup', this._onKeyUp, { passive: true })
    document.addEventListener('mousemove', this._onMouseMove, { passive: true })
    document.addEventListener('click', this._onClick, { passive: true })
    document.addEventListener('mouseenter', this._onMouseEnter, { passive: true })
    document.addEventListener('mouseleave', this._onMouseLeave, { passive: true })
    window.addEventListener('scroll', this._onScroll, { passive: true })

    this.attached = true
  }

  detach(): void {
    if (!this.attached) return

    document.removeEventListener('keydown', this._onKeyDown)
    document.removeEventListener('keyup', this._onKeyUp)
    document.removeEventListener('mousemove', this._onMouseMove)
    document.removeEventListener('click', this._onClick)
    document.removeEventListener('mouseenter', this._onMouseEnter)
    document.removeEventListener('mouseleave', this._onMouseLeave)
    window.removeEventListener('scroll', this._onScroll)

    if (this.flushTimer !== null) {
      clearInterval(this.flushTimer)
      this.flushTimer = null
    }

    this.attached = false
  }

  /**
   * Return all buffered signals and clear the buffer.
   * Called by the SDK before a verify() request.
   */
  flush(): SDKSignals {
    const signals: SDKSignals = {
      keystrokes: [...this.keystrokes],
      mouseEvents: [...this.mouseEvents],
      scrollEvents: [...this.scrollEvents],
    }
    this.keystrokes = []
    this.mouseEvents = []
    this.scrollEvents = []
    this.pendingKeys.clear()
    return signals
  }

  // ── Keystroke handlers ──────────────────────────────────────

  private onKeyDown(e: KeyboardEvent): void {
    // Skip modifier-only events
    if (e.code === 'Meta' || e.code === 'Control' || e.code === 'Alt') return

    // SECURITY: Use e.code (physical key) NEVER e.key (character value)
    this.pendingKeys.set(e.code, performance.now())
  }

  private onKeyUp(e: KeyboardEvent): void {
    const downTime = this.pendingKeys.get(e.code)
    if (downTime === undefined) return

    this.pendingKeys.delete(e.code)

    // Only record if dwell time is plausible (0-2000ms)
    const up = performance.now()
    const dwell = up - downTime
    if (dwell < 0 || dwell > 2000) return

    this.keystrokes.push({
      code: e.code,   // Physical key code ONLY. Never e.key.
      down: Math.round(downTime),
      up: Math.round(up),
    })

    // Cap buffer to prevent memory issues during long sessions
    if (this.keystrokes.length > 2000) {
      this.keystrokes = this.keystrokes.slice(-1000)
    }
  }

  // ── Mouse handlers ──────────────────────────────────────────

  private onMouseMove(e: globalThis.MouseEvent): void {
    const now = performance.now()

    // Throttle to sampleRate Hz
    if (now - this.lastMouseTime < this.mouseMoveInterval) return
    this.lastMouseTime = now

    this.mouseEvents.push({
      x: Math.round(e.clientX),
      y: Math.round(e.clientY),
      t: Math.round(now),
      type: 'm',
    })

    if (this.mouseEvents.length > 5000) {
      this.mouseEvents = this.mouseEvents.slice(-2500)
    }
  }

  private onMouseClick(e: globalThis.MouseEvent): void {
    this.mouseEvents.push({
      x: Math.round(e.clientX),
      y: Math.round(e.clientY),
      t: Math.round(performance.now()),
      type: 'c',
    })
  }

  private onMouseEnter(): void {
    this.mouseEvents.push({ x: 0, y: 0, t: Math.round(performance.now()), type: 'e' })
  }

  private onMouseLeave(): void {
    this.mouseEvents.push({ x: 0, y: 0, t: Math.round(performance.now()), type: 'l' })
  }

  // ── Scroll handler ──────────────────────────────────────────

  private onScroll(): void {
    const now = performance.now()
    const y = window.scrollY
    const dt = now - this.lastScrollTime
    const dy = y - this.lastScrollY

    if (dt < 16) return // max 60fps scroll capture

    const velocity = dt > 0 ? Math.abs(dy / dt) : 0

    this.scrollEvents.push({
      y: Math.round(y),
      t: Math.round(now),
      dir: dy >= 0 ? 'd' : 'u',
      v: Math.round(velocity * 1000) / 1000,
    })

    this.lastScrollY = y
    this.lastScrollTime = now

    if (this.scrollEvents.length > 2000) {
      this.scrollEvents = this.scrollEvents.slice(-1000)
    }
  }
}
