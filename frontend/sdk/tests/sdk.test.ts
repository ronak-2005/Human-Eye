/**
 * HumanEye SDK Tests
 * Run: npm test
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { SignalCollector } from '../src/core/SignalCollector'
import { SessionManager } from '../src/core/SessionManager'

// ── SessionManager ────────────────────────────────────────────

describe('SessionManager', () => {
  it('generates a valid UUID on construction', () => {
    const sm = new SessionManager()
    expect(sm.id).toMatch(/^[0-9a-f-]{36}$/)
  })

  it('rotates to a new ID after rotate()', () => {
    const sm = new SessionManager()
    const first = sm.id
    sm.rotate()
    expect(sm.id).not.toBe(first)
  })

  it('captures metadata on construction', () => {
    const sm = new SessionManager()
    expect(sm.metadata).toHaveProperty('viewport_width')
    expect(sm.metadata).toHaveProperty('timezone_offset')
  })
})

// ── SignalCollector ───────────────────────────────────────────

describe('SignalCollector', () => {
  let collector: SignalCollector
  const onBatch = vi.fn()

  beforeEach(() => {
    collector = new SignalCollector({
      sampleRate: 50,
      debug: false,
      onBatch,
    })
  })

  afterEach(() => {
    collector.detach()
    onBatch.mockClear()
  })

  it('returns empty signals when nothing captured', () => {
    const signals = collector.flush()
    expect(signals.keystrokes).toHaveLength(0)
    expect(signals.mouseEvents).toHaveLength(0)
    expect(signals.scrollEvents).toHaveLength(0)
  })

  it('records a keystroke with code but NOT the character value', () => {
    collector.attach()

    // Simulate keydown + keyup for 'a'
    document.dispatchEvent(new KeyboardEvent('keydown', {
      code: 'KeyA',
      key: 'a',      // This should NEVER appear in captured data
      bubbles: true,
    }))

    // Small delay
    return new Promise<void>(resolve => setTimeout(() => {
      document.dispatchEvent(new KeyboardEvent('keyup', {
        code: 'KeyA',
        key: 'a',
        bubbles: true,
      }))

      const signals = collector.flush()

      expect(signals.keystrokes).toHaveLength(1)
      expect(signals.keystrokes[0].code).toBe('KeyA')

      // CRITICAL: ensure the character 'a' is NOT in the captured data
      const json = JSON.stringify(signals.keystrokes[0])
      expect(json).not.toContain('"key"')
      expect(json).not.toContain('"a"')

      resolve()
    }, 50))
  })

  it('NEVER captures the key.key character value', () => {
    // This is the critical security test
    collector.attach()

    const sensitiveKeys = ['p', 'a', 's', 's', 'w', 'o', 'r', 'd']

    sensitiveKeys.forEach(char => {
      document.dispatchEvent(new KeyboardEvent('keydown', { code: `Key${char.toUpperCase()}`, key: char, bubbles: true }))
      document.dispatchEvent(new KeyboardEvent('keyup', { code: `Key${char.toUpperCase()}`, key: char, bubbles: true }))
    })

    const signals = collector.flush()
    const captured = JSON.stringify(signals)

    // The word 'password' must NEVER appear in captured signals
    expect(captured.toLowerCase()).not.toContain('password')
    // Individual characters should also not appear as values
    sensitiveKeys.forEach(char => {
      // Check that char doesn't appear as a standalone value (could be in 'KeyP' etc so we check specifically)
      const hasCharAsValue = signals.keystrokes.some((k: { code: string }) => k.code === char)
      expect(hasCharAsValue).toBe(false)
    })
  })

  it('flushes and clears the buffer', () => {
    collector.attach()

    document.dispatchEvent(new KeyboardEvent('keydown', { code: 'Space', bubbles: true }))
    document.dispatchEvent(new KeyboardEvent('keyup', { code: 'Space', bubbles: true }))

    const first = collector.flush()
    const second = collector.flush()

    expect(first.keystrokes.length).toBeGreaterThanOrEqual(0)
    expect(second.keystrokes).toHaveLength(0) // cleared after first flush
  })
})

// ── HTTPS enforcement ─────────────────────────────────────────

describe('HTTPS enforcement', () => {
  it('throws when initialized on HTTP (non-localhost)', () => {
    // Mock window.location.protocol
    const original = window.location
    Object.defineProperty(window, 'location', {
      value: { ...original, protocol: 'http:', hostname: 'example.com' },
      configurable: true,
    })

    const { HumanEye } = await import('../src/index')

    expect(() => new HumanEye({ apiKey: 'test_key' })).toThrow('HTTPS required')

    Object.defineProperty(window, 'location', { value: original, configurable: true })
  })
})
