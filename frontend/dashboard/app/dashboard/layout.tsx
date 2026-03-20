'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { authApi } from '../../lib/api'
import { useWebSocket } from '../../hooks/useWebSocket'

const NAV = [
  { href: '/dashboard', label: 'Overview', icon: IconGrid },
  { href: '/dashboard/verifications', label: 'Verifications', icon: IconShield },
  { href: '/dashboard/analytics', label: 'Analytics', icon: IconChart },
  { href: '/dashboard/api-keys', label: 'API Keys', icon: IconKey },
  { href: '/dashboard/settings', label: 'Settings', icon: IconGear },
]

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { status } = useWebSocket()

  async function handleLogout() {
    await authApi.logout()
    router.push('/')
  }

  return (
    <div style={styles.shell}>
      {/* Sidebar */}
      <aside style={styles.sidebar}>
        {/* Logo */}
        <div style={styles.logoRow}>
          <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
            <circle cx="20" cy="20" r="19" stroke="var(--teal-500)" strokeWidth="1.5" />
            <circle cx="20" cy="20" r="8" fill="var(--teal-500)" opacity="0.15" />
            <circle cx="20" cy="20" r="4" fill="var(--teal-400)" />
            <path d="M20 6C10 6 4 20 4 20C4 20 10 34 20 34C30 34 36 20 36 20C36 20 30 6 20 6Z"
              stroke="var(--teal-500)" strokeWidth="1.2" fill="none" />
          </svg>
          <span style={styles.logoText}>HumanEye</span>
        </div>

        {/* Live indicator */}
        <div style={styles.liveRow}>
          <span style={{
            ...styles.liveDot,
            background: status === 'connected' ? 'var(--teal-400)' : 'var(--text-muted)',
            animation: status === 'connected' ? 'pulse-ring 2s infinite' : 'none',
          }} />
          <span style={styles.liveText}>
            {status === 'connected' ? 'Live feed' : 'Connecting…'}
          </span>
        </div>

        {/* Nav */}
        <nav style={styles.nav}>
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== '/dashboard' && pathname.startsWith(href))
            return (
              <Link key={href} href={href} style={{
                ...styles.navItem,
                ...(active ? styles.navItemActive : {}),
              }}>
                <Icon size={16} active={active} />
                <span>{label}</span>
              </Link>
            )
          })}
        </nav>

        <div style={styles.sidebarBottom}>
          <button onClick={handleLogout} style={styles.logoutBtn}>
            <IconLogout size={14} active={false} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main style={styles.main}>
        {children}
      </main>
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  shell: {
    display: 'flex',
    minHeight: '100vh',
  },
  sidebar: {
    width: '220px',
    flexShrink: 0,
    background: 'var(--bg-surface)',
    borderRight: '1px solid var(--border-subtle)',
    display: 'flex',
    flexDirection: 'column',
    padding: '24px 16px',
    position: 'sticky',
    top: 0,
    height: '100vh',
    overflowY: 'auto',
  },
  logoRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '0 8px',
    marginBottom: '28px',
  },
  logoText: {
    fontFamily: 'var(--font-display)',
    fontWeight: 800,
    fontSize: '17px',
    letterSpacing: '-0.02em',
  },
  liveRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    background: 'var(--bg-raised)',
    borderRadius: 'var(--r-sm)',
    marginBottom: '20px',
  },
  liveDot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  liveText: {
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
  },
  nav: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    flex: 1,
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '9px 12px',
    borderRadius: 'var(--r-sm)',
    fontSize: '13px',
    fontWeight: 500,
    fontFamily: 'var(--font-body)',
    color: 'var(--text-muted)',
    textDecoration: 'none',
    transition: 'all 0.15s',
  },
  navItemActive: {
    background: 'rgba(16,184,138,0.08)',
    color: 'var(--teal-300)',
    borderLeft: '2px solid var(--teal-500)',
  },
  sidebarBottom: {
    borderTop: '1px solid var(--border-subtle)',
    paddingTop: '16px',
  },
  logoutBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    width: '100%',
    padding: '9px 12px',
    background: 'none',
    border: 'none',
    borderRadius: 'var(--r-sm)',
    color: 'var(--text-muted)',
    fontSize: '13px',
    fontFamily: 'var(--font-body)',
    cursor: 'pointer',
    transition: 'color 0.15s',
  },
  main: {
    flex: 1,
    minWidth: 0,
    padding: '32px',
    overflowY: 'auto',
  },
}

// ── Icon Components ────────────────────────────────────────────

function IconGrid({ size, active }: { size: number; active: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="6" height="6" rx="1.5" fill={active ? 'var(--teal-400)' : 'currentColor'} />
      <rect x="9" y="1" width="6" height="6" rx="1.5" fill={active ? 'var(--teal-400)' : 'currentColor'} />
      <rect x="1" y="9" width="6" height="6" rx="1.5" fill={active ? 'var(--teal-400)' : 'currentColor'} />
      <rect x="9" y="9" width="6" height="6" rx="1.5" fill={active ? 'var(--teal-400)' : 'currentColor'} />
    </svg>
  )
}

function IconShield({ size, active }: { size: number; active: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M8 1.5L2.5 4v4c0 3 2.5 5.5 5.5 6.5 3-1 5.5-3.5 5.5-6.5V4L8 1.5Z"
        stroke={active ? 'var(--teal-400)' : 'currentColor'} strokeWidth="1.2" fill="none" />
      <path d="M5.5 8l1.8 1.8L10.5 6" stroke={active ? 'var(--teal-400)' : 'currentColor'} strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  )
}

function IconChart({ size, active }: { size: number; active: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <rect x="2" y="9" width="3" height="5" rx="1" fill={active ? 'var(--teal-400)' : 'currentColor'} />
      <rect x="6.5" y="5" width="3" height="9" rx="1" fill={active ? 'var(--teal-400)' : 'currentColor'} />
      <rect x="11" y="2" width="3" height="12" rx="1" fill={active ? 'var(--teal-400)' : 'currentColor'} />
    </svg>
  )
}

function IconKey({ size, active }: { size: number; active: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="6" cy="7" r="3.5" stroke={active ? 'var(--teal-400)' : 'currentColor'} strokeWidth="1.2" />
      <path d="M9 7h5.5M12 7v2.5M14 7v2" stroke={active ? 'var(--teal-400)' : 'currentColor'} strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  )
}

function IconGear({ size, active }: { size: number; active: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2.5" stroke={active ? 'var(--teal-400)' : 'currentColor'} strokeWidth="1.2" />
      <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4"
        stroke={active ? 'var(--teal-400)' : 'currentColor'} strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  )
}

function IconLogout({ size, active }: { size: number; active: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <path d="M6 2H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3M10 11l3-3-3-3M13 8H6"
        stroke={active ? 'var(--teal-400)' : 'currentColor'} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
