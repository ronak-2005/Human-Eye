'use client'

import { use } from 'react'
import { useVerification } from '../../../../hooks/index'
import { ScoreGauge, VerdictBadge } from '../../../../components/ScoreGauge'

export default function VerificationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { data: v, isLoading } = useVerification(id)

  if (isLoading) return <LoadingSkeleton />
  if (!v) return <div style={styles.empty}>Verification not found.</div>

  return (
    <div className="animate-fade-up">
      {/* Back */}
      <a href="/dashboard/verifications" style={styles.back}>← Back to verifications</a>

      {/* Header row */}
      <div style={styles.headerRow}>
        <div>
          <h1 style={styles.title}>Verification Detail</h1>
          <p style={styles.verificationId} className="mono">{v.id}</p>
        </div>
        <ScoreGauge score={v.score} verdict={v.verdict} size="lg" />
      </div>

      {/* Meta grid */}
      <div style={styles.metaGrid}>
        <MetaCard label="Verdict"><VerdictBadge verdict={v.verdict} /></MetaCard>
        <MetaCard label="Confidence"><span style={{ ...styles.chip, color: v.confidence === 'high' ? 'var(--teal-400)' : v.confidence === 'medium' ? 'var(--score-uncertain)' : 'var(--score-suspicious)' }}>{v.confidence}</span></MetaCard>
        <MetaCard label="Action type"><span style={styles.chip}>{v.action_type.replace(/_/g, ' ')}</span></MetaCard>
        <MetaCard label="Processing time"><span style={styles.monoVal}>{v.processing_time_ms}ms</span></MetaCard>
        <MetaCard label="IP address"><span style={styles.monoVal}>{v.ip_address}</span></MetaCard>
        <MetaCard label="Created"><span style={styles.monoVal}>{new Date(v.created_at).toLocaleString()}</span></MetaCard>
      </div>

      <div style={styles.twoCol}>
        {/* Signal Breakdown */}
        <div className="card" style={styles.card}>
          <h2 style={styles.cardTitle}>Signal Breakdown</h2>
          <div style={styles.signals}>
            {v.signals_analyzed.map((s) => (
              <SignalRow key={s.signal} signal={s} />
            ))}
          </div>
        </div>

        {/* Flags */}
        <div className="card" style={styles.card}>
          <h2 style={styles.cardTitle}>
            Flags Raised
            {v.flags.length > 0 && (
              <span style={styles.flagBadge}>{v.flags.length}</span>
            )}
          </h2>
          {v.flags.length === 0
            ? <p style={styles.noFlags}>✓ No flags raised. Signal is clean.</p>
            : v.flags.map((f) => <FlagRow key={f.code} flag={f} />)
          }
        </div>
      </div>

      {/* Raw user agent */}
      <div className="card" style={{ ...styles.card, marginTop: 16 }}>
        <h2 style={styles.cardTitle}>User Agent</h2>
        <pre style={styles.pre}>{v.user_agent}</pre>
      </div>
    </div>
  )
}

function SignalRow({ signal: s }: { signal: { signal: string; score: number; confidence: string; anomalies: string[] } }) {
  const pct = Math.round(s.score * 100)
  const color = pct >= 80 ? 'var(--score-human)' : pct >= 60 ? 'var(--score-likely)' : pct >= 40 ? 'var(--score-uncertain)' : 'var(--score-blocked)'
  return (
    <div style={styles.signalRow}>
      <div style={styles.signalMeta}>
        <span style={styles.signalName}>{s.signal.toUpperCase()}</span>
        <span style={{ ...styles.signalScore, color }}>{pct}</span>
      </div>
      <div style={styles.signalBar}>
        <div style={{ ...styles.signalFill, width: `${pct}%`, background: color }} />
      </div>
      {s.anomalies.length > 0 && (
        <div style={styles.anomalies}>
          {s.anomalies.map((a, i) => (
            <span key={i} style={styles.anomaly}>⚠ {a}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function FlagRow({ flag: f }: { flag: { code: string; severity: string; message: string; detail: string } }) {
  const color = f.severity === 'critical' ? 'var(--score-blocked)' : f.severity === 'high' ? 'var(--score-suspicious)' : f.severity === 'medium' ? 'var(--score-uncertain)' : 'var(--text-muted)'
  return (
    <div style={{ ...styles.flagRow, borderLeftColor: color }}>
      <div style={styles.flagHeader}>
        <span style={{ ...styles.flagCode, color }} className="mono">{f.code}</span>
        <span style={{ ...styles.severityBadge, color, borderColor: `${color}40`, background: `${color}18` }}>{f.severity}</span>
      </div>
      <p style={styles.flagMsg}>{f.message}</p>
      <p style={styles.flagDetail}>{f.detail}</p>
    </div>
  )
}

function MetaCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={styles.metaCard}>
      <div style={styles.metaLabel}>{label}</div>
      <div>{children}</div>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div>
      <div className="skeleton" style={{ height: 24, width: 120, marginBottom: 24 }} />
      <div style={{ display: 'flex', gap: 24, marginBottom: 32 }}>
        <div style={{ flex: 1 }}>
          <div className="skeleton" style={{ height: 36, width: '60%', marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 16, width: '40%' }} />
        </div>
        <div className="skeleton" style={{ width: 160, height: 160, borderRadius: '50%' }} />
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  back: { display: 'inline-block', fontSize: 12, color: 'var(--text-muted)', textDecoration: 'none', fontFamily: 'var(--font-mono)', marginBottom: 24 },
  headerRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 },
  title: { fontSize: 24, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 6 },
  verificationId: { fontSize: 11, color: 'var(--text-muted)' },
  metaGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 },
  metaCard: { background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-md)', padding: '14px 18px' },
  metaLabel: { fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 },
  chip: { fontSize: 11, padding: '3px 10px', borderRadius: 100, background: 'var(--bg-overlay)', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', textTransform: 'capitalize' },
  monoVal: { fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' },
  twoCol: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
  card: { padding: '20px 24px' },
  cardTitle: { fontSize: 13, fontWeight: 700, letterSpacing: '-0.01em', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 },
  flagBadge: { fontSize: 10, padding: '2px 7px', borderRadius: 100, background: 'rgba(244,63,94,0.15)', color: 'var(--score-blocked)', fontFamily: 'var(--font-mono)' },
  signals: { display: 'flex', flexDirection: 'column', gap: 14 },
  signalRow: { display: 'flex', flexDirection: 'column', gap: 4 },
  signalMeta: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  signalName: { fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.06em' },
  signalScore: { fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 700 },
  signalBar: { height: 5, background: 'var(--bg-overlay)', borderRadius: 2.5, overflow: 'hidden' },
  signalFill: { height: '100%', borderRadius: 2.5, transition: 'width 0.6s ease' },
  anomalies: { display: 'flex', flexWrap: 'wrap', gap: 4 },
  anomaly: { fontSize: 10, color: 'var(--score-suspicious)', fontFamily: 'var(--font-mono)' },
  noFlags: { color: 'var(--teal-400)', fontSize: 13, fontFamily: 'var(--font-mono)', padding: '8px 0' },
  flagRow: { borderLeft: '3px solid', paddingLeft: 14, marginBottom: 16 },
  flagHeader: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 },
  flagCode: { fontSize: 11, fontWeight: 600 },
  severityBadge: { fontSize: 9, padding: '1px 7px', borderRadius: 100, border: '1px solid', textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: 'var(--font-mono)' },
  flagMsg: { fontSize: 13, color: 'var(--text-primary)', marginBottom: 3, fontWeight: 500 },
  flagDetail: { fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 },
  pre: { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.6, wordBreak: 'break-all', whiteSpace: 'pre-wrap' },
  empty: { padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' },
}
