from django.apps import AppConfig


class RiskConfig(AppConfig):
    name = "sentinel.risk"
    label = "sentinel_risk"
    verbose_name = "Sentinel Risk Intelligence"

    def ready(self) -> None:
        pass
