// ============================================================
// HumanEye — React Query Hooks
// All server state goes through these hooks.
// Uses TanStack Query v5 for caching + background refresh.
// ============================================================

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  verificationsApi,
  statsApi,
  apiKeysApi,
  settingsApi,
  authApi,
} from '../lib/api'

// ── Auth ──────────────────────────────────────────────────────

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => authApi.me(),
    staleTime: 5 * 60 * 1000,
  })
}

// ── Dashboard Stats ───────────────────────────────────────────

export function useDashboardStats() {
  return useQuery({
    queryKey: ['stats', 'dashboard'],
    queryFn: () => statsApi.dashboard(),
    refetchInterval: 30_000,
  })
}

// ── Verifications ─────────────────────────────────────────────

export function useVerifications(params?: {
  page?: number
  page_size?: number
  verdict?: string
  min_score?: number
  max_score?: number
  action_type?: string
  date_from?: string
  date_to?: string
  search?: string
}) {
  return useQuery({
    queryKey: ['verifications', params],
    queryFn: () => verificationsApi.list(params),
    placeholderData: (prev) => prev,
  })
}

export function useVerification(id: string) {
  return useQuery({
    queryKey: ['verification', id],
    queryFn: () => verificationsApi.get(id),
    enabled: !!id,
  })
}

// ── Analytics ─────────────────────────────────────────────────

export function useAnalytics(period: '7d' | '30d' | '90d' = '30d') {
  return useQuery({
    queryKey: ['analytics', period],
    queryFn: () => statsApi.analytics({ period }),
    staleTime: 5 * 60 * 1000,
  })
}

// ── API Keys ──────────────────────────────────────────────────

export function useApiKeys() {
  return useQuery({
    queryKey: ['apiKeys'],
    queryFn: () => apiKeysApi.list(),
  })
}

export function useCreateApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => apiKeysApi.create(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['apiKeys'] }),
  })
}

export function useRevokeApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiKeysApi.revoke(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['apiKeys'] }),
  })
}

// ── Settings ──────────────────────────────────────────────────

export function useWebhookConfig() {
  return useQuery({
    queryKey: ['webhook'],
    queryFn: () => settingsApi.getWebhook(),
  })
}

export function useSaveWebhook() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: settingsApi.saveWebhook,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['webhook'] }),
  })
}
