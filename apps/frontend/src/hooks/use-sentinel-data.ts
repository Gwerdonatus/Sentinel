/**
 * Sentinel Dashboard Query Hooks.
 *
 * All server state goes through TanStack Query. Zero fetch-in-useEffect.
 * Every hook returns { data, isLoading, error, refetch } consistently.
 *
 * Stale times are tuned per data type:
 *   - Risk summary: 30s (live operational data)
 *   - Alerts: 60s (actioned items)
 *   - Audit events: 2min (historical, doesn't change)
 *   - Compliance reports: 10s (polling for READY status)
 */

"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/dashboard-api";
import type {
  AlertDetail,
  AlertListItem,
  AlertRule,
  ActorRiskProfile,
  AuditEvent,
  ComplianceReport,
  APIKeyListItem,
  PaginatedResponse,
  RiskSummary,
} from "@/types/dashboard";

// =============================================================================
// Query Keys
// =============================================================================

export const queryKeys = {
  riskSummary: ["risk", "summary"] as const,
  alerts: (filters?: Record<string, string>) => ["alerts", filters ?? {}] as const,
  alertDetail: (id: string) => ["alerts", id] as const,
  alertRules: ["alerts", "rules"] as const,
  auditEvents: (filters?: Record<string, string>) => ["events", filters ?? {}] as const,
  actorProfile: (actorId: string) => ["risk", "actors", actorId] as const,
  apiKeys: ["api-keys"] as const,
  complianceReports: ["compliance", "reports"] as const,
  complianceReport: (id: string) => ["compliance", "reports", id] as const,
};

// =============================================================================
// Risk & Alerts
// =============================================================================

export function useRiskSummary() {
  return useQuery({
    queryKey: queryKeys.riskSummary,
    queryFn: () => dashboardApi.get<RiskSummary>("risk/summary"),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useAlerts(filters?: Record<string, string>) {
  return useQuery({
    queryKey: queryKeys.alerts(filters),
    queryFn: () =>
      dashboardApi.get<PaginatedResponse<AlertListItem>>("alerts", { params: filters }),
    staleTime: 60_000,
  });
}

export function useAlertDetail(id: string) {
  return useQuery({
    queryKey: queryKeys.alertDetail(id),
    queryFn: () => dashboardApi.get<AlertDetail>(`alerts/${id}`),
    staleTime: 30_000,
    enabled: !!id,
  });
}

export function useAlertRules() {
  return useQuery({
    queryKey: queryKeys.alertRules,
    queryFn: () => dashboardApi.get<AlertRule[]>("alerts/rules"),
    staleTime: 5 * 60_000,
  });
}

export function useAcknowledgeAlert() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) =>
      dashboardApi.post<AlertDetail>(`alerts/${alertId}/acknowledge`),
    onSuccess: (data) => {
      client.setQueryData(queryKeys.alertDetail(data.id), data);
      client.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useResolveAlert() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ alertId, note }: { alertId: string; note?: string }) =>
      dashboardApi.post<AlertDetail>(`alerts/${alertId}/resolve`, { note }),
    onSuccess: (data) => {
      client.setQueryData(queryKeys.alertDetail(data.id), data);
      client.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

// =============================================================================
// Audit Events
// =============================================================================

export function useAuditEvents(filters?: Record<string, string>) {
  return useQuery({
    queryKey: queryKeys.auditEvents(filters),
    queryFn: () =>
      dashboardApi.get<PaginatedResponse<AuditEvent>>("events", { params: filters }),
    staleTime: 2 * 60_000,
  });
}

// =============================================================================
// Actor Risk Profile
// =============================================================================

export function useActorRiskProfile(actorId: string) {
  return useQuery({
    queryKey: queryKeys.actorProfile(actorId),
    queryFn: () => dashboardApi.get<ActorRiskProfile>(`risk/actors/${actorId}`),
    staleTime: 60_000,
    enabled: !!actorId,
  });
}

// =============================================================================
// API Keys
// =============================================================================

export function useAPIKeys() {
  return useQuery({
    queryKey: queryKeys.apiKeys,
    queryFn: () => dashboardApi.get<APIKeyListItem[]>("api-keys"),
    staleTime: 2 * 60_000,
  });
}

export function useRevokeAPIKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) => dashboardApi.delete(`api-keys/${keyId}`),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.apiKeys });
    },
  });
}

// =============================================================================
// Compliance Reports
// =============================================================================

export function useComplianceReports() {
  return useQuery({
    queryKey: queryKeys.complianceReports,
    queryFn: () => dashboardApi.get<ComplianceReport[]>("compliance/reports"),
    staleTime: 30_000,
  });
}

export function useComplianceReport(id: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.complianceReport(id),
    queryFn: () => dashboardApi.get<ComplianceReport>(`compliance/reports/${id}`),
    // Poll every 5s until the report is ready or failed
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "pending" || status === "generating") return 5_000;
      return false;
    },
    staleTime: 10_000,
    enabled: !!id && enabled,
  });
}

export function useRequestComplianceReport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      report_type: string;
      report_format: string;
      from_dt: string;
      to_dt: string;
      filters?: Record<string, unknown>;
    }) => dashboardApi.post<ComplianceReport>("compliance/reports", payload),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.complianceReports });
    },
  });
}
