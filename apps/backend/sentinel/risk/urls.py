from django.urls import path

from sentinel.risk.views import (
    ActorRiskProfileView,
    AlertAcknowledgeView,
    AlertDetailView,
    AlertListView,
    AlertResolveView,
    AlertRuleDetailView,
    AlertRuleListView,
    RiskSummaryView,
)

urlpatterns = [
    # Alerts
    path("alerts/", AlertListView.as_view(), name="alert-list"),
    path("alerts/rules/", AlertRuleListView.as_view(), name="alert-rule-list"),
    path("alerts/rules/<str:rule_id>/", AlertRuleDetailView.as_view(), name="alert-rule-detail"),
    path("alerts/<str:alert_id>/", AlertDetailView.as_view(), name="alert-detail"),
    path("alerts/<str:alert_id>/acknowledge/", AlertAcknowledgeView.as_view(), name="alert-acknowledge"),
    path("alerts/<str:alert_id>/resolve/", AlertResolveView.as_view(), name="alert-resolve"),

    # Risk intelligence
    path("risk/summary/", RiskSummaryView.as_view(), name="risk-summary"),
    path("risk/actors/<str:actor_id>/", ActorRiskProfileView.as_view(), name="actor-risk-profile"),
]
