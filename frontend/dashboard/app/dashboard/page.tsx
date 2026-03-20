'use client'

import { useDashboardStats, useVerifications, useMe } from '../../hooks/index'
import { ScoreBadge, VerdictBadge } from '../../components/ScoreGauge'

export default function DashboardHome() {
  const { data: stats, isLoading: statsLoading } = useDashboardStats()
  const { data: recent } = useVerifications({ page: 1, page_size: 5 })
  const { data: me } = useMe()

  return (
    <div className="animate-fade-up">
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Overview</h1>
          <p style={styles.subtitle}>
            {me?.company_name ?? 'Your workspace'} · {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
          </p>
        </div>
        <div style={styles.planBadge}>
          {me?.plan?.toUpperCase() ?? 'LOADING'}
        </div>
      </div>

      {/* Stat cards */}
      <div style={styles.statsGrid}>
        <StatCard
          label="Verifications today"
          value={stats?.verifications_today ?? 0}
          sub={`${stats?.verifications_this_month ?? 0} this month`}
          loading={statsLoading}
          accent="var(--teal-400)"
        />
        <StatCard
          label="Average trust score"
          value={stats?.average_score?.toFixed(1) ?? '—'}
          sub="Across all verifications"
          loading={statsLoading}
          accent="var(--score-likely)"
        />
        <StatCard
          label="Human rate"
          value={`${stats?.human_rate?.toFixed(1) ?? '—'}%`}
          sub="Score ≥ 80 (verified human)"
          loading={statsLoading}
          accent="var(--score-human)"
        />
        <StatCard
          label="Flag rate"
          value={`${stats?.flag_rate?.toFixed(1) ?? '—'}%`}
          sub="Verifications with flags raised"
          loading={statsLoading}
          accent="var(--score-suspicious)"
        />
        <StatCard
          label="Blocked rate"
          value={`${stats?.blocked_rate?.toFixed(1) ?? '—'}%`}
          sub="Score < 25 (synthetic likely)"
          loading={statsLoading}
          accent="var(--score-blocked)"
        />
        <UsageCard
          used={me?.verifications_used ?? 0}
          limit={me?.verifications_limit ?? 0}
        />
      </div>

      {/* Recent verifications */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <h2 style={styles.sectionTitle}>Recent Verifications</h2>
          <a href="/dashboard/verifications" style={styles.seeAll}>See all →</a>
        </div>

        <div style={styles.table}>
          <div style={styles.tableHead}>
            <span>User ID</span>
            <span>Score</span>
            <span>Verdict</span>
            <span>Action</span>
            <span>Time</span>
          </div>
          {recent?.items.map((v, i) => (
            <a key={v.id} href={`/dashboard/verifications/${v.id}`} style={{
              ...styles.tableRow,
              animationDelay: `${i * 60}ms`,
            }} className="animate-fade-up">
              <span style={styles.mono}>{v.platform_user_id.slice(0, 12)}…</span>
              <ScoreBadge score={v.score} verdict={v.verdict} />
              <VerdictBadge verdict={v.verdict} />
              <span style={styles.actionBadge}>{v.action_type.replace('_', ' ')}</span>
              <span style={styles.muted}>{timeAgo(v.created_at)}</span>
            </a>
          ))}
          {!recent?.items.length && (
            <div style={styles.empty}>No verifications yet. Integrate the SDK to start.</div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────

function StatCard({ label, value, sub, loading, accent }: {
  label: string; value: string | number; sub: string; loading: boolean; accent: string
}) {
  return (
    <div className="card" style={styles.statCard}>
      <div style={{ ...styles.statAccent, background: accent }} />
      <div style={styles.statLabel}>{label}</div>
      {loading
        ? <div className="skeleton" style={{ height: 36, width: '60%', marginBottom: 6 }} />
        : <div style={{ ...styles.statValue, color: accent }}>{value}</div>
      }
      <div style={styles.statSub}>{sub}</div>
    </div>
  )
}

function UsageCard({ used, limit }: { used: number; limit: number }) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0
  const color = pct > 90 ? 'var(--score-blocked)' : pct > 70 ? 'var(--score-suspicious)' : 'var(--teal-400)'
  return (
    <div className="card" style={styles.statCard}>
      <div style={{ ...styles.statAccent, background: color }} />
      <div style={styles.statLabel}>Monthly usage</div>
      <div style={{ ...styles.statValue, color }}>{used.toLocaleString()} <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>/ {limit.toLocaleString()}</span></div>
      <div style={styles.usageBar}>
        <div style={{ ...styles.usageFill, width: `${pct}%`, background: color }} />
      </div>
      <div style={styles.statSub}>{pct.toFixed(1)}% of monthly limit used</div>
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return new Date(iso).toLocaleDateString()
}

// ── Styles ────────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 32 },
  title: { fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 4 },
  subtitle: { color: 'var(--text-muted)', fontSize: 13, fontFamily: 'var(--font-mono)' },
  planBadge: {
    padding: '4px 12px', borderRadius: 100,
    background: 'rgba(16,184,138,0.1)', border: '1px solid var(--border-default)',
    fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--teal-400)', letterSpacing: '0.08em',
  },
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 32 },
  statCard: { padding: '20px 24px', position: 'relative', overflow: 'hidden' },
  statAccent: { position: 'absolute', top: 0, left: 0, right: 0, height: 2, opacity: 0.7 },
  statLabel: { fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 },
  statValue: { fontFamily: 'var(--font-display)', fontSize: 32, fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1, marginBottom: 6 },
  statSub: { fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-body)' },
  usageBar: { height: 4, background: 'var(--bg-overlay)', borderRadius: 2, marginBottom: 6, overflow: 'hidden' },
  usageFill: { height: '100%', borderRadius: 2, transition: 'width 0.6s ease' },
  section: { marginBottom: 32 },
  sectionHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: 700, letterSpacing: '-0.02em' },
  seeAll: { fontSize: 12, color: 'var(--teal-400)', textDecoration: 'none', fontFamily: 'var(--font-mono)' },
  table: { background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)', overflow: 'hidden' },
  tableHead: {
    display: 'grid', gridTemplateColumns: '2fr 1fr 1.5fr 1fr 1fr',
    padding: '10px 20px', borderBottom: '1px solid var(--border-subtle)',
    fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
    textTransform: 'uppercase', letterSpacing: '0.06em',
  },
  tableRow: {
    display: 'grid', gridTemplateColumns: '2fr 1fr 1.5fr 1fr 1fr',
    padding: '12px 20px', borderBottom: '1px solid var(--border-subtle)',
    alignItems: 'center', cursor: 'pointer', textDecoration: 'none', color: 'inherit',
    transition: 'background 0.12s', fontSize: 13,
  },
  mono: { fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' },
  muted: { color: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-mono)' },
  actionBadge: {
    fontSize: 11, padding: '2px 8px', borderRadius: 100,
    background: 'var(--bg-overlay)', color: 'var(--text-secondary)',
    fontFamily: 'var(--font-mono)', textTransform: 'capitalize',
  },
  empty: { padding: '32px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, fontFamily: 'var(--font-mono)' },
}
