from django.apps import AppConfig


class TenantsConfig(AppConfig):
    name = "sentinel.tenants"
    label = "sentinel_tenants"
    verbose_name = "Sentinel Tenants"

    def ready(self) -> None:
        pass
