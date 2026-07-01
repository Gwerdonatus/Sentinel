/**
 * Sentinel Dashboard Types — Phase 4
 *
 * All types match backend serializer shapes exactly.
 * Organized by domain: auth, audit, risk, api_keys, compliance.
 */

// =============================================================================
// Shared
// =============================================================================

export interface PaginatedResponse<T> {
  pagination: {
    next: string | null;
    previous: string | null;
    page_size: number;
  };
  results: T[];
}

// =============================================================================
// Auth
// =============================================================================

export type UserRole = "ADMIN" | "AUDITOR" | "ANALYST" | "VIEWER";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  last_login: string | null;
  last_login_ip: string | null;
  must_change_password: boolean;
  created_at: string;
  updated_at: string;
}

// =============================================================================
// Audit Events
// =============================================================================

export type ActorType = "HUMAN" | "SERVICE" | "AI_AGENT";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export const RISK_LEVEL_COLORS: Record<RiskLevel, string> = {
  low: "text-green-400",
  medium: "text-yellow-400",
  high: "text-orange-400",
  critical: "text-red-500",
};

export const RISK_LEVEL_BG: Record<RiskLevel, string> = {
  low: "bg-green-900/30 text-green-400",
  medium: "bg-yellow-900/30 text-yellow-400",
  high: "bg-orange-900/30 text-orange-400",
  critical: "bg-red-900/30 text-red-400",
};

export const ACTOR_TYPE_ICONS: Record<ActorType, string> = {
  HUMAN: "👤",
  SERVICE: "⚙️",
  AI_AGENT: "🤖",
};

export interface AuditEvent {
  id: string;
  event_type: string;
  actor_id: string | null;
  actor_type: ActorType;
  actor_email: string;
  actor_role: string;
  actor_ip: string | null;
  agent_name: string;
  resource_type: string;
  resource_id: string;
  metadata: Record<string, unknown>;
  request_id: string;
  signature: string;
  risk_score: number | null;
  created_at: string;
}

// =============================================================================
// Risk & Alerts
// =============================================================================

export type AlertSeverity = "low" | "medium" | "high" | "critical";
export type AlertStatus = "open" | "acknowledged" | "resolved" | "suppressed";

export const SEVERITY_COLORS: Record<AlertSeverity, string> = {
  low: "bg-green-900/30 text-green-400 border-green-800",
  medium: "bg-yellow-900/30 text-yellow-400 border-yellow-800",
  high: "bg-orange-900/30 text-orange-400 border-orange-800",
  critical: "bg-red-900/30 text-red-400 border-red-800",
};

export const STATUS_COLORS: Record<AlertStatus, string> = {
  open: "text-red-400",
  acknowledged: "text-yellow-400",
  resolved: "text-green-400",
  suppressed: "text-gray-500",
};

export interface AlertListItem {
  id: string;
  rule_name: string;
  severity: AlertSeverity;
  status: AlertStatus;
  actor_type: ActorType;
  actor_email: string;
  agent_name: string;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  created_at: string;
}

export interface AlertDetail extends AlertListItem {
  rule_id: string;
  audit_event_id: string;
  actor_id: string | null;
  risk_explanation: string;
  acknowledged_by_email: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  resolution_note: string;
  notifications_sent: Array<{ channel: string; outcome: string; timestamp: string }>;
  updated_at: string;
}

export interface AlertRule {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  is_builtin: boolean;
  severity: AlertSeverity;
  condition: Record<string, unknown>;
  notification_channels: string[];
  suppression_window_minutes: number;
  trigger_count: number;
  created_at: string;
}

export interface RiskSummary {
  open_alerts: {
    total: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  last_24h: {
    total_events: number;
    ai_agent_events: number;
    high_risk_events: number;
    new_alerts: number;
  };
  top_risky_ai_agents: Array<{ agent_name: string; event_count: number }>;
}

export interface ActorRiskProfile {
  actor_id: string;
  actor_type: ActorType;
  actor_email: string;
  agent_name: string;
  last_30_days: {
    total_events: number;
    avg_risk_score: number;
    max_risk_score: number;
    open_alerts: number;
  };
  recent_events: Array<{
    id: string;
    event_type: string;
    risk_score: number | null;
    created_at: string;
  }>;
}

// =============================================================================
// API Keys
// =============================================================================

export type APIKeyActorType = "HUMAN_API" | "SERVICE" | "AI_AGENT";

export interface APIKeyListItem {
  id: string;
  name: string;
  actor_type: APIKeyActorType;
  environment: "live" | "test";
  key_prefix: string;
  scopes: string[];
  agent_name: string;
  agent_version: string;
  agent_description: string;
  is_active: boolean;
  is_expired: boolean;
  total_uses: number;
  last_used_at: string | null;
  last_used_ip: string | null;
  expires_at: string | null;
  created_by_email: string | null;
  created_at: string;
}

export interface APIKeyCreated extends APIKeyListItem {
  key: string; // Shown once — never retrievable again
}

// =============================================================================
// Compliance Reports
// =============================================================================

export type ReportType = "pci_dss" | "soc2" | "custom";
export type ReportFormat = "pdf" | "csv" | "json";
export type ReportStatus = "pending" | "generating" | "ready" | "failed" | "expired";

export interface ComplianceReport {
  id: string;
  report_type: ReportType;
  report_format: ReportFormat;
  status: ReportStatus;
  from_dt: string;
  to_dt: string;
  filters: Record<string, unknown>;
  summary: {
    total_events?: number;
    by_actor_type?: Record<string, number>;
    ai_agents_involved?: Array<{ agent_name: string; event_count: number }>;
    high_risk_event_count?: number;
    top_event_types?: Record<string, number>;
    generated_at?: string;
  };
  file_size_bytes: number | null;
  error_message: string;
  requested_by_email: string | null;
  generated_at: string | null;
  expires_at: string | null;
  created_at: string;
}

// =============================================================================
// Helpers
// =============================================================================

export function getRiskLevel(score: number | null): RiskLevel {
  if (score === null) return "low";
  if (score < 25) return "low";
  if (score < 50) return "medium";
  if (score < 75) return "high";
  return "critical";
}

export function formatActorLabel(event: Pick<AuditEvent, "actor_type" | "actor_email" | "agent_name">): string {
  if (event.actor_type === "AI_AGENT" && event.agent_name) return `🤖 ${event.agent_name}`;
  if (event.actor_type === "SERVICE") return `⚙️ Service`;
  return `👤 ${event.actor_email || "Unknown"}`;
}
