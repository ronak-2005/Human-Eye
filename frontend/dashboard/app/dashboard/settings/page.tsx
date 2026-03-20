'use client'

import { useState, useEffect } from 'react'
import { useWebhookConfig, useSaveWebhook, useMe } from '../../../hooks/index'

export default function SettingsPage() {
  const { data: me } = useMe()
  const { data: webhook } = useWebhookConfig()
  const saveMutation = useSaveWebhook()

  const [webhookUrl, setWebhookUrl] = useState('')
  const [webhookActive, setWebhookActive] = useState(true)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (webhook) {
      setWebhookUrl(webhook.url ?? '')
      setWebhookActive(webhook.is_active ?? true)
    }
  }, [webhook])

  async function handleSaveWebhook() {
    setError('')
    try {
      await saveMutation.mutateAsync({ url: webhookUrl, is_active: webhookActive })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
    }
  }

  return (
    <div className="animate-fade-up">
      <h1 style={styles.title}>Settings</h1>

      {/* Account */}
      <div className="card" style={styles.section}>
        <h2 style={styles.sectionTitle}>Account</h2>
        <div style={styles.infoGrid}>
          <InfoRow label="Company" value={me?.company_name ?? '—'} />
          <InfoRow label="Email" value={me?.email ?? '—'} />
          <InfoRow label="Plan" value={me?.plan?.toUpperCase() ?? '—'} accent />
          <InfoRow label="Customer ID" value={me?.id ?? '—'} mono />
        </div>
      </div>

      {/* Webhook */}
      <div className="card" style={styles.section}>
        <h2 style={styles.sectionTitle}>Webhook</h2>
        <p style={styles.sectionDesc}>
          HumanEye will POST verification results to your endpoint as they complete.
          Payloads are signed with your secret using HMAC-SHA256.
        </p>
        <div style={styles.field}>
          <label style={styles.label}>Webhook URL</label>
          <input
            type="url"
            placeholder="https://your-app.com/webhooks/humaneye"
            value={webhookUrl}
            onChange={e => setWebhookUrl(e.target.value)}
            style={styles.input}
          />
        </div>
        <div style={styles.toggleRow}>
          <div>
            <div style={styles.toggleLabel}>Active</div>
            <div style={styles.toggleDesc}>Pause delivery without deleting your endpoint</div>
          </div>
          <button
            onClick={() => setWebhookActive(a => !a)}
            style={{ ...styles.toggle, background: webhookActive ? 'var(--teal-500)' : 'var(--bg-overlay)' }}
          >
            <span style={{ ...styles.toggleThumb, transform: webhookActive ? 'translateX(20px)' : 'translateX(2px)' }} />
          </button>
        </div>
        {error && <p style={styles.error}>{error}</p>}
        <button onClick={handleSaveWebhook} disabled={saveMutation.isPending} style={styles.saveBtn}>
          {saveMutation.isPending ? 'Saving…' : saved ? '✓ Saved' : 'Save webhook'}
        </button>
      </div>

      {/* Data retention info */}
      <div className="card" style={styles.section}>
        <h2 style={styles.sectionTitle}>Data & Privacy</h2>
        <div style={styles.retentionGrid}>
          <RetentionItem label="Behavioral signals" value="90 days, then aggregated" />
          <RetentionItem label="Verification results" value="2 years" />
          <RetentionItem label="API key hashes" value="Until revoked" />
          <RetentionItem label="Raw video/audio" value="Never stored (processed in memory)" accent />
        </div>
        <p style={styles.complianceNote}>
          HumanEye is SOC 2 Type II certified (Month 18 target). All data encrypted at rest (AES-256) and in transit (TLS 1.3).
          GDPR and CCPA compliant. Deletion requests processed within 30 days.
        </p>
      </div>
    </div>
  )
}

function InfoRow({ label, value, mono, accent }: { label: string; value: string; mono?: boolean; accent?: boolean }) {
  return (
    <div style={styles.infoRow}>
      <span style={styles.infoLabel}>{label}</span>
      <span style={{
        ...styles.infoValue,
        ...(mono ? { fontFamily: 'var(--font-mono)', fontSize: 12 } : {}),
        ...(accent ? { color: 'var(--teal-400)' } : {}),
      }}>{value}</span>
    </div>
  )
}

function RetentionItem({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={styles.retentionItem}>
      <div style={styles.retentionLabel}>{label}</div>
      <div style={{ ...styles.retentionValue, ...(accent ? { color: 'var(--teal-400)' } : {}) }}>{value}</div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  title: { fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 28 },
  section: { padding: '24px 28px', marginBottom: 16 },
  sectionTitle: { fontSize: 15, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 14 },
  sectionDesc: { fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 20, fontFamily: 'var(--font-body)' },
  infoGrid: { display: 'flex', flexDirection: 'column', gap: 0 },
  infoRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--border-subtle)' },
  infoLabel: { fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' },
  infoValue: { fontSize: 14, color: 'var(--text-secondary)', fontWeight: 500 },
  field: { marginBottom: 16 },
  label: { display: 'block', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 },
  input: {
    width: '100%', padding: '10px 14px', background: 'var(--bg-raised)',
    border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)',
    color: 'var(--text-primary)', fontSize: 14, fontFamily: 'var(--font-body)', outline: 'none',
  },
  toggleRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
  toggleLabel: { fontSize: 14, fontWeight: 500, marginBottom: 2 },
  toggleDesc: { fontSize: 12, color: 'var(--text-muted)' },
  toggle: { width: 44, height: 24, borderRadius: 12, border: 'none', cursor: 'pointer', position: 'relative', transition: 'background 0.2s', flexShrink: 0 },
  toggleThumb: { position: 'absolute', top: 2, width: 20, height: 20, background: '#fff', borderRadius: '50%', transition: 'transform 0.2s', display: 'block' },
  error: { color: 'var(--score-blocked)', fontSize: 12, fontFamily: 'var(--font-mono)', marginBottom: 12 },
  saveBtn: { padding: '9px 20px', background: 'var(--teal-500)', color: '#000', border: 'none', borderRadius: 'var(--r-sm)', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 13, cursor: 'pointer' },
  retentionGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 },
  retentionItem: { background: 'var(--bg-raised)', padding: '12px 16px', borderRadius: 'var(--r-sm)' },
  retentionLabel: { fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 },
  retentionValue: { fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500 },
  complianceNote: { fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6, borderTop: '1px solid var(--border-subtle)', paddingTop: 14 },
}
