/**
 * SessionManager
 * 
 * Manages the current session ID and captures session metadata.
 * Session rotates after each verify() call.
 */

import type { SessionMetadata } from '../types'

export class SessionManager {
  private _id: string
  private _metadata: SessionMetadata

  constructor() {
    this._id = this.generateId()
    this._metadata = this.captureMetadata()
  }

  get id(): string {
    return this._id
  }

  get metadata(): SessionMetadata {
    return this._metadata
  }

  /**
   * Rotate session. Call after each verify() to avoid
   * correlating signals from different form submissions.
   */
  rotate(): void {
    this._id = this.generateId()
    this._metadata = this.captureMetadata()
  }

  private generateId(): string {
    // crypto.randomUUID is available in all modern browsers
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID()
    }
    // Fallback for older browsers
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0
      const v = c === 'x' ? r : (r & 0x3) | 0x8
      return v.toString(16)
    })
  }

  private captureMetadata(): SessionMetadata {
    if (typeof window === 'undefined') {
      return {
        viewport_width: 0,
        viewport_height: 0,
        screen_width: 0,
        screen_height: 0,
        device_pixel_ratio: 1,
        timezone_offset: 0,
        page_load_time: 0,
        connection_type: null,
        touch_support: false,
        language: 'en',
      }
    }

    const nav = navigator as Navigator & {
      connection?: { effectiveType?: string }
    }

    return {
      viewport_width: window.innerWidth,
      viewport_height: window.innerHeight,
      screen_width: screen.width,
      screen_height: screen.height,
      device_pixel_ratio: window.devicePixelRatio ?? 1,
      timezone_offset: new Date().getTimezoneOffset(),
      page_load_time: Math.round(performance.now()),
      connection_type: nav.connection?.effectiveType ?? null,
      touch_support: 'ontouchstart' in window,
      language: navigator.language ?? 'en',
    }
  }
}
