from django.urls import path

from sentinel.core.health.views import HealthSummaryView, LivenessView, ReadinessView

urlpatterns = [
    path("", HealthSummaryView.as_view(), name="health-summary"),
    path("live/", LivenessView.as_view(), name="health-liveness"),
    path("ready/", ReadinessView.as_view(), name="health-readiness"),
]
