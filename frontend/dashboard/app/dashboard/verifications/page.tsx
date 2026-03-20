'use client'

import { useState, useCallback } from 'react'
import { useVerifications } from '../../../hooks/index'
import { ScoreBadge, VerdictBadge } from '../../../components/ScoreGauge'
import type { Verdict, ActionType } from '../../../lib/types'

const VERDICTS: { value: string; label: string }[] = [
  { value: '', label: 'All verdicts' },
  { value: 'human', label: 'Verified Human' },
  { value: 'likely_human', label: 'Likely Human' },
  { value: 'uncertain', label: 'Uncertain' },
  { value: 'suspicious', label: 'Suspicious' },
  { value: 'blocked', label: 'Blocked' },
]

const ACTIONS: { value: string; label: string }[] = [
  { value: '', label: 'All actions' },
  { value: 'job_application', label: 'Job Application' },
  { value: 'review_submission', label: 'Review Submission' },
  { value: 'account_creation', label: 'Account Creation' },
  { value: 'financial_transaction', label: 'Financial Transaction' },
  { value: 'exam_submission', label: 'Exam Submission' },
]

export default function VerificationsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [verdict, setVerdict] = useState('')
  const [actionType, setActionType] = useState('')
  const [minScore, setMinScore] = useState('')
  const [maxScore, setMaxScore] = useState('')

  const { data, isLoading, isFetching } = useVerifications({
    page,
    page_size: 20,
    search: search || undefined,
    verdict: verdict || undefined,
    action_type: actionType || undefined,
    min_score: minScore ? Number(minScore) : undefined,
    max_score: maxScore ? Number(maxScore) : undefined,
  })

  const handleSearch = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value)
    setPage(1)
  }, [])

  return (
    <div className="animate-fade-up">
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Verifications</h1>
          <p style={styles.subtitle}>
            {data?.total.toLocaleString() ?? '—'} total records
          </p>
        </div>
      </div>

      {/* Filters */}
      <div style={styles.filters}>
        <input
          type="text"
          placeholder="Search by user ID or session ID…"
          value={search}
          onChange={handleSearch}
          style={styles.searchInput}
        />
        <select value={verdict} onChange={e => { setVerdict(e.target.value); setPage(1) }} style={styles.select}>
          {VERDICTS.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
        </select>
        <select value={actionType} onChange={e => { setActionType(e.target.value); setPage(1) }} style={styles.select}>
          {ACTIONS.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
        </select>
        <div style={styles.scoreRange}>
          <input
            type="number" placeholder="Min score" min={0} max={100}
            value={minScore} onChange={e => { setMinScore(e.target.value); setPage(1) }}
            style={{ ...styles.scoreInput }}
          />
          <span style={styles.scoreSep}>–</span>
          <input
            type="number" placeholder="Max score" min={0} max={100}
            value={maxScore} onChange={e => { setMaxScore(e.target.value); setPage(1) }}
            style={{ ...styles.scoreInput }}
          />
        </div>
      </div>

      {/* Table */}
      <div style={{ ...styles.table, opacity: isFetching ? 0.7 : 1, transition: 'opacity 0.2s' }}>
        <div style={styles.tableHead}>
          <span>User ID</span>
          <span>Score</span>
          <span>Verdict</span>
          <span>Action</span>
          <span>Flags</span>
          <span>Time (ms)</span>
          <span>Date</span>
        </div>

        {isLoading && Array.from({ length: 8 }).map((_, i) => (
          <div key={i} style={styles.tableRow}>
            {Array.from({ length: 7 }).map((_, j) => (
              <div key={j} className="skeleton" style={{ height: 16, width: '70%' }} />
            ))}
          </div>
        ))}

        {!isLoading && data?.items.map((v, i) => (
          <a
            key={v.id}
            href={`/dashboard/verifications/${v.id}`}
            style={{ ...styles.tableRow, animationDelay: `${i * 30}ms` }}
            className="animate-fade-up"
          >
            <span style={styles.mono}>{v.platform_user_id.slice(0, 14)}…</span>
            <ScoreBadge score={v.score} verdict={v.verdict} />
            <VerdictBadge verdict={v.verdict} />
            <span style={styles.actionChip}>{v.action_type.replace(/_/g, ' ')}</span>
            <span style={v.flags_count > 0 ? styles.flagCount : styles.muted}>
              {v.flags_count > 0 ? `⚑ ${v.flags_count}` : '—'}
            </span>
            <span style={styles.mono}>{v.processing_time_ms}ms</span>
            <span style={styles.muted}>{new Date(v.created_at).toLocaleString()}</span>
          </a>
        ))}

        {!isLoading && !data?.items.length && (
          <div style={styles.empty}>No verifications match your filters.</div>
        )}
      </div>

      {/* Pagination */}
      {data && data.total > 20 && (
        <div style={styles.pagination}>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            style={styles.pageBtn}
          >
            ← Prev
          </button>
          <span style={styles.pageInfo}>
            Page {page} of {Math.ceil(data.total / 20)}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={!data.has_next}
            style={styles.pageBtn}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 },
  title: { fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 4 },
  subtitle: { color: 'var(--text-muted)', fontSize: 13, fontFamily: 'var(--font-mono)' },
  filters: { display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20, alignItems: 'center' },
  searchInput: {
    flex: '1 1 280px', padding: '9px 14px', background: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)',
    color: 'var(--text-primary)', fontSize: 13, fontFamily: 'var(--font-body)', outline: 'none',
  },
  select: {
    padding: '9px 12px', background: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)',
    color: 'var(--text-secondary)', fontSize: 12, fontFamily: 'var(--font-mono)', outline: 'none', cursor: 'pointer',
  },
  scoreRange: { display: 'flex', alignItems: 'center', gap: 6 },
  scoreInput: {
    width: 90, padding: '9px 10px', background: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)',
    color: 'var(--text-secondary)', fontSize: 12, fontFamily: 'var(--font-mono)', outline: 'none',
  },
  scoreSep: { color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 12 },
  table: { background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)', overflow: 'hidden', marginBottom: 16 },
  tableHead: {
    display: 'grid', gridTemplateColumns: '2fr 1fr 1.5fr 1.2fr 0.7fr 0.8fr 1.5fr',
    padding: '10px 20px', borderBottom: '1px solid var(--border-subtle)',
    fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
    textTransform: 'uppercase', letterSpacing: '0.06em',
  },
  tableRow: {
    display: 'grid', gridTemplateColumns: '2fr 1fr 1.5fr 1.2fr 0.7fr 0.8fr 1.5fr',
    padding: '12px 20px', borderBottom: '1px solid var(--border-subtle)',
    alignItems: 'center', cursor: 'pointer', textDecoration: 'none', color: 'inherit',
    transition: 'background 0.12s', fontSize: 12,
  },
  mono: { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)' },
  muted: { color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)' },
  actionChip: {
    fontSize: 10, padding: '2px 8px', borderRadius: 100, background: 'var(--bg-overlay)',
    color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', textTransform: 'capitalize',
  },
  flagCount: { color: 'var(--score-suspicious)', fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600 },
  empty: { padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, fontFamily: 'var(--font-mono)' },
  pagination: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16 },
  pageBtn: {
    padding: '8px 16px', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
    borderRadius: 'var(--r-sm)', color: 'var(--text-secondary)', fontSize: 13, fontFamily: 'var(--font-mono)',
    cursor: 'pointer', transition: 'all 0.15s',
  },
  pageInfo: { fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)' },
}
