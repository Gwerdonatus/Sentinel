from django.apps import AppConfig


class ComplianceConfig(AppConfig):
    name = "sentinel.compliance"
    label = "sentinel_compliance"
    verbose_name = "Sentinel Compliance Reports"

    def ready(self) -> None:
        pass
