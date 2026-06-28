from django.apps import AppConfig


class AuthServiceConfig(AppConfig):
    name = "sentinel.auth_service"
    label = "sentinel_auth"
    verbose_name = "Sentinel Authentication"

    def ready(self) -> None:
        # Import signal handlers to register them
        import sentinel.auth_service.signals  # noqa: F401
