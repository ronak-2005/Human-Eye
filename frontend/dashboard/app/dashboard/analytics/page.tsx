'use client'

import { useState } from 'react'
import { useAnalytics } from '../../../hooks/index'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend
} from 'recharts'

const VERDICT_COLORS: Record<string, string> = {
  human: '#10B88A',
  likely_human: '#4ADE80',
  uncertain: '#FACC15',
  suspicious: '#FB923C',
  blocked: '#F43F5E',
}

const PERIODS = [
  { value: '7d', label: '7 days' },
  { value: '30d', label: '30 days' },
  { value: '90d', label: '90 days' },
] as const

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<'7d' | '30d' | '90d'>('30d')
  const { data, isLoading } = useAnalytics(period)

  return (
    <div className="animate-fade-up">
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Analytics</h1>
          <p style={styles.subtitle}>Detection trends and score distributions</p>
        </div>
        <div style={styles.periodTabs}>
          {PERIODS.map(p => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              style={{ ...styles.periodBtn, ...(period === p.value ? styles.periodBtnActive : {}) }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Volume chart */}
      <div className="card" style={styles.chartCard}>
        <h2 style={styles.chartTitle}>Verification Volume</h2>
        <div style={styles.chartWrap}>
          {isLoading
            ? <div className="skeleton" style={{ height: 220 }} />
            : (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={data?.daily_volumes ?? []} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
                  <CartesianGrid stroke="rgba(62,207,163,0.06)" strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontFamily: 'DM Mono', fontSize: 10, fill: '#4E6478' }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontFamily: 'DM Mono', fontSize: 10, fill: '#4E6478' }} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#111820', border: '1px solid #1E2A35', borderRadius: 8, fontFamily: 'DM Mono', fontSize: 11 }}
                    labelStyle={{ color: '#8BA4B8' }}
                    itemStyle={{ color: '#10B88A' }}
                  />
                  <Line type="monotone" dataKey="count" stroke="#10B88A" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: '#10B88A' }} />
                </LineChart>
              </ResponsiveContainer>
            )
          }
        </div>
      </div>

      <div style={styles.twoCol}>
        {/* Score distribution */}
        <div className="card" style={styles.chartCard}>
          <h2 style={styles.chartTitle}>Score Distribution</h2>
          <div style={styles.chartWrap}>
            {isLoading
              ? <div className="skeleton" style={{ height: 200 }} />
              : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={data?.score_distribution ?? []} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
                    <CartesianGrid stroke="rgba(62,207,163,0.06)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="range" tick={{ fontFamily: 'DM Mono', fontSize: 10, fill: '#4E6478' }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontFamily: 'DM Mono', fontSize: 10, fill: '#4E6478' }} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{ background: '#111820', border: '1px solid #1E2A35', borderRadius: 8, fontFamily: 'DM Mono', fontSize: 11 }}
                      labelStyle={{ color: '#8BA4B8' }}
                    />
                    <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                      {(data?.score_distribution ?? []).map((entry, i) => {
                        const score = parseInt(entry.range)
                        const color = score >= 80 ? '#10B88A' : score >= 65 ? '#4ADE80' : score >= 50 ? '#FACC15' : score >= 25 ? '#FB923C' : '#F43F5E'
                        return <Cell key={i} fill={color} fillOpacity={0.8} />
                      })}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )
            }
          </div>
        </div>

        {/* Verdict breakdown pie */}
        <div className="card" style={styles.chartCard}>
          <h2 style={styles.chartTitle}>Verdict Breakdown</h2>
          <div style={styles.chartWrap}>
            {isLoading
              ? <div className="skeleton" style={{ height: 200 }} />
              : (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={Object.entries(data?.verdict_breakdown ?? {}).map(([k, v]) => ({ name: k.replace(/_/g, ' '), value: v }))}
                      cx="50%" cy="50%" innerRadius={55} outerRadius={80}
                      paddingAngle={2} dataKey="value"
                    >
                      {Object.keys(data?.verdict_breakdown ?? {}).map((k, i) => (
                        <Cell key={i} fill={VERDICT_COLORS[k] ?? '#4E6478'} />
                      ))}
                    </Pie>
                    <Legend
                      formatter={(value) => (
                        <span style={{ fontFamily: 'DM Mono', fontSize: 10, color: '#8BA4B8', textTransform: 'capitalize' }}>{value}</span>
                      )}
                    />
                    <Tooltip
                      contentStyle={{ background: '#111820', border: '1px solid #1E2A35', borderRadius: 8, fontFamily: 'DM Mono', fontSize: 11 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )
            }
          </div>
        </div>
      </div>

      {/* Flag type breakdown */}
      <div className="card" style={styles.chartCard}>
        <h2 style={styles.chartTitle}>Top Flags Raised</h2>
        <div style={styles.flagTable}>
          {isLoading && Array.from({ length: 5 }).map((_, i) => (
            <div key={i} style={styles.flagRow}>
              <div className="skeleton" style={{ height: 14, width: '25%' }} />
              <div className="skeleton" style={{ height: 8, flex: 1, maxWidth: 300 }} />
              <div className="skeleton" style={{ height: 14, width: '8%' }} />
            </div>
          ))}
          {!isLoading && (data?.flag_breakdown ?? []).map((f) => (
            <div key={f.flag_code} style={styles.flagRow}>
              <span style={styles.flagCode}>{f.flag_code}</span>
              <div style={styles.flagBarWrap}>
                <div style={{ ...styles.flagBar, width: `${f.percentage}%` }} />
              </div>
              <span style={styles.flagCount}>{f.count.toLocaleString()}</span>
              <span style={styles.flagPct}>{f.percentage.toFixed(1)}%</span>
            </div>
          ))}
          {!isLoading && !data?.flag_breakdown?.length && (
            <p style={styles.empty}>No flags raised in this period.</p>
          )}
        </div>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 },
  title: { fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 4 },
  subtitle: { color: 'var(--text-muted)', fontSize: 13, fontFamily: 'var(--font-mono)' },
  periodTabs: { display: 'flex', gap: 4, background: 'var(--bg-surface)', padding: 4, borderRadius: 'var(--r-sm)', border: '1px solid var(--border-subtle)' },
  periodBtn: { padding: '6px 14px', borderRadius: 'var(--r-sm)', background: 'none', border: 'none', fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', cursor: 'pointer', transition: 'all 0.15s' },
  periodBtnActive: { background: 'var(--bg-overlay)', color: 'var(--teal-400)' },
  chartCard: { padding: '20px 24px', marginBottom: 16 },
  chartTitle: { fontSize: 13, fontWeight: 700, letterSpacing: '-0.01em', marginBottom: 16 },
  chartWrap: { position: 'relative' },
  twoCol: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 },
  flagTable: { display: 'flex', flexDirection: 'column', gap: 10 },
  flagRow: { display: 'flex', alignItems: 'center', gap: 12 },
  flagCode: { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--teal-300)', width: '22%', flexShrink: 0 },
  flagBarWrap: { flex: 1, height: 6, background: 'var(--bg-overlay)', borderRadius: 3, overflow: 'hidden' },
  flagBar: { height: '100%', background: 'var(--score-suspicious)', borderRadius: 3, transition: 'width 0.6s ease' },
  flagCount: { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-secondary)', width: '10%', textAlign: 'right' },
  flagPct: { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', width: '8%', textAlign: 'right' },
  empty: { color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 13 },
}
