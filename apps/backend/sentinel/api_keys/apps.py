from django.apps import AppConfig


class APIKeysConfig(AppConfig):
    name = "sentinel.api_keys"
    label = "sentinel_api_keys"
    verbose_name = "Sentinel API Keys"

    def ready(self) -> None:
        pass
