# ============================================================
# HumanEye — Dashboard Dockerfile (Next.js 14)
# ============================================================

FROM node:20-alpine AS base
WORKDIR /app/dashboard
RUN apk add --no-cache curl

# ── Dependencies ──────────────────────────────────────────
FROM base AS deps
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm ci

# ── Development (hot reload) ──────────────────────────────
FROM base AS development
COPY --from=deps /app/dashboard/node_modules ./node_modules
COPY dashboard/ ./
ENV NODE_ENV=development
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ── Build ─────────────────────────────────────────────────
FROM base AS builder
COPY --from=deps /app/dashboard/node_modules ./node_modules
COPY dashboard/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Production ────────────────────────────────────────────
FROM node:20-alpine AS production
WORKDIR /app/dashboard
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/dashboard/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/dashboard/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/dashboard/.next/static ./.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:3000 || exit 1
