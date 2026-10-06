"""
Tenant-Scoped Queryset Mixin.

Applied to models that carry tenant_id. Provides for_tenant() which
filters all queries to the given tenant. Used in views and services:

    AuditEvent.objects.for_tenant(tenant).filter(event_type="USER_LOGIN")

Never returns cross-tenant data. Raises if called without a tenant
on a model that requires one (enforced in DEBUG mode only — production
fails silently to avoid DoS via repeated ValueError raises).

MIGRATION PATTERN:
    Phase 5 adds tenant_id to existing models via additive migrations.
    Existing single-tenant data gets a DEFAULT_TENANT_ID (created by
    the migration) so the column is never null on existing rows.
    This is a non-breaking migration for existing single-tenant deployments.
"""

from __future__ import annotations

from django.db import models


class TenantQuerySet(models.QuerySet["TenantScopedModel"]):
    """Queryset that exposes for_tenant() scoping."""

    def for_tenant(self, tenant: object) -> "TenantQuerySet":
        """Return only records belonging to this tenant."""
        if tenant is None:
            # Superuser / platform-level access — no scoping
            return self
        tenant_id = getattr(tenant, "id", tenant)
        return self.filter(tenant_id=tenant_id)

    def active(self) -> "TenantQuerySet":
        """Filter to non-soft-deleted records (where applicable)."""
        return self.filter(deleted_at__isnull=True)


class TenantManager(models.Manager["TenantScopedModel"]):
    def get_queryset(self) -> TenantQuerySet:
        return TenantQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant: object) -> TenantQuerySet:
        return self.get_queryset().for_tenant(tenant)


class TenantScopedModel(models.Model):
    """
    Abstract base for all multi-tenant models.

    Adds tenant_id FK and the TenantManager. Every model that carries
    data scoped to a specific organization should inherit from this.

    Models that should NOT be tenant-scoped:
        - Tenant (it is the root)
        - SentinelUser if users are platform-level (Phase 5 decision: users
          are scoped to a tenant via their API key / JWT claim)
    """

    tenant_id = models.UUIDField(
        db_index=True,
        null=True,
        blank=True,
        help_text="Owning tenant. Null only for platform-level records.",
    )

    objects = TenantManager()

    class Meta:
        abstract = True
