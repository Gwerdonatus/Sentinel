"""
Sentinel Base Models.

All Sentinel models inherit from these base classes.
They provide:
- UUID primary keys (non-enumerable, distributed-safe)
- created_at / updated_at timestamps (partition-key candidates)
- __str__ conventions

See ADR-004 (PostgreSQL partitioning) and ADR-005 (UUID primary keys)
for the rationale behind these choices.
"""

from __future__ import annotations

import uuid

from django.db import models


class TimestampedModel(models.Model):
    """
    Abstract base model with UUID PK and timestamp fields.

    All Sentinel models should inherit from this.

    UUID primary keys:
        - Non-enumerable (no sequential ID exposure)
        - Distributed-safe (can be generated without DB coordination)
        - Merge-safe (no collision risk when combining datasets)

    Timestamps:
        - Both are non-nullable with DB defaults
        - created_at is the candidate partition key for large tables
        - Both use timestamptz (timezone-aware) — UTC always
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier (UUIDv4, non-enumerable)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="UTC timestamp when this record was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="UTC timestamp when this record was last modified",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id}>"


class SoftDeletableModel(TimestampedModel):
    """
    Abstract base model with soft delete support.

    Records are never hard-deleted. Instead, deleted_at is set.
    The default queryset filters out soft-deleted records.

    Use for: API keys, users, organizations
    Do NOT use for: audit events (immutable, no deletion at all)
    """

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="UTC timestamp when this record was soft-deleted. Null if active.",
    )

    class Meta(TimestampedModel.Meta):
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
