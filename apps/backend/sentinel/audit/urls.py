from django.urls import path

from sentinel.audit.views import (
    AuditEventDetailView,
    AuditEventIngestView,
    AuditEventListView,
    AuditEventVerifyView,
)

urlpatterns = [
    path("", AuditEventListView.as_view(), name="audit-event-list"),
    path("ingest/", AuditEventIngestView.as_view(), name="audit-event-ingest"),
    path("<str:event_id>/", AuditEventDetailView.as_view(), name="audit-event-detail"),
    path("<str:event_id>/verify/", AuditEventVerifyView.as_view(), name="audit-event-verify"),
]
