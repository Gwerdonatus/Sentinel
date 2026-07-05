"""
Tenant Model.

A Tenant is a single organization using Sentinel.
Every significant data model carries a tenant_id foreign key.

ISOLATION STRATEGY:
    Row-level filtering via a custom queryset manager, not schema separation.

    Schema-per-tenant (CREATE SCHEMA per org) breaks down at ~100 tenants:
    - Connection pooling becomes per-schema → pool exhaustion
    - Django migrations must run per-schema → deployment complexity
    - Cross-tenant analytics require schema federation

    Row-level filtering with `tenant_id` indexed columns scales to
    thousands of tenants on shared infrastructure with proper indexing.
    The tenant filter is applied by TenantQuerySet.for_tenant() which
    is called automatically by middleware before any view logic runs.

ENFORCEMENT LAYERS:
    1. JWT/API key carries tenant_id claim — injected by middleware
    2. TenantQuerySet.for_tenant() filters every query automatically
    3. Serializers validate tenant_id matches request.tenant
    4. Django admin is scoped per-tenant for ADMIN role users

KAFKA ISOLATION:
    Each tenant gets its own Kafka topic prefix:
        sentinel.{tenant_id}.audit.events
        sentinel.{tenant_id}.risk.scores
        sentinel.{tenant_id}.alerts
    Consumer groups are also per-tenant, ensuring event ordering
    is maintained within a tenant regardless of overall throughput.
"""

from __future__ import annotations

import uuid

from django.db import models

from sentinel.core.models.base import TimestampedModel


class TenantPlan(models.TextChoices):
    STARTER = "starter", "Starter"
    GROWTH = "growth", "Growth"
    ENTERPRISE = "enterprise", "Enterprise"


class Tenant(TimestampedModel):
    """
    A single organization using Sentinel.
    All other models reference this via tenant_id.
    """

    name = models.CharField(
        max_length=128,
        help_text="Organization name. e.g. 'Acme Fintech Ltd'",
    )
    slug = models.SlugField(
        unique=True,
        max_length=64,
        help_text="URL-safe identifier. e.g. 'acme-fintech'",
    )
    plan = models.CharField(
        max_length=20,
        choices=TenantPlan.choices,
        default=TenantPlan.STARTER,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # Kafka topic prefix — computed from id, stored for fast lookup
    kafka_topic_prefix = models.CharField(
        max_length=128,
        blank=True,
        help_text="Auto-set on creation. sentinel.{tenant_id}",
    )

    # Usage limits (enforced at ingestion)
    max_events_per_day = models.PositiveIntegerField(
        default=100_000,
        help_text="Daily event ingestion limit. 0 = unlimited.",
    )
    max_api_keys = models.PositiveIntegerField(default=20)
    max_alert_rules = models.PositiveIntegerField(default=50)

    # Contact
    owner_email = models.EmailField(
        help_text="Primary contact for billing and critical alerts.",
    )

    class Meta:
        db_table = "tenants"
        ordering = ["name"]
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"

    def __str__(self) -> str:
        return f"Tenant({self.name}, plan={self.plan})"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.kafka_topic_prefix:
            self.kafka_topic_prefix = f"sentinel.{self.id}"
        super().save(*args, **kwargs)

    def get_kafka_topic(self, topic_type: str) -> str:
        """
        Return the fully-qualified Kafka topic name for this tenant.

        topic_type: "audit.events" | "risk.scores" | "alerts"
        Returns: "sentinel.{tenant_id}.audit.events"
        """
        return f"{self.kafka_topic_prefix}.{topic_type}"
