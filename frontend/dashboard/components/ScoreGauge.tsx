'use client'

import { useMemo } from 'react'
import type { Verdict } from '../lib/types'

interface ScoreGaugeProps {
  score: number
  verdict: Verdict
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

const VERDICT_LABELS: Record<Verdict, string> = {
  human:       'Verified Human',
  likely_human:'Likely Human',
  uncertain:   'Uncertain',
  suspicious:  'Suspicious',
  blocked:     'Blocked',
}

const VERDICT_COLORS: Record<Verdict, string> = {
  human:       'var(--score-human)',
  likely_human:'var(--score-likely)',
  uncertain:   'var(--score-uncertain)',
  suspicious:  'var(--score-suspicious)',
  blocked:     'var(--score-blocked)',
}

function verdictFromScore(score: number): Verdict {
  if (score >= 80) return 'human'
  if (score >= 65) return 'likely_human'
  if (score >= 50) return 'uncertain'
  if (score >= 25) return 'suspicious'
  return 'blocked'
}

const SIZES = {
  sm: { outer: 72,  inner: 56,  stroke: 6,  fontSize: 18 },
  md: { outer: 110, inner: 86,  stroke: 8,  fontSize: 26 },
  lg: { outer: 160, inner: 126, stroke: 10, fontSize: 38 },
}

export function ScoreGauge({ score, verdict, size = 'md', showLabel = true }: ScoreGaugeProps) {
  const s = SIZES[size]
  const resolvedVerdict = verdict || verdictFromScore(score)
  const color = VERDICT_COLORS[resolvedVerdict]

  const { dashArray, dashOffset, circumference } = useMemo(() => {
    const r = (s.outer - s.stroke) / 2
    const circ = 2 * Math.PI * r
    // Gauge is 270° arc (start from bottom-left, go clockwise)
    const arcLength = circ * 0.75
    const offset = circ - (score / 100) * arcLength
    return { dashArray: `${arcLength} ${circ - arcLength}`, dashOffset: offset, circumference: circ }
  }, [score, s])

  const cx = s.outer / 2
  const cy = s.outer / 2
  const r = (s.outer - s.stroke) / 2

  return (
    <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
      <div style={{ position: 'relative', width: s.outer, height: s.outer }}>
        <svg
          width={s.outer}
          height={s.outer}
          style={{ transform: 'rotate(135deg)', display: 'block' }}
        >
          {/* Track */}
          <circle
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke="var(--bg-overlay)"
            strokeWidth={s.stroke}
            strokeDasharray={`${2 * Math.PI * r * 0.75} ${2 * Math.PI * r * 0.25}`}
            strokeDashoffset={0}
            strokeLinecap="round"
          />
          {/* Progress */}
          <circle
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke={color}
            strokeWidth={s.stroke}
            strokeDasharray={dashArray}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 0.8s cubic-bezier(0.4,0,0.2,1), stroke 0.3s' }}
          />
        </svg>

        {/* Score number centered */}
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          textAlign: 'center',
          pointerEvents: 'none',
        }}>
          <div style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 800,
            fontSize: s.fontSize,
            color,
            lineHeight: 1,
            letterSpacing: '-0.03em',
          }}>
            {score}
          </div>
          {size !== 'sm' && (
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '9px',
              color: 'var(--text-muted)',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              marginTop: '2px',
            }}>
              / 100
            </div>
          )}
        </div>
      </div>

      {showLabel && (
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: size === 'sm' ? '10px' : '12px',
          color,
          letterSpacing: '0.04em',
          fontWeight: 500,
          textTransform: 'uppercase',
        }}>
          {VERDICT_LABELS[resolvedVerdict]}
        </div>
      )}
    </div>
  )
}

// Compact inline score badge
export function ScoreBadge({ score, verdict }: { score: number; verdict: Verdict }) {
  const resolvedVerdict = verdict || verdictFromScore(score)
  const color = VERDICT_COLORS[resolvedVerdict]
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '5px',
      padding: '3px 8px',
      borderRadius: '100px',
      background: `${color}18`,
      border: `1px solid ${color}40`,
      fontFamily: 'var(--font-mono)',
      fontSize: '11px',
      fontWeight: 600,
      color,
      whiteSpace: 'nowrap',
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: color, flexShrink: 0 }} />
      {score}
    </span>
  )
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const color = VERDICT_COLORS[verdict]
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '5px',
      padding: '3px 10px',
      borderRadius: '100px',
      background: `${color}18`,
      border: `1px solid ${color}40`,
      fontFamily: 'var(--font-mono)',
      fontSize: '11px',
      fontWeight: 500,
      color,
      textTransform: 'uppercase',
      letterSpacing: '0.04em',
      whiteSpace: 'nowrap',
    }}>
      {VERDICT_LABELS[verdict]}
    </span>
  )
}
