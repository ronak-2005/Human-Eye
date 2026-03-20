'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { authApi, api } from '../lib/api'

export default function AuthPage() {
  const router = useRouter()
  const [mode, setMode] = useState<'login' | 'signup'>('login')

  // Login fields
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  // Signup fields
  const [companyName, setCompanyName] = useState('')
  const [signupEmail, setSignupEmail] = useState('')
  const [signupPassword, setSignupPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [signupSuccess, setSignupSuccess] = useState(false)

  function switchMode(next: 'login' | 'signup') {
    setError('')
    setMode(next)
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.login({ email, password })
      router.push('/dashboard')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid email or password')
    } finally {
      setLoading(false)
    }
  }

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (signupPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    if (signupPassword.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setLoading(true)
    try {
      await api.post('/api/v1/auth/register', {
        email: signupEmail,
        password: signupPassword,
        company_name: companyName,
      })
      setSignupSuccess(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Signup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.bgGlow} />

      <div style={styles.container} className="animate-fade-up">

        {/* Logo */}
        <div style={styles.logoWrap}>
          <svg width="36" height="36" viewBox="0 0 40 40" fill="none">
            <circle cx="20" cy="20" r="19" stroke="var(--teal-500)" strokeWidth="1.5" />
            <circle cx="20" cy="20" r="8" fill="var(--teal-500)" opacity="0.15" />
            <circle cx="20" cy="20" r="4" fill="var(--teal-400)" />
            <path d="M20 6C10 6 4 20 4 20C4 20 10 34 20 34C30 34 36 20 36 20C36 20 30 6 20 6Z"
              stroke="var(--teal-500)" strokeWidth="1.2" fill="none" strokeLinejoin="round" />
          </svg>
          <span style={styles.logoText}>HumanEye</span>
        </div>

        {/* Tab switcher */}
        <div style={styles.tabs}>
          <button
            onClick={() => switchMode('login')}
            style={{ ...styles.tab, ...(mode === 'login' ? styles.tabActive : {}) }}
          >
            Sign in
          </button>
          <button
            onClick={() => switchMode('signup')}
            style={{ ...styles.tab, ...(mode === 'signup' ? styles.tabActive : {}) }}
          >
            Create account
          </button>
        </div>

        {/* ── LOGIN FORM ── */}
        {mode === 'login' && (
          <>
            <h1 style={styles.heading}>Welcome back</h1>
            <p style={styles.subheading}>Sign in to your verification dashboard</p>

            <form onSubmit={handleLogin} style={styles.form}>
              <div style={styles.field}>
                <label style={styles.label}>Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  style={styles.input}
                  autoComplete="email"
                />
              </div>
              <div style={styles.field}>
                <label style={styles.label}>Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  style={styles.input}
                  autoComplete="current-password"
                />
              </div>

              {error && <p style={styles.error}>{error}</p>}

              <button type="submit" disabled={loading} style={styles.btn}>
                {loading ? 'Signing in…' : 'Sign in'}
              </button>
            </form>

            <p style={styles.switchText}>
              No account?{' '}
              <button onClick={() => switchMode('signup')} style={styles.switchBtn}>
                Create one →
              </button>
            </p>
          </>
        )}

        {/* ── SIGNUP FORM ── */}
        {mode === 'signup' && !signupSuccess && (
          <>
            <h1 style={styles.heading}>Get started</h1>
            <p style={styles.subheading}>Create your HumanEye workspace</p>

            <form onSubmit={handleSignup} style={styles.form}>
              <div style={styles.field}>
                <label style={styles.label}>Company name</label>
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="Acme Corp"
                  required
                  style={styles.input}
                  autoComplete="organization"
                />
              </div>
              <div style={styles.field}>
                <label style={styles.label}>Work email</label>
                <input
                  type="email"
                  value={signupEmail}
                  onChange={(e) => setSignupEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  style={styles.input}
                  autoComplete="email"
                />
              </div>
              <div style={styles.twoCol}>
                <div style={styles.field}>
                  <label style={styles.label}>Password</label>
                  <input
                    type="password"
                    value={signupPassword}
                    onChange={(e) => setSignupPassword(e.target.value)}
                    placeholder="Min 8 characters"
                    required
                    style={styles.input}
                    autoComplete="new-password"
                  />
                </div>
                <div style={styles.field}>
                  <label style={styles.label}>Confirm</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repeat password"
                    required
                    style={styles.input}
                    autoComplete="new-password"
                  />
                </div>
              </div>

              {error && <p style={styles.error}>{error}</p>}

              <button type="submit" disabled={loading} style={styles.btn}>
                {loading ? 'Creating account…' : 'Create account'}
              </button>
            </form>

            <p style={styles.terms}>
              By signing up you agree to our{' '}
              <a href="#" style={styles.link}>Terms of Service</a>
              {' '}and{' '}
              <a href="#" style={styles.link}>Privacy Policy</a>.
            </p>

            <p style={styles.switchText}>
              Already have an account?{' '}
              <button onClick={() => switchMode('login')} style={styles.switchBtn}>
                Sign in →
              </button>
            </p>
          </>
        )}

        {/* ── SIGNUP SUCCESS ── */}
        {mode === 'signup' && signupSuccess && (
          <div style={styles.successBox}>
            <div style={styles.successIcon}>✓</div>
            <h2 style={styles.successTitle}>Account created!</h2>
            <p style={styles.successSub}>
              Your workspace is ready. Sign in to get started.
            </p>
            <button
              onClick={() => { setMode('login'); setSignupSuccess(false) }}
              style={styles.btn}
            >
              Go to sign in
            </button>
          </div>
        )}

      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    overflow: 'hidden',
    padding: '24px',
  },
  bgGlow: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -60%)',
    width: '600px',
    height: '600px',
    background: 'radial-gradient(circle, rgba(16,184,138,0.08) 0%, transparent 70%)',
    pointerEvents: 'none',
  },
  container: {
    width: '100%',
    maxWidth: '420px',
    background: 'var(--bg-surface)',
    border: '1px solid var(--border-default)',
    borderRadius: 'var(--r-xl)',
    padding: '40px',
    position: 'relative',
    boxShadow: 'var(--shadow-pop)',
  },
  logoWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    marginBottom: '28px',
  },
  logoText: {
    fontFamily: 'var(--font-display)',
    fontSize: '20px',
    fontWeight: 700,
    color: 'var(--text-primary)',
    letterSpacing: '-0.02em',
  },
  tabs: {
    display: 'flex',
    background: 'var(--bg-raised)',
    borderRadius: 'var(--r-sm)',
    padding: '3px',
    marginBottom: '28px',
    gap: '2px',
  },
  tab: {
    flex: 1,
    padding: '8px',
    borderRadius: 'var(--r-sm)',
    border: 'none',
    background: 'none',
    fontSize: '13px',
    fontFamily: 'var(--font-body)',
    fontWeight: 500,
    color: 'var(--text-muted)',
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  tabActive: {
    background: 'var(--bg-overlay)',
    color: 'var(--teal-300)',
    boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
  },
  heading: {
    fontSize: '24px',
    fontWeight: 800,
    marginBottom: '4px',
    letterSpacing: '-0.03em',
  },
  subheading: {
    color: 'var(--text-secondary)',
    fontSize: '13px',
    marginBottom: '24px',
    fontFamily: 'var(--font-body)',
    fontWeight: 300,
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
  },
  twoCol: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '5px',
  },
  label: {
    fontSize: '11px',
    fontWeight: 500,
    color: 'var(--text-secondary)',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
    fontFamily: 'var(--font-mono)',
  },
  input: {
    background: 'var(--bg-raised)',
    border: '1px solid var(--border-subtle)',
    borderRadius: 'var(--r-sm)',
    padding: '10px 12px',
    color: 'var(--text-primary)',
    fontSize: '13px',
    fontFamily: 'var(--font-body)',
    outline: 'none',
    transition: 'border-color 0.15s',
    width: '100%',
  },
  error: {
    color: 'var(--score-blocked)',
    fontSize: '12px',
    fontFamily: 'var(--font-mono)',
  },
  btn: {
    marginTop: '6px',
    background: 'var(--teal-500)',
    color: '#000',
    fontFamily: 'var(--font-display)',
    fontWeight: 700,
    fontSize: '14px',
    border: 'none',
    borderRadius: 'var(--r-sm)',
    padding: '12px',
    cursor: 'pointer',
    transition: 'background 0.15s',
    letterSpacing: '-0.01em',
    width: '100%',
  },
  switchText: {
    textAlign: 'center',
    fontSize: '12px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-body)',
    marginTop: '20px',
  },
  switchBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--teal-400)',
    fontSize: '12px',
    fontFamily: 'var(--font-body)',
    fontWeight: 500,
    cursor: 'pointer',
    padding: 0,
  },
  terms: {
    textAlign: 'center',
    fontSize: '11px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-body)',
    marginTop: '14px',
    lineHeight: 1.6,
  },
  link: {
    color: 'var(--teal-400)',
    textDecoration: 'none',
  },
  successBox: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
    padding: '16px 0',
    gap: '10px',
  },
  successIcon: {
    width: '52px',
    height: '52px',
    borderRadius: '50%',
    background: 'rgba(16,184,138,0.12)',
    border: '1px solid var(--teal-700)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '22px',
    color: 'var(--teal-400)',
    marginBottom: '6px',
  },
  successTitle: {
    fontSize: '20px',
    fontWeight: 800,
    letterSpacing: '-0.02em',
  },
  successSub: {
    fontSize: '13px',
    color: 'var(--text-muted)',
    marginBottom: '10px',
  },
}