'use client'

import { useState } from 'react'
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '../../../hooks/index'
import type { ApiKey, CreateApiKeyResponse } from '../../../lib/types'

export default function ApiKeysPage() {
  const { data: keys, isLoading } = useApiKeys()
  const createMutation = useCreateApiKey()
  const revokeMutation = useRevokeApiKey()

  const [newKeyName, setNewKeyName] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [justCreated, setJustCreated] = useState<CreateApiKeyResponse | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [revokeConfirm, setRevokeConfirm] = useState<string | null>(null)
  const [error, setError] = useState('')

  async function handleCreate() {
    if (!newKeyName.trim()) return
    setError('')
    try {
      const res = await createMutation.mutateAsync(newKeyName.trim())
      setJustCreated(res)
      setNewKeyName('')
      setShowCreate(false)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create key')
    }
  }

  async function handleRevoke(id: string) {
    try {
      await revokeMutation.mutateAsync(id)
      setRevokeConfirm(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to revoke key')
    }
  }

  function copyToClipboard(text: string, id: string) {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  return (
    <div className="animate-fade-up">
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>API Keys</h1>
          <p style={styles.subtitle}>Manage keys for authenticating API requests</p>
        </div>
        <button onClick={() => setShowCreate(true)} style={styles.createBtn}>
          + New key
        </button>
      </div>

      {/* One-time key reveal */}
      {justCreated && (
        <div style={styles.newKeyBanner}>
          <div style={styles.newKeyHeader}>
            <span style={styles.newKeyTitle}>⚠ Copy your key now — it will never be shown again</span>
            <button onClick={() => setJustCreated(null)} style={styles.dismissBtn}>Dismiss</button>
          </div>
          <div style={styles.keyReveal}>
            <code style={styles.keyCode}>{justCreated.key}</code>
            <button onClick={() => copyToClipboard(justCreated.key, 'new')} style={styles.copyBtn}>
              {copiedId === 'new' ? '✓ Copied' : 'Copy'}
            </button>
          </div>
          <p style={styles.newKeyNote}>
            Store this key securely. Use it as the <code style={styles.inlineCode}>Authorization: Bearer {'<key>'}</code> header in API requests.
          </p>
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <div style={styles.modal} onClick={() => setShowCreate(false)}>
          <div style={styles.modalBox} onClick={e => e.stopPropagation()}>
            <h2 style={styles.modalTitle}>Create new API key</h2>
            <p style={styles.modalSub}>Give it a descriptive name (e.g. "Production", "Staging", "ATS Integration")</p>
            <input
              type="text"
              placeholder="Key name…"
              value={newKeyName}
              onChange={e => setNewKeyName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              style={styles.nameInput}
              autoFocus
            />
            {error && <p style={styles.error}>{error}</p>}
            <div style={styles.modalActions}>
              <button onClick={() => setShowCreate(false)} style={styles.cancelBtn}>Cancel</button>
              <button
                onClick={handleCreate}
                disabled={!newKeyName.trim() || createMutation.isPending}
                style={styles.confirmBtn}
              >
                {createMutation.isPending ? 'Creating…' : 'Create key'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Keys list */}
      <div style={styles.keysList}>
        {isLoading && Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="card" style={styles.keyCard}>
            <div className="skeleton" style={{ height: 18, width: '30%', marginBottom: 10 }} />
            <div className="skeleton" style={{ height: 14, width: '60%' }} />
          </div>
        ))}

        {!isLoading && keys?.map((key) => (
          <div key={key.id} className="card" style={styles.keyCard}>
            <div style={styles.keyTop}>
              <div>
                <div style={styles.keyName}>{key.name}</div>
                <div style={styles.keyPreview} className="mono">{key.key_preview}</div>
              </div>
              <div style={styles.keyActions}>
                <button onClick={() => copyToClipboard(key.key_preview, key.id)} style={styles.copyIconBtn}>
                  {copiedId === key.id ? '✓' : '⎘'}
                </button>
                {key.is_active ? (
                  revokeConfirm === key.id
                    ? <span style={styles.revokeConfirmRow}>
                        Sure?{' '}
                        <button onClick={() => handleRevoke(key.id)} style={styles.revokeYes}>Revoke</button>
                        {' · '}
                        <button onClick={() => setRevokeConfirm(null)} style={styles.revokeNo}>Cancel</button>
                      </span>
                    : <button onClick={() => setRevokeConfirm(key.id)} style={styles.revokeBtn}>Revoke</button>
                ) : (
                  <span style={styles.revokedBadge}>Revoked</span>
                )}
              </div>
            </div>
            <div style={styles.keyMeta}>
              <span>Created {new Date(key.created_at).toLocaleDateString()}</span>
              <span>·</span>
              <span>{key.usage_count.toLocaleString()} requests</span>
              {key.last_used_at && (
                <>
                  <span>·</span>
                  <span>Last used {new Date(key.last_used_at).toLocaleDateString()}</span>
                </>
              )}
            </div>
          </div>
        ))}

        {!isLoading && !keys?.length && (
          <div style={styles.empty}>
            No API keys yet. Create one to start integrating HumanEye.
          </div>
        )}
      </div>

      {/* Docs callout */}
      <div style={styles.docsCard}>
        <div style={styles.docsTitle}>Quick start</div>
        <pre style={styles.codeBlock}>{`// Install
npm install @humaneye/sdk

// Initialize
import HumanEye from '@humaneye/sdk'
const eye = new HumanEye({ apiKey: 'your_key_here' })

// Verify on form submit
const result = await eye.verify({ text_content: resumeText })
console.log(result.score, result.verdict)`}</pre>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 },
  title: { fontSize: 28, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 4 },
  subtitle: { color: 'var(--text-muted)', fontSize: 13, fontFamily: 'var(--font-mono)' },
  createBtn: {
    padding: '9px 18px', background: 'var(--teal-500)', color: '#000',
    border: 'none', borderRadius: 'var(--r-sm)', fontFamily: 'var(--font-display)',
    fontWeight: 700, fontSize: 14, cursor: 'pointer',
  },
  newKeyBanner: {
    background: 'rgba(250,204,21,0.06)', border: '1px solid rgba(250,204,21,0.25)',
    borderRadius: 'var(--r-lg)', padding: '20px 24px', marginBottom: 24,
  },
  newKeyHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  newKeyTitle: { fontSize: 13, fontWeight: 600, color: 'var(--score-uncertain)' },
  dismissBtn: { background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 12, cursor: 'pointer', fontFamily: 'var(--font-mono)' },
  keyReveal: { display: 'flex', gap: 10, alignItems: 'center', marginBottom: 12 },
  keyCode: {
    flex: 1, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--teal-200)',
    background: 'var(--bg-raised)', padding: '10px 14px', borderRadius: 'var(--r-sm)',
    wordBreak: 'break-all',
  },
  copyBtn: {
    padding: '8px 16px', background: 'var(--teal-500)', color: '#000',
    border: 'none', borderRadius: 'var(--r-sm)', fontSize: 12, fontFamily: 'var(--font-mono)', cursor: 'pointer', whiteSpace: 'nowrap',
  },
  newKeyNote: { fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' },
  inlineCode: { fontFamily: 'var(--font-mono)', background: 'var(--bg-overlay)', padding: '1px 5px', borderRadius: 3 },
  modal: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
  },
  modalBox: { background: 'var(--bg-surface)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-xl)', padding: '32px', width: '400px', boxShadow: 'var(--shadow-pop)' },
  modalTitle: { fontSize: 20, fontWeight: 800, marginBottom: 8, letterSpacing: '-0.02em' },
  modalSub: { fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 },
  nameInput: {
    width: '100%', padding: '10px 14px', background: 'var(--bg-raised)',
    border: '1px solid var(--border-default)', borderRadius: 'var(--r-sm)',
    color: 'var(--text-primary)', fontSize: 14, fontFamily: 'var(--font-body)', outline: 'none', marginBottom: 16,
  },
  error: { color: 'var(--score-blocked)', fontSize: 12, fontFamily: 'var(--font-mono)', marginBottom: 12 },
  modalActions: { display: 'flex', gap: 10, justifyContent: 'flex-end' },
  cancelBtn: { padding: '9px 16px', background: 'none', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', color: 'var(--text-secondary)', fontSize: 13, cursor: 'pointer', fontFamily: 'var(--font-body)' },
  confirmBtn: { padding: '9px 18px', background: 'var(--teal-500)', color: '#000', border: 'none', borderRadius: 'var(--r-sm)', fontSize: 13, fontFamily: 'var(--font-display)', fontWeight: 700, cursor: 'pointer' },
  keysList: { display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 },
  keyCard: { padding: '18px 22px' },
  keyTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 },
  keyName: { fontSize: 15, fontWeight: 600, marginBottom: 4, letterSpacing: '-0.01em' },
  keyPreview: { fontSize: 12, color: 'var(--text-muted)' },
  keyActions: { display: 'flex', alignItems: 'center', gap: 10 },
  copyIconBtn: { background: 'none', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', color: 'var(--text-muted)', fontSize: 14, padding: '4px 10px', cursor: 'pointer' },
  revokeBtn: { background: 'none', border: 'none', color: 'var(--score-blocked)', fontSize: 12, fontFamily: 'var(--font-mono)', cursor: 'pointer' },
  revokeConfirmRow: { fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 },
  revokeYes: { background: 'none', border: 'none', color: 'var(--score-blocked)', fontSize: 12, fontFamily: 'var(--font-mono)', cursor: 'pointer', fontWeight: 600 },
  revokeNo: { background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-mono)', cursor: 'pointer' },
  revokedBadge: { fontSize: 10, padding: '2px 8px', borderRadius: 100, background: 'var(--bg-overlay)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' },
  keyMeta: { display: 'flex', gap: 8, fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' },
  empty: { padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 13 },
  docsCard: { background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)', padding: '24px' },
  docsTitle: { fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--teal-400)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 14 },
  codeBlock: { fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.7, overflow: 'auto' },
}
