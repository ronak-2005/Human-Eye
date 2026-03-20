# HumanEye — Frontend

Human Verification Infrastructure for the AI Age.

This directory contains both frontend products:

- **`/dashboard`** — Customer portal (Next.js 14 + TypeScript)
- **`/sdk`** — Browser SDK (`@humaneye/sdk`, TypeScript)

---

## Quick Start

### Dashboard

```bash
cd dashboard
npm install
cp .env.example .env.local
# Edit .env.local — set NEXT_PUBLIC_API_URL to your backend URL
npm run dev
# Opens on http://localhost:3000
```

### Browser SDK

```bash
cd sdk
npm install
npm run build        # Builds dist/index.esm.js + dist/index.cjs.js
npm run size         # Checks bundle is under 50KB gzipped
npm test             # Runs unit tests
```

---

## Architecture

```
humaneye/
├── dashboard/                    ← Next.js 14 customer portal
│   ├── app/
│   │   ├── page.tsx              ← Login
│   │   └── dashboard/
│   │       ├── layout.tsx        ← Sidebar nav
│   │       ├── page.tsx          ← Overview stats
│   │       ├── verifications/    ← List + detail pages
│   │       ├── api-keys/         ← Key management
│   │       ├── analytics/        ← Charts (Recharts)
│   │       └── settings/         ← Webhook + account
│   ├── components/
│   │   └── ScoreGauge.tsx        ← SVG trust score gauge
│   ├── hooks/
│   │   ├── index.ts              ← TanStack Query hooks
│   │   └── useWebSocket.ts       ← Live verification feed
│   └── lib/
│       ├── api.ts                ← Typed API client
│       └── types.ts              ← All TypeScript interfaces
│
└── sdk/                          ← @humaneye/sdk browser package
    ├── src/
    │   ├── index.ts              ← Public API + HumanEye class
    │   ├── types.ts              ← All types
    │   └── core/
    │       ├── SignalCollector.ts ← Event listeners (keystrokes, mouse, scroll)
    │       ├── BatchSender.ts    ← 500ms batch flushing
    │       └── SessionManager.ts ← Session ID + metadata
    ├── tests/
    │   └── sdk.test.ts           ← Unit tests (Vitest)
    └── scripts/
        └── check-size.js         ← Fails CI if bundle > 50KB
```

---

## API Contract (Backend Requirements)

The dashboard consumes these backend endpoints. The backend engineer must implement all of these.

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Email + password → session cookie |
| POST | `/api/v1/auth/logout` | Clear session |
| GET | `/api/v1/auth/me` | Current customer object |

### Core Verification
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/verify` | Run full verification pipeline |
| POST | `/api/v1/signals` | Receive raw behavioral signal batch from SDK |
| GET | `/api/v1/verifications` | Paginated list with filters |
| GET | `/api/v1/verifications/{id}` | Single verification detail |
| GET | `/api/v1/scores/{user_id}` | Current trust score for a user |

### Stats & Analytics
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/stats/dashboard` | Summary stats for home page |
| GET | `/api/v1/stats/analytics?period=7d\|30d\|90d` | Charts data |

### API Keys
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/keys` | List all keys (masked) |
| POST | `/api/v1/keys` | Create key — returns plaintext ONCE |
| DELETE | `/api/v1/keys/{id}` | Revoke key |

### Settings
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/settings/webhook` | Get webhook config |
| PATCH | `/api/v1/settings/webhook` | Update webhook config |
| GET | `/api/v1/settings/account` | Get account info |
| PATCH | `/api/v1/settings/account` | Update account info |

### WebSocket
| Protocol | Path | Description |
|----------|------|-------------|
| WS | `/api/v1/ws/verifications` | Push `{ type: "verification.complete", data: VerificationListItem }` on each new verification |

### Response format for errors
```json
{
  "error": "validation_error",
  "message": "Human-readable description",
  "code": "400"
}
```

---

## SDK Usage (For Your Backend + Pilot Customers)

```bash
npm install @humaneye/sdk
```

```typescript
import HumanEye from '@humaneye/sdk'

// Initialize once on page load
const eye = new HumanEye({
  apiKey: 'he_live_xxxxxxxxxxxx',
  context: { action_type: 'job_application' },
})

// On form submit — sends all buffered signals + optional text
const result = await eye.verify({
  text_content: coverLetterText,
  platform_user_id: currentUserId,
})

if (result.score !== null) {
  console.log(result.score)    // 0-100
  console.log(result.verdict)  // 'human' | 'suspicious' | 'blocked' | ...
}
```

### SDK Security Properties
- **No key logging** — captures `KeyboardEvent.code` (physical key) only, never `KeyboardEvent.key` (character value)
- **HTTPS required** — throws on HTTP (localhost exempt for dev)
- **Zero dependencies** — no npm packages that inflate bundle
- **Non-blocking** — event listeners are passive, no main thread blocking
- **Graceful degradation** — returns `{ score: null, verdict: 'error' }` if API unreachable

---

## Design System

The dashboard uses a custom dark design system defined in `globals.css`:

| Token | Value | Use |
|-------|-------|-----|
| `--bg-base` | `#080C10` | Page background |
| `--teal-500` | `#10B88A` | Primary brand colour |
| `--score-human` | `#10B88A` | Score ≥ 80 |
| `--score-suspicious` | `#FB923C` | Score 25–49 |
| `--score-blocked` | `#F43F5E` | Score 0–24 |
| `--font-display` | Syne | Headings, scores |
| `--font-body` | DM Sans | Body text |
| `--font-mono` | DM Mono | Code, IDs, metadata |

---

## Security Notes (Coordinate with Security Engineer)

- [ ] CSP headers in `next.config.js` need nonces for inline scripts (replace `unsafe-inline`)
- [ ] SDK capture code must be reviewed before every SDK release
- [ ] Auth flow: session cookie must be `httpOnly, Secure, SameSite=Strict`
- [ ] API keys masked in all UI (`he_live_xxxx...xxxx`) — full key shown once at creation only
- [ ] All user-supplied content sanitized with DOMPurify before rendering (add to API key name display)
- [ ] No sensitive data in `localStorage` or `sessionStorage`
