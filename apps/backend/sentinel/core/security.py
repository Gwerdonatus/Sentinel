"""
Sentinel Security Utilities.

Provides the django-axes lockout callable that returns a DRF-compatible
JSON response instead of the default HTML 403 page.

Registered in settings.py as AXES_LOCKOUT_CALLABLE.
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse


def axes_lockout_response(request: HttpRequest, credentials: dict[str, object]) -> JsonResponse:
    """
    Return a structured JSON 429 response when an account is locked out.

    django-axes calls this function when the failure threshold is exceeded.
    We return 429 (Too Many Requests) rather than 403 (Forbidden) because
    the lockout is temporary and the standard indicates retry-after semantics.
    """
    return JsonResponse(
        {
            "error": {
                "code": "account_locked",
                "message": (
                    "Too many failed authentication attempts. "
                    "Your account has been temporarily locked. "
                    "Please try again after 1 hour."
                ),
                "request_id": getattr(request, "request_id", None),
            }
        },
        status=429,
    )
