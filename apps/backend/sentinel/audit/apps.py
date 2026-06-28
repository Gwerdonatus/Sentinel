from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = "sentinel.audit"
    label = "sentinel_audit"
    verbose_name = "Sentinel Audit Ledger"

    def ready(self) -> None:
        pass
