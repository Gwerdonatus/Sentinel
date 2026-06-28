"""
Auth Service Signals.

Django signals that hook into user lifecycle events to produce audit records.
Using signals (rather than overriding model methods) keeps the audit logic
decoupled from the model itself — the model stays clean, audit is cross-cutting.
"""

from __future__ import annotations

import structlog
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

logger = structlog.get_logger(__name__)


@receiver(user_logged_in)
def on_user_logged_in(
    sender: type,
    request: object,
    user: object,
    **kwargs: object,
) -> None:
    """
    Fired by Django's login() function after successful authentication.
    Records successful login audit event and updates security fields.
    """
    from sentinel.audit.tasks import record_audit_event_task

    ip = getattr(request, "META", {}).get("REMOTE_ADDR", "unknown")  # type: ignore[union-attr]

    logger.info(
        "user_logged_in",
        user_id=str(getattr(user, "id", None)),
        email=getattr(user, "email", None),
        ip_address=ip,
    )

    # Update security fields on user model
    if hasattr(user, "record_successful_login"):
        user.record_successful_login(ip)  # type: ignore[union-attr]

    # Produce immutable audit event asynchronously
    record_audit_event_task.delay(
        event_type="USER_LOGIN",
        actor_id=str(getattr(user, "id", None)),
        actor_email=getattr(user, "email", None),
        resource_type="user",
        resource_id=str(getattr(user, "id", None)),
        metadata={"ip_address": ip},
    )


@receiver(user_logged_out)
def on_user_logged_out(
    sender: type,
    request: object,
    user: object,
    **kwargs: object,
) -> None:
    """Fired on explicit logout. Records logout audit event."""
    from sentinel.audit.tasks import record_audit_event_task

    if user is None:
        return

    ip = getattr(request, "META", {}).get("REMOTE_ADDR", "unknown")  # type: ignore[union-attr]

    logger.info(
        "user_logged_out",
        user_id=str(getattr(user, "id", None)),
        email=getattr(user, "email", None),
    )

    record_audit_event_task.delay(
        event_type="USER_LOGOUT",
        actor_id=str(getattr(user, "id", None)),
        actor_email=getattr(user, "email", None),
        resource_type="user",
        resource_id=str(getattr(user, "id", None)),
        metadata={"ip_address": ip},
    )


@receiver(user_login_failed)
def on_user_login_failed(
    sender: type,
    credentials: dict[str, object],
    request: object,
    **kwargs: object,
) -> None:
    """Fired on authentication failure. Records failed login attempt."""
    from sentinel.audit.tasks import record_audit_event_task

    ip = getattr(request, "META", {}).get("REMOTE_ADDR", "unknown")  # type: ignore[union-attr]
    email = credentials.get("email", "unknown")

    logger.warning(
        "user_login_failed",
        email=email,
        ip_address=ip,
    )

    record_audit_event_task.delay(
        event_type="USER_LOGIN_FAILED",
        actor_id=None,
        actor_email=str(email),
        resource_type="user",
        resource_id=None,
        metadata={"ip_address": ip, "attempted_email": str(email)},
    )
