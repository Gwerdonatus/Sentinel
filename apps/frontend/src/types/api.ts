/**
 * Sentinel Shared TypeScript Types.
 *
 * Canonical type definitions for all API response shapes.
 * These match the Django serializer output — keep them in sync.
 *
 * In Phase 2+: These will be auto-generated from the OpenAPI schema
 * using `openapi-typescript`. For now they are maintained manually.
 */

// =============================================================================
// Pagination
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
// Error
// =============================================================================

export interface APIErrorResponse {
  error: {
    code: string;
    message: string;
    request_id?: string;
    details?: Record<string, unknown>;
  };
}

// =============================================================================
// Health
// =============================================================================

export type CheckStatus = "ok" | "error" | "degraded";

export interface CheckResult {
  status: CheckStatus;
  latency_ms: number;
  message?: string;
  metadata?: Record<string, unknown>;
}

export interface HealthResponse {
  status: "healthy" | "degraded";
  service: string;
  version: string;
  checks: Record<string, CheckResult>;
  total_ms: number;
}

export interface LivenessResponse {
  status: "ok";
  service: string;
}

export interface ReadinessResponse {
  status: "ready" | "not_ready";
  checks: Record<string, CheckResult>;
}

// =============================================================================
// API Root
// =============================================================================

export interface APIFeatures {
  authentication: boolean;
  audit_ledger: boolean;
  risk_scoring: boolean;
  alerting: boolean;
  webhooks: boolean;
  dashboard: boolean;
}

export interface APIRootResponse {
  service: string;
  version: string;
  api_version: string;
  status: string;
  timestamp: string;
  documentation: string;
  endpoints: Record<string, string>;
  features: APIFeatures;
}

// =============================================================================
// Phase 2+ Types (stubs — will be implemented when features land)
// =============================================================================

/**
 * Audit event types — defined now to establish the vocabulary.
 * Implementation in Phase 2.
 */
export type AuditEventType =
  | "USER_LOGIN"
  | "USER_LOGOUT"
  | "USER_LOGIN_FAILED"
  | "PASSWORD_RESET_REQUESTED"
  | "PASSWORD_RESET_COMPLETED"
  | "API_KEY_CREATED"
  | "API_KEY_ROTATED"
  | "API_KEY_REVOKED"
  | "TRANSFER_INITIATED"
  | "TRANSFER_APPROVED"
  | "TRANSFER_REJECTED"
  | "ADMIN_ACTION"
  | "WEBHOOK_DELIVERED"
  | "WEBHOOK_FAILED"
  | "DEVICE_REGISTERED"
  | "PERMISSION_CHANGED";

/**
 * Risk score levels for display purposes.
 */
export type RiskLevel = "low" | "medium" | "high" | "critical";

export function getRiskLevel(score: number): RiskLevel {
  if (score < 25) return "low";
  if (score < 50) return "medium";
  if (score < 75) return "high";
  return "critical";
}

export const RISK_LEVEL_COLORS: Record<RiskLevel, string> = {
  low: "text-green-400",
  medium: "text-yellow-400",
  high: "text-orange-400",
  critical: "text-red-400",
};
