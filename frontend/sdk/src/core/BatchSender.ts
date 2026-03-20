/**
 * BatchSender
 * 
 * Accumulates signals and POSTs them to /api/v1/signals every batchInterval ms.
 * Batching prevents one-request-per-event flooding.
 * 
 * On API failure: logs silently, never throws.
 * Graceful degradation: if API is down, signals are dropped (not queued forever).
 */

import type { BatchSenderConfig, SDKSignals } from '../types'

export class BatchSender {
  private queue: SDKSignals[] = []
  private timer: ReturnType<typeof setInterval> | null = null
  private config: BatchSenderConfig
  private sending = false

  constructor(config: BatchSenderConfig) {
    this.config = config
    this.startTimer()
  }

  enqueue(signals: SDKSignals): void {
    // Drop empty batches
    if (
      signals.keystrokes.length === 0 &&
      signals.mouseEvents.length === 0 &&
      signals.scrollEvents.length === 0
    ) return

    this.queue.push(signals)
  }

  private startTimer(): void {
    this.timer = setInterval(() => {
      this.sendQueued()
    }, this.config.batchInterval)
  }

  private async sendQueued(): Promise<void> {
    if (this.queue.length === 0 || this.sending) return

    this.sending = true
    const batch = this.queue.splice(0, this.queue.length)

    // Merge all batches into one payload
    const merged: SDKSignals = {
      keystrokes: batch.flatMap(b => b.keystrokes),
      mouseEvents: batch.flatMap(b => b.mouseEvents),
      scrollEvents: batch.flatMap(b => b.scrollEvents),
    }

    try {
      const res = await fetch(`${this.config.apiBase}/api/v1/signals`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.config.apiKey}`,
        },
        body: JSON.stringify(merged),
        keepalive: true, // survive page unload
      })

      if (!res.ok && this.config.debug) {
        console.warn(`[HumanEye] Signal batch rejected: ${res.status}`)
      }
    } catch (err) {
      // Network failure — drop signals, do NOT re-queue
      // (Re-queueing causes unbounded memory growth on persistent failures)
      this.config.onError(err instanceof Error ? err : new Error('Signal send failed'))
    } finally {
      this.sending = false
    }
  }

  /**
   * Force-send any queued signals immediately. Called on verify() and destroy().
   */
  flush(): void {
    this.sendQueued()
  }

  destroy(): void {
    if (this.timer !== null) {
      clearInterval(this.timer)
      this.timer = null
    }
    this.flush()
  }
}
