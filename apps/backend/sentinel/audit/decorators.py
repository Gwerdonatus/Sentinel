"""
Audit Action Decorator.

Wraps view methods to automatically produce audit records after successful
execution. Zero chance of forgetting to audit an important action.

Usage:
    class TransferView(APIView):
        @audit_action(
            event_type="TRANSFER_INITIATED",
            resource_type="transfer",
            get_resource_id=lambda req, resp: resp.data.get("id"),
        )
        def post(self, request):
            ...

The decorator fires AFTER a successful response (2xx). Failed requests
(4xx, 5xx) do not produce audit events unless audit_on_failure=True.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import structlog
from rest_framework.request import Request
from rest_framework.response import Response

logger = structlog.get_logger(__name__)


def audit_action(
    event_type: str,
    resource_type: str = "",
    get_resource_id: Callable[[Request, Response], str] | None = None,
    get_metadata: Callable[[Request, Response], dict[str, object]] | None = None,
    audit_on_failure: bool = False,
    async_audit: bool = True,
) -> Callable[..., Any]:
    """
    Decorator that produces an audit event after a successful view method.

    Args:
        event_type: AuditEventType value (e.g. "USER_CREATED")
        resource_type: Type of affected resource (e.g. "user", "api_key")
        get_resource_id: Callable(request, response) -> resource_id string
        get_metadata: Callable(request, response) -> metadata dict
        audit_on_failure: Also audit 4xx/5xx responses if True
        async_audit: If True, dispatch Celery task. If False, write synchronously.
    """

    def decorator(view_method: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(view_method)
        def wrapper(view_instance: Any, request: Request, *args: Any, **kwargs: Any) -> Any:
            response: Response = view_method(view_instance, request, *args, **kwargs)

            should_audit = (
                response.status_code < 400
                or audit_on_failure
            )

            if should_audit:
                try:
                    user = request.user
                    actor_id = str(user.id) if user.is_authenticated else None
                    actor_email = user.email if user.is_authenticated else ""
                    actor_role = getattr(user, "role", "") if user.is_authenticated else ""
                    actor_ip = request.META.get("REMOTE_ADDR", "")
                    request_id = getattr(request, "request_id", "")

                    resource_id = ""
                    if get_resource_id is not None:
                        try:
                            resource_id = get_resource_id(request, response)
                        except Exception:
                            pass

                    metadata: dict[str, object] = {}
                    if get_metadata is not None:
                        try:
                            metadata = get_metadata(request, response)
                        except Exception:
                            pass

                    if async_audit:
                        from sentinel.audit.tasks import record_audit_event_task
                        record_audit_event_task.delay(
                            event_type=event_type,
                            actor_id=actor_id,
                            actor_email=actor_email,
                            actor_role=actor_role,
                            actor_ip=actor_ip,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            metadata=metadata,
                            request_id=request_id,
                        )
                    else:
                        from sentinel.audit.services import AuditEventService
                        AuditEventService().record(
                            event_type=event_type,
                            actor_id=actor_id,
                            actor_email=actor_email,
                            actor_role=actor_role,
                            actor_ip=actor_ip,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            metadata=metadata,
                            request_id=request_id,
                        )

                except Exception as exc:
                    # Audit failures must never crash the request
                    logger.error(
                        "audit_decorator_failed",
                        event_type=event_type,
                        error=str(exc),
                        exc_info=True,
                    )

            return response

        return wrapper

    return decorator
